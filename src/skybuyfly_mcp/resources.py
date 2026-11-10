# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The one MCP Apps UI resource: the results widget (product cards, per-airport offer table, live badges).

It is served as ``text/html;profile=mcp-app`` from the package's ``widget/results.html``, read on every
``resources/read`` (a missing file is an error, never an empty widget). Its ``_meta.ui`` declares the standard
sandbox policy (images and other resources only from SkyBuyFly and ``assets.pitchai.net``, no network calls:
the widget gets its data from the tool result); the ``openai/*`` keys say the same for ChatGPT. ``_meta.ui.domain``
is left out: Claude only accepts its own sandbox domain there.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.apps import APP_MIME_TYPE, ResourceCsp
from mcp.server.mcpserver.resources.types import FileResource

from skybuyfly_mcp.links import ASSETS_ORIGIN

WIDGET_URI = "ui://skybuyfly/results.html"
WIDGET_PATH = Path(__file__).resolve().parent / "widget" / "results.html"
_DESCRIPTION = (
    "SkyBuyFly price comparison results: product cards with their price at each airport duty-free shop, the "
    "per-airport offer table with live-confirmed and stored prices, and links to SkyBuyFly."
)


def widget_resource(public_base_url: str) -> FileResource:
    """Return the widget resource with its sandbox policy for ``public_base_url`` (``https://skybuyfly.pitchai.net``).

    Returns:
        The ``ui://skybuyfly/results.html`` resource.
    """
    resource_domains = [public_base_url, ASSETS_ORIGIN]
    csp = ResourceCsp(connect_domains=[], resource_domains=resource_domains)
    return FileResource(
        uri=WIDGET_URI,
        name="skybuyfly-results",
        title="SkyBuyFly results",
        description=_DESCRIPTION,
        mime_type=APP_MIME_TYPE,
        path=WIDGET_PATH,
        meta={
            "ui": {"csp": csp.model_dump(by_alias=True, exclude_none=True), "prefersBorder": True},
            "openai/widgetCSP": {
                "connect_domains": [],
                "resource_domains": resource_domains,
                "redirect_domains": [public_base_url],
            },
            "openai/widgetDomain": public_base_url,
            "openai/widgetDescription": _DESCRIPTION,
            "openai/widgetPrefersBorder": True,
        },
    )
