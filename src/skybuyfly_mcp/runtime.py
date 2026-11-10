# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The tool call edge: call limits, the access log line and the counters around every tool, and its result form.

Each call is admitted against the per-client and global budgets first (``limits.CallGate``), then runs; its
``structuredContent`` is the contract document and its text the summary for the model. A tool error (an
anticipated ``ToolError``) is counted by its kind and re-raised for the SDK to answer with ``isError``; anything
else is counted as ``crash`` (the SDK logs its traceback and answers a generic error).

The access log has one line per call: tool, outcome, duration, the API's statuses and the client's family. It never
holds a client address (nginx logs those) and holds at most 200 characters of a query.
"""

from __future__ import annotations

import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self

from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, TextContent

from skybuyfly_mcp.contract import LiveResult
from skybuyfly_mcp.metrics import client_family
from skybuyfly_mcp.upstream import UPSTREAM_STATUSES

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from contextvars import Token
    from types import TracebackType

    from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
    from pydantic import JsonValue
    from starlette.requests import Request

    from skybuyfly_mcp.contract import Contract
    from skybuyfly_mcp.limits import CallGate
    from skybuyfly_mcp.metrics import Metrics

logger = logging.getLogger("skybuyfly_mcp.access")
_LOGGED_QUERY_CHARACTERS = 200


@dataclass(frozen=True, slots=True)
class RequestClient:
    """Who sent the MCP request: nginx's ``X-Real-IP`` (``direct`` without nginx) and the User-Agent."""

    address: str
    user_agent: str | None


DIRECT = RequestClient("direct", None)
"""The client of a call that did not come over HTTP (in-process), or of a request without ``X-Real-IP``."""
REQUEST_CLIENT: ContextVar[RequestClient | None] = ContextVar("REQUEST_CLIENT", default=None)
"""The client of the MCP request being handled (set by ``remember_client``)."""


async def remember_client(
    ctx: ServerRequestContext[dict[str, JsonValue], Request],
    call_next: CallNext,
) -> HandlerResult:
    """Server middleware: note the HTTP client of every MCP message for the tool call it may run.

    Returns:
        The rest of the chain's result, unchanged.
    """
    request = ctx.request
    client = DIRECT
    if request is not None:
        address = (request.headers.get("x-real-ip") or "").strip() or DIRECT.address
        client = RequestClient(address, request.headers.get("user-agent"))
    token = REQUEST_CLIENT.set(client)
    try:
        return await call_next(ctx)
    finally:
        REQUEST_CLIENT.reset(token)


@dataclass(frozen=True, slots=True)
class AccessLine:
    """One tool call's access log line: tool, outcome, duration, the API's statuses, the client's family, the query."""

    tool: str
    outcome: str
    duration_ms: int
    statuses: list[int]
    family: str
    query: str | None = None

    def write(self) -> None:
        """Log the line (at most 200 characters of the query, never a client address)."""
        shown = "" if self.query is None else f" query={self.query[:_LOGGED_QUERY_CHARACTERS]!r}"
        upstream = ",".join(str(status) for status in self.statuses) or "-"
        logger.info(
            "event=tool_call tool=%s outcome=%s duration_ms=%d upstream_status=%s client=%s%s",
            self.tool,
            self.outcome,
            self.duration_ms,
            upstream,
            self.family,
            shown,
        )


@dataclass(frozen=True, slots=True)
class Rendered:
    """A tool's answer: its contract document and the text for the model."""

    result: Contract
    text: str


@dataclass(slots=True)
class _Call:
    """One tool call being recorded: the API statuses it saw, its outcome, its counters and access log line."""

    tool: str
    family: str
    query: str | None
    metrics: Metrics
    statuses: list[int] = field(default_factory=list[int])
    started: float = field(default_factory=time.monotonic)
    token: Token[list[int] | None] | None = None

    def __enter__(self) -> Self:
        """Start collecting the API statuses of this call.

        Returns:
            The call.
        """
        self.token = UPSTREAM_STATUSES.set(self.statuses)
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        """Count the call by its outcome (``ok``, the tool error's kind, or ``crash``) and log it; never suppress."""
        if self.token is not None:
            UPSTREAM_STATUSES.reset(self.token)
        outcome = "ok" if kind is None else kind.__name__ if issubclass(kind, ToolError) else "crash"
        self.metrics.record(self.tool, outcome, self.family, self.statuses)
        duration_ms = round((time.monotonic() - self.started) * 1000)
        AccessLine(self.tool, outcome, duration_ms, self.statuses, self.family, self.query).write()


@dataclass(frozen=True, slots=True)
class ToolRunner:
    """Runs every tool call inside the call limits, the access log and the counters."""

    calls: CallGate
    metrics: Metrics

    async def run(
        self,
        tool: str,
        work: Callable[[], Awaitable[Rendered]],
        *,
        query: str | None = None,
    ) -> CallToolResult:
        """Admit, run and record one tool call (a refusal or failure propagates after it is counted).

        Returns:
            The result with ``structuredContent`` and its summary text.
        """
        client = REQUEST_CLIENT.get() or DIRECT
        with _Call(tool, client_family(client.user_agent), query, self.metrics):
            self.calls.admit(client.address)
            rendered = await work()
        if isinstance(rendered.result, LiveResult):
            self.metrics.record_live(rendered.result.live_status)
        return CallToolResult(
            content=[TextContent(type="text", text=rendered.text)],
            structured_content=rendered.result.model_dump(mode="json"),
        )
