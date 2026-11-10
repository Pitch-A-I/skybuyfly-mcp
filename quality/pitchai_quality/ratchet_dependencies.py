# Copyright (c) 2026 PitchAI. All rights reserved.
"""Build a conservative import graph without importing application code."""

from __future__ import annotations

import ast
from pathlib import PurePosixPath

type Graph = dict[str, set[str]]


def module_aliases(path: str) -> tuple[str, ...]:
    """Return possible module names across repository and nested source roots.

    Returns:
        All dotted suffixes, including package names for initializers.
    """
    parts = PurePosixPath(path).with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return tuple(".".join(parts[index:]) for index in range(len(parts)))


def _imports(tree: ast.Module, path: str) -> tuple[set[str], bool]:
    names: set[str] = set()
    dynamic = False
    package = list(PurePosixPath(path).parent.parts)
    loaders = {"__import__", "import_module"}
    for statement in ast.walk(tree):
        if isinstance(statement, ast.ImportFrom) and statement.module == "importlib":
            loaders.update(alias.asname or alias.name for alias in statement.names if alias.name == "import_module")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = node.module or ""
            if node.level:
                parent = package[: len(package) - node.level + 1]
                prefix = ".".join([*parent, prefix]).rstrip(".")
            names.add(prefix)
            names.update(f"{prefix}.{alias.name}".lstrip(".") for alias in node.names)
        elif isinstance(node, ast.Call):
            function = node.func
            name = function.id if isinstance(function, ast.Name) else ""
            if isinstance(function, ast.Attribute):
                name = function.attr
            if name in loaders:
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    names.add(node.args[0].value.lstrip("."))
                else:
                    dynamic = True
    return names, dynamic


def dependency_graph(sources: dict[str, str]) -> tuple[Graph, frozenset[str]]:
    """Resolve imports conservatively, retaining ambiguous local modules.

    Returns:
        Dependency edges and modules with unresolved dynamic imports.
    """
    aliases: dict[str, set[str]] = {}
    for path in sources:
        for name in module_aliases(path):
            aliases.setdefault(name, set()).add(path)
    graph: Graph = {path: set() for path in sources}
    dynamic: set[str] = set()
    for path, source in sources.items():
        for suffix in (".py", ".pyi"):
            companion = str(PurePosixPath(path).with_suffix(suffix))
            if companion in sources:
                graph[path].add(companion)
        names, unresolved = _imports(ast.parse(source, filename=path), path)
        if unresolved:
            dynamic.add(path)
        for name in names:
            for length in range(1, len(name.split(".")) + 1):
                graph[path].update(aliases.get(".".join(name.split(".")[:length]), ()))
        for parent in PurePosixPath(path).parents:
            for filename in ("__init__.py", "__init__.pyi", "conftest.py"):
                candidate = str(parent / filename)
                if candidate in sources and candidate != path:
                    graph[path].add(candidate)
    return graph, frozenset(dynamic)


def reachable(graph: Graph, seeds: frozenset[str]) -> frozenset[str]:
    """Follow transitive edges, including cycles, exactly once.

    Returns:
        Seed paths and every reachable dependency.
    """
    found = set(seeds)
    pending = list(seeds)
    while pending:
        for path in graph.get(pending.pop(), ()):
            if path not in found:
                found.add(path)
                pending.append(path)
    return frozenset(found)


def dependency_closure(sources: dict[str, str], previous: dict[str, str], changed: frozenset[str]) -> frozenset[str]:
    """Follow affected importers, then their dependencies, in both revisions.

    Returns:
        Current files affected by the change, without unrelated consumers of a dependency.
    """
    old = {**sources, **previous}
    graph, dynamic = dependency_graph(old)
    current, current_dynamic = dependency_graph(sources)
    for path, edges in current.items():
        graph.setdefault(path, set()).update(edges)
    reverse: Graph = {}
    for importer, dependencies in graph.items():
        for dependency in dependencies:
            reverse.setdefault(dependency, set()).add(importer)
    # Runtime-computed imports have no statically resolvable target. Include all
    # such consumers and their importers whenever Python changes, then analyze
    # their statically resolvable dependencies too. Never execute plugin loaders.
    affected = reachable(reverse, changed | dynamic | current_dynamic)
    return reachable(graph, affected) & sources.keys()
