# Copyright (c) 2026 PitchAI. All rights reserved.
"""Find the process edges a repository declares: the kit marker, console scripts, routes and a listed set.

An edge is a function decorated with ``@process_edge`` imported from a module
whose file is byte-identical to the kit's ``process_edge_marker.py``. It must
also be a ``[project.scripts]`` target, an HTTP route, or listed in the
manifested ``quality/process-edges.json`` (``{"edges": ["path.py:function"]}``).
"""

from __future__ import annotations

import ast
import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pitchai_quality.source_files import NON_SOURCE_DIRECTORY_NAMES, REPOSITORY_ROOT, iter_python_files

if TYPE_CHECKING:
    from collections.abc import Iterator

type FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef

MARKER_PATH = Path(__file__).with_name("process_edge_marker.py")
CONFIG_PATH = REPOSITORY_ROOT / "quality" / "process-edges.json"
EDGE_KINDS = frozenset({"cli", "worker_loop", "http_boundary", "job", "best_effort"})
MARKER_NAMES = frozenset({"process_edge", "fail_job"})
BROAD_EXCEPTIONS = frozenset({"Exception", "BaseException"})
ROUTE_METHODS = frozenset(
    {"get", "post", "put", "patch", "delete", "head", "options", "route", "api_route", "websocket"},
)
ROUTE_RECEIVER = re.compile(r"(?:^|_)(?:app|router|api|blueprint|bp)$")
LOGGER_RECEIVER = re.compile(r"(?:^|_)(?:log|logger|logging)$")
_SKIPPED_PARTS = frozenset({"quality", *NON_SOURCE_DIRECTORY_NAMES})


@dataclass(frozen=True)
class Edges:
    """Everything a repository declares about its process edges."""

    scripts: frozenset[tuple[str, str]]
    listed: frozenset[str]
    marker_files: frozenset[Path]


def dotted_name(node: ast.expr) -> str:
    """Return the dotted spelling of a name or attribute chain, or an empty string."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def module_name(path: Path) -> str:
    """Return a file's repository-relative dotted path, without a trailing __init__."""
    resolved = path.resolve(strict=False)
    relative = resolved.relative_to(REPOSITORY_ROOT) if resolved.is_relative_to(REPOSITORY_ROOT) else resolved
    return ".".join(relative.with_suffix("").parts).removesuffix(".__init__")


def _script_targets() -> frozenset[tuple[str, str]]:
    targets: set[tuple[str, str]] = set()
    for pyproject in sorted(REPOSITORY_ROOT.rglob("pyproject.toml")):
        if _SKIPPED_PARTS.intersection(pyproject.relative_to(REPOSITORY_ROOT).parts):
            continue
        with pyproject.open("rb") as stream:
            document = cast("dict[str, object]", tomllib.load(stream))
        project = cast("dict[str, object]", document.get("project", {}))
        for target in cast("dict[str, str]", project.get("scripts", {})).values():
            module, _, function = target.partition(":")
            targets.add((module.strip(), function.strip()))
    return frozenset(targets)


def load_edges() -> Edges:
    """Read the declared edges: console scripts, the manifested edge list and the marker copies.

    Returns:
        The repository's edge declarations.
    """
    listed: frozenset[str] = frozenset()
    if CONFIG_PATH.is_file():
        payload = cast("dict[str, list[str]]", json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        listed = frozenset(payload["edges"])
    marker = MARKER_PATH.read_bytes()
    copies: set[Path] = set()
    for path in iter_python_files((REPOSITORY_ROOT,)):
        if path.stat().st_size == len(marker) and path.read_bytes() == marker:
            copies.add(path)
    return Edges(scripts=_script_targets(), listed=listed, marker_files=frozenset(copies))


def _imported_file(node: ast.ImportFrom, path: Path, edges: Edges) -> bool:
    if node.level:
        base = path.parents[node.level - 1]
        target = base.joinpath(*(node.module or "").split("."))
        return target.with_suffix(".py") in edges.marker_files
    module = node.module or ""
    marker_modules = (module_name(marker) for marker in edges.marker_files)
    return any(name == module or name.endswith(f".{module}") for name in marker_modules)


def marker_aliases(tree: ast.Module, path: Path, edges: Edges) -> dict[str, str]:
    """Map local names bound to the kit marker's process_edge and fail_job.

    Returns:
        Local name to marker name, only for imports of a byte-identical marker copy.
    """
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and _imported_file(node, path, edges):
            for alias in node.names:
                if alias.name in MARKER_NAMES:
                    aliases[alias.asname or alias.name] = alias.name
    return aliases


def edge_kind(function: FunctionNode | None, aliases: dict[str, str]) -> str | None:
    """Return the kind a function declares with @process_edge, or None when it is not marked."""
    for decorator in function.decorator_list if function is not None else ():
        if not isinstance(decorator, ast.Call) or aliases.get(dotted_name(decorator.func)) != "process_edge":
            continue
        values = [keyword.value for keyword in decorator.keywords if keyword.arg == "kind"] or decorator.args[:1]
        constant = values[0] if values else None
        return constant.value if isinstance(constant, ast.Constant) and isinstance(constant.value, str) else ""
    return None


def is_route(function: FunctionNode) -> bool:
    """Return whether a function carries an HTTP route decorator such as @router.get(...).

    The decorator must be a call on a route registry (app, router, api, blueprint or bp, or a name ending in one
    of those), so an unrelated @cache.get(...) is not an HTTP edge.
    """
    for decorator in function.decorator_list:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
            continue
        receiver = dotted_name(decorator.func.value).rsplit(".", 1)[-1].lower()
        if decorator.func.attr in ROUTE_METHODS and ROUTE_RECEIVER.search(receiver) is not None:
            return True
    return False


def is_script_target(path: Path, function: FunctionNode, edges: Edges) -> bool:
    """Return whether a top-level function is a [project.scripts] console entry point."""
    module = module_name(path)
    for script_module, script_function in edges.scripts:
        if script_function == function.name and (module == script_module or module.endswith(f".{script_module}")):
            return True
    return False


def is_broad(handler: ast.ExceptHandler) -> bool:
    """Return whether a handler catches Exception, BaseException or everything."""
    if handler.type is None:
        return True
    caught = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(dotted_name(node).rsplit(".", 1)[-1] in BROAD_EXCEPTIONS for node in caught)


def with_enclosing_function[NodeT: ast.AST](
    tree: ast.Module,
    node_type: type[NodeT],
) -> Iterator[tuple[NodeT, FunctionNode | None]]:
    """Yield every node of a type with its innermost enclosing function, or None at module level."""
    pending: list[tuple[ast.AST, FunctionNode | None]] = [(tree, None)]
    while pending:
        node, function = pending.pop()
        if isinstance(node, node_type):
            yield node, function
        inner = node if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) else function
        pending.extend((child, inner) for child in ast.iter_child_nodes(node))
