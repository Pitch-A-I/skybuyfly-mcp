# Copyright (c) 2026 PitchAI. All rights reserved.
"""Allow a broad exception handler only at a declared process edge, and only when it fails loudly.

Every ``except Exception`` / ``except BaseException`` / bare ``except`` outside a
``@process_edge`` function is a finding, repository-wide, unless it is cleanup that
re-raises the caught error on every path and can swallow nothing (process_edge_reraise). Inside one, the handler
must end in a bare ``raise`` or ``raise ... from <error>``; a cli edge may also end
in ``return <non-zero literal>``; any edge may end in ``sys.exit(<non-zero literal>)``
or ``raise SystemExit(<non-zero literal>)``; any edge may end in
``fail_job(logger, <error>, record_failure)`` or ``return fail_job(...)``, which hands
back record_failure's result (optional ``message=``). A handler that exits or returns logs
the exception first (``logger.exception`` or ``exc_info=`` on a logger). It never leaves early:
``fail_job(...)`` followed by ``continue`` is a finding, because the handler must end in ``fail_job``.
A decorator spelled ``process_edge`` that is not imported by name from a byte-identical marker copy is a
finding too: Semgrep's try/except rule exempts ``@process_edge(...)`` by its spelling alone.
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
    EDGE_KINDS,
    LOGGER_RECEIVER,
    dotted_name,
    edge_kind,
    is_broad,
    is_route,
    is_script_target,
    load_edges,
    marker_aliases,
    with_enclosing_function,
)
from pitchai_quality.process_edge_reraise import always_reraises, broad_suppressions

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from pitchai_quality.process_edge_model import Edges, FunctionNode

FAIL_JOB_ARGUMENTS = 3
SUPPRESS_RULE = "contextlib.suppress(Exception) swallows broadly; suppress a concrete error"
ENDING_RULE = (
    "a broad handler at a process edge must end in raise, raise ... from <error>, "
    "a non-zero sys.exit/SystemExit/return literal, or fail_job(logger, <error>, record_failure)"
)
MARKER_ORIGIN_RULE = (
    "@process_edge must be imported by name from a byte-identical copy of the kit's process_edge_marker.py"
)


@dataclass(frozen=True)
class Violation:
    """One broad handler or edge declaration that breaks the process-edge contract."""

    path: Path
    line: int
    reason: str


def _nonzero_literal(node: ast.expr | None) -> bool:
    if not isinstance(node, ast.Constant) or isinstance(node.value, bool):
        return False
    return isinstance(node.value, int) and node.value != 0


def _raise_ending(statement: ast.Raise, error: str | None) -> str | None:
    if statement.exc is None or (isinstance(statement.cause, ast.Name) and statement.cause.id == error):
        return "raise"
    exit_call = statement.exc if isinstance(statement.exc, ast.Call) else None
    if exit_call is None or dotted_name(exit_call.func) != "SystemExit" or not exit_call.args:
        return None
    return "exit" if _nonzero_literal(exit_call.args[0]) else None


def _call_ending(call: ast.Call, error: str | None, aliases: dict[str, str]) -> str | None:
    if dotted_name(call.func) == "sys.exit":
        return "exit" if call.args and _nonzero_literal(call.args[0]) else None
    if aliases.get(dotted_name(call.func)) != "fail_job" or len(call.args) != FAIL_JOB_ARGUMENTS:
        return None
    passed = call.args[1]
    return "fail_job" if isinstance(passed, ast.Name) and passed.id == error else None


def _ending(statement: ast.stmt, error: str | None, aliases: dict[str, str]) -> str | None:
    if isinstance(statement, ast.Raise):
        return _raise_ending(statement, error)
    if isinstance(statement, ast.Return) and isinstance(statement.value, ast.Call):
        # `return fail_job(...)` hands record_failure's result (the failed job's result) back to the loop.
        returned = _call_ending(statement.value, error, aliases)
        return returned if returned == "fail_job" else None
    if isinstance(statement, ast.Return):
        return "return" if _nonzero_literal(statement.value) else None
    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
        return _call_ending(statement.value, error, aliases)
    return None


def _level_reason(statement: ast.stmt, kind: str) -> str | None:
    """Hold fail_job's level= to logging.WARNING at a best_effort edge; every other edge logs at ERROR.

    Returns:
        Why the level is refused, or None when the call keeps the default or is a best_effort WARNING.
    """
    call = statement.value if isinstance(statement, ast.Return | ast.Expr) else None
    if not isinstance(call, ast.Call):
        return None
    level = None
    for keyword in call.keywords:
        if keyword.arg == "level":
            level = keyword.value
    if level is None:
        return None
    if kind != "best_effort":
        return "only a best_effort process edge may pass level= to fail_job"
    if dotted_name(level) != "logging.WARNING":
        return "a best_effort fail_job level must be logging.WARNING"
    return None


def _logs_exception(handler: ast.ExceptHandler) -> bool:
    """Return whether the handler logs the exception through a logger (logger.exception or exc_info=).

    A call such as future.exception() is not logging; the receiver must be named like a logger.
    """
    for node in ast.walk(handler):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        receiver = dotted_name(node.func.value).rsplit(".", 1)[-1].lower()
        if LOGGER_RECEIVER.search(receiver) is None:
            continue
        if node.func.attr == "exception" or any(keyword.arg == "exc_info" for keyword in node.keywords):
            return True
    return False


def _handler_reason(handler: ast.ExceptHandler, kind: str, aliases: dict[str, str]) -> str | None:
    *leading, last = handler.body
    for statement in leading:
        for node in ast.walk(statement):
            if isinstance(node, ast.Return | ast.Break | ast.Continue):
                return "a broad handler at a process edge may not return, break or continue before its ending"
    ending = _ending(last, handler.name, aliases)
    if ending is None:
        return ENDING_RULE
    if ending == "return" and kind != "cli":
        return "only a cli process edge may end a broad handler with return"
    if ending == "fail_job":
        return _level_reason(last, kind)
    if ending in {"exit", "return"} and not _logs_exception(handler):
        return "log the exception (logger.exception or exc_info=) before exiting a process edge"
    return None


def _declaration_reason(path: Path, function: FunctionNode, kind: str, edges: Edges) -> str | None:
    if kind not in EDGE_KINDS:
        return f"@process_edge kind must be one of {', '.join(sorted(EDGE_KINDS))}"
    listed = f"{relative_path(path).as_posix()}:{function.name}" in edges.listed
    if is_route(function) or is_script_target(path, function, edges) or listed:
        return None
    return "@process_edge is only allowed on a [project.scripts] target, an HTTP route or a listed edge"


def _origin_reason(function: FunctionNode, aliases: dict[str, str]) -> str | None:
    for decorator in function.decorator_list:
        spelling = dotted_name(decorator.func if isinstance(decorator, ast.Call) else decorator)
        if spelling.rsplit(".", 1)[-1] == "process_edge" and aliases.get(spelling) != "process_edge":
            return MARKER_ORIGIN_RULE
    return None


def check_file(path: Path, edges: Edges) -> list[Violation]:
    """Return every process-edge finding in one Python file.

    Returns:
        The violations, in source order.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    aliases = marker_aliases(tree, path, edges)
    violations: list[Violation] = []
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        kind = edge_kind(function, aliases)
        reason = _origin_reason(function, aliases) if kind is None else _declaration_reason(path, function, kind, edges)
        if reason is not None:
            violations.append(Violation(path, function.lineno, reason))
    for item in broad_suppressions(tree):
        line = item.context_expr.lineno
        violations.append(Violation(path, line, SUPPRESS_RULE))
    for handler, function in with_enclosing_function(tree, ast.ExceptHandler):
        if not is_broad(handler):
            continue
        kind = edge_kind(function, aliases)
        if kind is None and always_reraises(handler):
            continue
        if kind is None:
            reason = "broad except outside a @process_edge function"
        else:
            reason = _handler_reason(handler, kind, aliases)
        if reason is not None:
            violations.append(Violation(path, handler.lineno, reason))
    return violations


def main(argv: Sequence[str] | None = None) -> int:
    """Run the process-edge checker.

    Returns:
        Zero when every broad handler stands at a declared edge and fails loudly; otherwise one.
    """
    args = checker_parser("Reject broad exception handlers outside declared process edges.").parse_args(
        list(argv) if argv is not None else None,
    )
    edges = load_edges()
    roots = scan_roots(cast("list[str]", args.paths))
    violations = collect_file_violations(roots, lambda path: check_file(path, edges))
    for violation in sorted(violations, key=lambda item: (str(item.path), item.line)):
        write_failure(f"{relative_path(violation.path)}:{violation.line}: {violation.reason}")
    if violations:
        return 1
    write_success("ok process_edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
