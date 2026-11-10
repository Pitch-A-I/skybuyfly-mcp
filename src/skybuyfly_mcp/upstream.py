# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The one HTTP client of the public SkyBuyFly API, and the edge where its failures become typed tool errors.

Every request carries the MCP's own User-Agent (``Settings.user_agent``: never a crawler's, which the live API
refuses) and ``DNT: 1`` (the web app records no analytics for a Do-Not-Track request, so MCP traffic never reaches
the site's analytics), and times out after 5 s connecting and 10 s between reads. A merged duplicate product answers a
redirect to the product it was merged into, which is followed. Nothing is retried and no other route is tried:
a failure reaches the model as a tool error naming the route and the cause.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import TYPE_CHECKING, Literal

import anyio
import httpx
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, ValidationError

from skybuyfly_mcp.sse import SseParser
from skybuyfly_mcp.upstream_models import ErrorBody

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from skybuyfly_mcp.sse import SseEvent

TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0)
StreamEnd = Literal["finished", "deadline", "closed"]
"""``finished``: the sink saw its last event; ``deadline``: the wait ran out; ``closed``: the stream ended first."""
UPSTREAM_STATUSES: ContextVar[list[int] | None] = ContextVar("UPSTREAM_STATUSES", default=None)
"""The statuses the API answered during the current tool call (for its access log line), when one is recorded."""


class UpstreamError(ToolError):
    """The API answered a status the tool cannot use."""

    def __init__(self, route: str, status: int, error: ErrorBody | None) -> None:
        """Name the route, the status and the API's own error code."""
        self.route: str = route
        self.status: int = status
        code = None if error is None else error.error_code or error.error
        detail = f" ({code})" if code else ""
        retry = " Please try again later." if status >= HTTPStatus.TOO_MANY_REQUESTS else ""
        super().__init__(f"The SkyBuyFly API answered {status}{detail} for {route}.{retry}")


class UpstreamUnavailableError(ToolError):
    """The API could not be reached or did not answer in time."""

    def __init__(self, route: str, cause: httpx.HTTPError) -> None:
        """Name the route and the transport failure."""
        super().__init__(f"The SkyBuyFly API is unreachable for {route} ({type(cause).__name__}); try again later.")


class UpstreamContractError(ToolError):
    """The API answered a document the tools do not understand (its contract changed)."""

    def __init__(self, route: str, error: ValidationError) -> None:
        """Name the route and the first field that did not validate."""
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        super().__init__(f"The SkyBuyFly API answered an unexpected document for {route} (field {where!r}).")


def parse_body[M: BaseModel](route: str, body: bytes | str, model: type[M]) -> M:
    """Validate an API document.

    Returns:
        The validated document.

    Raises:
        UpstreamContractError: The document does not match ``model``.
    """
    try:
        return model.model_validate_json(body)
    except ValidationError as error:
        raise UpstreamContractError(route, error) from error


@dataclass(frozen=True, slots=True)
class UpstreamAnswer:
    """One answered request: its route label (``/api/mobile/product/{id}``), status and raw body."""

    route: str
    status: int
    body: bytes

    def parsed[M: BaseModel](self, model: type[M]) -> M:
        """Validate the body as ``model``.

        Returns:
            The validated document.
        """
        return parse_body(self.route, self.body, model)


@dataclass(frozen=True, slots=True)
class StreamRefused:
    """A live stream request the API answered with a JSON error instead of events."""

    status: int
    error: ErrorBody


@dataclass(frozen=True, slots=True)
class ApiRequest:
    """One read of the public API: its route label (``/api/mobile/product/<id>``), path, query and headers."""

    route: str
    path: str
    params: Mapping[str, str] = field(default_factory=dict[str, str])
    headers: Mapping[str, str] = field(default_factory=dict[str, str])
    expected: frozenset[int] = frozenset({HTTPStatus.OK})
    """The statuses the caller handles; any other is an ``UpstreamError``."""


def _record(status: int) -> None:
    statuses = UPSTREAM_STATUSES.get()
    if statuses is not None:
        statuses.append(status)


def _error_body(route: str, response: httpx.Response) -> ErrorBody | None:
    """Read an unexpected answer's error document: the API answers JSON; a proxy's error page is no document.

    Returns:
        The API's error document, or ``None`` for a non-JSON answer.
    """
    headers = response.headers
    if "content-type" not in headers or not headers["content-type"].startswith("application/json"):
        return None
    return parse_body(route, response.content, ErrorBody)


class UpstreamClient:
    """The process's one connection pool to the public API."""

    def __init__(self, base_url: str, user_agent: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        """Open the pool (``transport`` replaces the network in tests)."""
        self._client: httpx.AsyncClient = httpx.AsyncClient(
            base_url=base_url,
            headers={"User-Agent": user_agent, "Accept": "application/json", "DNT": "1"},
            timeout=TIMEOUT,
            follow_redirects=True,
            transport=transport,
        )

    async def aclose(self) -> None:
        """Close the pool."""
        await self._client.aclose()

    async def get(self, request: ApiRequest) -> UpstreamAnswer:
        """Send ``request`` and require one of its expected statuses.

        Returns:
            The answer (its status is one of ``request.expected``).

        Raises:
            UpstreamUnavailableError: The request failed or timed out.
            UpstreamError: The status is not expected.
        """
        try:
            response = await self._client.get(request.path, params=request.params, headers=request.headers)
        except httpx.HTTPError as error:
            raise UpstreamUnavailableError(request.route, error) from error
        _record(response.status_code)
        if response.status_code not in request.expected:
            raise UpstreamError(request.route, response.status_code, _error_body(request.route, response))
        return UpstreamAnswer(request.route, response.status_code, response.content)

    async def stream_events(
        self,
        request: ApiRequest,
        deadline_seconds: float,
        sink: Callable[[SseEvent], bool],
    ) -> StreamEnd | StreamRefused:
        """Read a Server-Sent Events stream into ``sink`` until it returns ``True`` or ``deadline_seconds`` pass.

        A refusal's body must be a JSON error document (``UpstreamContractError`` otherwise).

        Returns:
            How the reading ended, or the API's refusal (any status but 200).

        Raises:
            UpstreamUnavailableError: The request failed or a read timed out.
        """
        try:
            return await self._stream(request, deadline_seconds, sink)
        except httpx.HTTPError as error:
            raise UpstreamUnavailableError(request.route, error) from error

    async def _stream(
        self,
        request: ApiRequest,
        deadline_seconds: float,
        sink: Callable[[SseEvent], bool],
    ) -> StreamEnd | StreamRefused:
        headers = {**request.headers, "Accept": "text/event-stream"}
        with anyio.move_on_after(deadline_seconds):
            async with self._client.stream("GET", request.path, params=request.params, headers=headers) as response:
                return await _drain(request.route, response, sink)
        return "deadline"


async def _drain(route: str, response: httpx.Response, sink: Callable[[SseEvent], bool]) -> StreamEnd | StreamRefused:
    """Feed an open stream's events to ``sink``.

    Returns:
        ``finished`` once the sink has its last event, ``closed`` when the stream ends first, or the refusal.
    """
    _record(response.status_code)
    if response.status_code != HTTPStatus.OK:
        return StreamRefused(response.status_code, parse_body(route, await response.aread(), ErrorBody))
    parser = SseParser()
    async for line in response.aiter_lines():
        event = parser.feed(line)
        if event is not None and sink(event):
            return "finished"
    return "closed"
