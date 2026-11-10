# Copyright (c) 2026 PitchAI. All rights reserved.
"""Fail when runtime code creates nested asyncio event loops.

The one sanctioned loop is a single ``asyncio.run`` directly owned by a console
entry point: a ``@process_edge(kind="cli")`` function or a ``[project.scripts]``
target. Every other loop construction is a finding.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from pitchai_quality.analysis_support import (
    checker_parser,
    collect_file_violations,
    relative_path,
    scan_roots,
    write_failure,
    write_success,
)
from pitchai_quality.process_edge_model import (
    edge_kind,
    is_script_target,
    load_edges,
    marker_aliases,
    with_enclosing_function,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from pitchai_quality.process_edge_model import Edges, FunctionNode


@dataclass(frozen=True)
class Violation:
    """One forbidden event-loop construction call."""

    path: Path
    line: int
    expression: str


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _entry_point(path: Path, function: FunctionNode | None, aliases: dict[str, str], edges: Edges) -> bool:
    if function is None:
        return False
    return edge_kind(function, aliases) == "cli" or is_script_target(path, function, edges)


def check_file(path: Path, edges: Edges) -> list[Violation]:
    """Return every forbidden event-loop construction in one Python file.

    Returns:
        The violations, in source order.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    aliases = marker_aliases(tree, path, edges)
    owners: set[int] = set()
    violations: list[Violation] = []
    for node, function in sorted(with_enclosing_function(tree, ast.Call), key=lambda item: item[0].lineno):
        expression = _call_name(node.func)
        forbidden_creation = expression in {
            "asyncio.run",
            "asyncio.new_event_loop",
            "asyncio.get_event_loop",
            "asyncio.get_event_loop_policy",
        }
        sanctioned = expression == "asyncio.run" and _entry_point(path, function, aliases, edges)
        if sanctioned and id(function) not in owners:
            owners.add(id(function))
            continue
        if forbidden_creation or expression.endswith(".run_until_complete"):
            violations.append(Violation(path, node.lineno, expression))
    return violations


def main(argv: Sequence[str] | None = None) -> int:
    """Run the nested-event-loop checker.

    Returns:
        Zero when no violations exist; otherwise one.
    """
    args = checker_parser("Reject nested event-loop construction.").parse_args(list(argv) if argv is not None else None)
    raw_paths = cast("list[str]", args.paths)
    edges = load_edges()
    violations = collect_file_violations(scan_roots(raw_paths), lambda path: check_file(path, edges))

    if violations:
        for violation in violations:
            write_failure(
                f"{relative_path(violation.path)}:{violation.line}: "
                f"nested event-loop creation is forbidden: {violation.expression}",
            )
        return 1

    write_success("ok nested_event_loops")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
