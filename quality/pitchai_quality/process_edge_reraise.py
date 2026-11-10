# Copyright (c) 2026 PitchAI. All rights reserved.
"""Decide whether a broad handler can never swallow: cleanup that always re-raises.

A broad handler outside a process edge is accepted only when (1) every path through
it ends in a bare ``raise`` or ``raise X from <the caught error>``, with no
conditional raise that another path falls past; (2) it contains no return, break,
continue or yield, and no nested try whose handler can swallow;
and (3) the raise is never inside a loop, since a loop can exit normally.
"""

from __future__ import annotations

import ast

ESCAPES = (ast.Return, ast.Break, ast.Continue, ast.Yield, ast.YieldFrom)
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _own_nodes(statements: list[ast.stmt]) -> list[ast.AST]:
    """Return every node under the statements, without entering nested functions, lambdas or classes.

    Returns:
        The nodes, in no particular order.
    """
    pending: list[ast.AST] = list(statements)
    found: list[ast.AST] = []
    while pending:
        node = pending.pop()
        found.append(node)
        if not isinstance(node, SCOPES):
            pending.extend(ast.iter_child_nodes(node))
    return found


def _reraises(statement: ast.Raise, error: str | None) -> bool:
    if statement.exc is None:
        return True
    return isinstance(statement.cause, ast.Name) and statement.cause.id == error


def _terminates(statements: list[ast.stmt], error: str | None) -> bool:
    """Return whether every path through the statements ends in a re-raise of the caught error.

    A raise inside a with block never counts: the context manager (contextlib.suppress, for one) may swallow it.

    Returns:
        True when some statement in the block re-raises on every path through it.
    """
    for statement in statements:
        if isinstance(statement, ast.Raise) and _reraises(statement, error):
            return True
        branches = (statement.body, statement.orelse) if isinstance(statement, ast.If) else ()
        if branches and all(_terminates(branch, error) for branch in branches):
            return True
    return False


def _swallowing_try(node: ast.AST, error: str | None) -> bool:
    if not isinstance(node, ast.Try | ast.TryStar):
        return False
    return any(not _terminates(handler.body, handler.name or error) for handler in node.handlers)


def always_reraises(handler: ast.ExceptHandler) -> bool:
    """Return whether a broad handler re-raises the caught error on every path and can swallow nothing.

    Returns:
        True only for cleanup-and-re-raise handlers that meet all three conditions.
    """
    nodes = _own_nodes(handler.body)
    if any(isinstance(node, ESCAPES) for node in nodes):
        return False
    if any(_swallowing_try(node, handler.name) for node in nodes):
        return False
    for loop in nodes:
        if not isinstance(loop, ast.For | ast.AsyncFor | ast.While):
            continue
        inside = _own_nodes(loop.body + loop.orelse)
        if any(isinstance(inner, ast.Raise) for inner in inside):
            return False
    return _terminates(handler.body, handler.name)


def broad_suppressions(tree: ast.Module) -> list[ast.withitem]:
    """Return every contextlib.suppress(...) item that suppresses Exception or BaseException.

    Returns:
        The with-items, each a broad swallow that no except handler shows.
    """
    found: list[ast.withitem] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.With | ast.AsyncWith):
            continue
        for item in node.items:
            call = item.context_expr
            if not isinstance(call, ast.Call) or not _named(call.func, "suppress"):
                continue
            if any(_named(argument, name) for argument in call.args for name in ("Exception", "BaseException")):
                found.append(item)
    return found


def _named(node: ast.expr, name: str) -> bool:
    if isinstance(node, ast.Name):
        return node.id == name
    return isinstance(node, ast.Attribute) and node.attr == name
