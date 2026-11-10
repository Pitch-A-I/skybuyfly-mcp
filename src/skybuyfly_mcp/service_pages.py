# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The service pages of the MCP container and the CORS policy of every route.

``GET /mcp/docs``, ``/mcp/privacy``, ``/mcp/terms``, ``/mcp/support``
    The package's ``pages/*.html`` (``text/html; charset=utf-8``, cacheable for an hour). Each file is read once
    when the application is built: a missing page stops the start instead of serving an empty one.

CORS: the server is public, read-only, needs no sign-in and sets no cookie, so a browser ``Origin`` is no security
boundary here. Every origin may call it (Claude's ``*.claudemcpcontent.com`` frames, ``chatgpt.com``, ChatGPT's
``*.oaiusercontent.com``, the MCP Inspector on ``http://localhost:*``, editor webviews) without credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse
from starlette.routing import Route

if TYPE_CHECKING:
    from starlette.types import Receive, Scope, Send

PAGES_DIR = Path(__file__).resolve().parent / "pages"
PAGES = {"docs": "docs.html", "privacy": "privacy.html", "terms": "terms.html", "support": "support.html"}
"""``/mcp/<name>`` -> the page file."""
PAGE_HEADERS = {"Cache-Control": "public, max-age=3600"}
CORS_METHODS = ("GET", "POST", "OPTIONS", "DELETE")
CORS_HEADERS = ("authorization", "mcp-protocol-version", "mcp-session-id", "last-event-id")
"""Allowed request headers besides the CORS-safelisted ones (``Accept``, ``Content-Type`` and the two language
headers), which ``CORSMiddleware`` always allows."""
CORS_EXPOSED = ("mcp-session-id",)
CORS_MAX_AGE_SECONDS = 86400


def cors() -> Middleware:
    """Return the CORS middleware: any origin, no credentials, the MCP headers, preflights cached for a day.

    Returns:
        The middleware entry of the application.
    """
    return Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=list(CORS_METHODS),
        allow_headers=list(CORS_HEADERS),
        allow_credentials=False,
        expose_headers=list(CORS_EXPOSED),
        max_age=CORS_MAX_AGE_SECONDS,
    )


@dataclass(frozen=True, slots=True)
class _Page:
    """One service page: its HTML, answered as is."""

    html: str

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Send the page."""
        await HTMLResponse(self.html, headers=PAGE_HEADERS)(scope, receive, send)


def page_routes() -> list[Route]:
    """Read every service page and return its ``GET /mcp/<name>`` route.

    Returns:
        The routes.
    """
    return [
        Route(f"/mcp/{name}", _Page((PAGES_DIR / file).read_text(encoding="utf-8")), methods=["GET"])
        for name, file in PAGES.items()
    ]
