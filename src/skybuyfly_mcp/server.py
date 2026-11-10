# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The ASGI application: the MCP endpoint and the service routes of the MCP container.

``POST/GET /mcp``
    MCP over Streamable HTTP, stateless with JSON responses (no sessions: any instance answers any request).
``GET /mcp/health``
    ``{"service": "skybuyfly-mcp", "status": "ok", "version": ..., "revision": ...}`` (``revision``: the deployed git
    commit, ``null`` for a local run).
``GET /mcp/metrics``
    Aggregate counters (``metrics.MetricsDocument``): no address, no query, no identifier.
``GET /.well-known/openai-apps-challenge`` / ``GET /.well-known/mcp-registry-auth``
    The directory verification token and registry auth record as plain text; 404 while not configured.
``GET /mcp/docs``, ``/mcp/privacy``, ``/mcp/terms``, ``/mcp/support``
    The service pages (``service_pages``).

Every origin may call every route (CORS, ``service_pages.cors``). There is no ``Host`` or ``Origin`` check: the
server is public, needs no sign-in, sets no cookie and holds no state, every link it answers is built from
``Settings.public_base_url`` (never from ``Host``), so a DNS-rebinding page could do nothing a direct request
cannot.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mcp.server.apps import Apps
from mcp.server.mcpserver import Icon, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route

from skybuyfly_mcp.arguments import ArgumentCheck, ToolArguments
from skybuyfly_mcp.descriptions import INSTRUCTIONS
from skybuyfly_mcp.live import utc_now
from skybuyfly_mcp.resources import widget_resource
from skybuyfly_mcp.runtime import remember_client
from skybuyfly_mcp.service_pages import cors, page_routes
from skybuyfly_mcp.services import Services
from skybuyfly_mcp.tools import register_widget_tools
from skybuyfly_mcp.tools_reference import register_reference_tools

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable
    from datetime import datetime

    import httpx
    from starlette.responses import Response
    from starlette.types import Receive, Scope, Send

    from skybuyfly_mcp.config import Settings

ICON_PATH = "/static/icons/icon-512.png"
_NO_STORE = {"Cache-Control": "no-store"}
_OPEN_TRANSPORT = TransportSecuritySettings(enable_dns_rebinding_protection=False)
"""The SDK's Host/Origin allow-lists are off (see the module docstring); its POST Content-Type check stays."""


def build_server(services: Services) -> MCPServer:
    """Build the MCP server: nine tools, the widget resource, the instructions for the model and the middleware.

    The middleware notes each request's client (``runtime.remember_client``), then checks every tool call's arguments
    (``arguments.ArgumentCheck``).

    Returns:
        The server.
    """
    public = services.settings.public_base_url
    apps = Apps()
    functions = register_widget_tools(apps, services)
    apps.add_resource(widget_resource(public))
    server = MCPServer(
        "skybuyfly",
        title="SkyBuyFly",
        description="Airport duty-free price comparison: prices per airport shop, confirmed live on request.",
        instructions=INSTRUCTIONS,
        website_url=public,
        icons=[Icon(src=f"{public}{ICON_PATH}", mime_type="image/png", sizes=["512x512"])],
        version=services.settings.version,
        extensions=[apps],
        middleware=[remember_client],
    )
    functions |= register_reference_tools(server, services)
    registered = functions.items()
    checks = {name: ToolArguments.of(function) for name, function in registered}
    server.middleware.append(ArgumentCheck(checks, services.metrics))
    return server


def _text_or_404(value: str | None) -> PlainTextResponse:
    if value is None:
        return PlainTextResponse("Not configured\n", status_code=404)
    return PlainTextResponse(value)


@dataclass(frozen=True, slots=True)
class _Answer:
    """A service route: an ASGI app answering the document ``answer`` builds at request time."""

    answer: Callable[[], Response]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Send the current answer."""
        await self.answer()(scope, receive, send)


def build_app(
    settings: Settings,
    transport: httpx.AsyncBaseTransport | None = None,
    wall_clock: Callable[[], datetime] = utc_now,
) -> Starlette:
    """Build the ASGI application.

    ``transport`` replaces the network to the API in tests; ``wall_clock`` the time live checks are stamped with
    (the widget harness stamps the recorded run's end).

    Returns:
        The Starlette application.
    """
    services = Services.build(settings, transport, wall_clock=wall_clock)
    server = build_server(services)
    mcp_app = server.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        transport_security=_OPEN_TRANSPORT,
    )

    health = {"service": "skybuyfly-mcp", "status": "ok", "version": settings.version, "revision": settings.revision}

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncGenerator[None]:
        async with server.session_manager.run():
            yield
        await services.upstream.aclose()

    routes = [
        *mcp_app.routes,
        Route("/mcp/health", _Answer(lambda: JSONResponse(health)), methods=["GET"]),
        Route(
            "/mcp/metrics",
            _Answer(lambda: JSONResponse(services.metrics.document().model_dump(), headers=_NO_STORE)),
            methods=["GET"],
        ),
        Route(
            "/.well-known/openai-apps-challenge",
            _Answer(lambda: _text_or_404(settings.published.openai_challenge_token)),
            methods=["GET"],
        ),
        Route(
            "/.well-known/mcp-registry-auth",
            _Answer(lambda: _text_or_404(settings.published.registry_auth)),
            methods=["GET"],
        ),
        *page_routes(),
    ]
    return Starlette(routes=routes, middleware=[cors()], lifespan=lifespan)
