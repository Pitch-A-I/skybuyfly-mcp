# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The six tools that render in the results widget (``ui://skybuyfly/results.html``).

Every tool is read-only, idempotent and closed-world (it only queries SkyBuyFly's own catalogue and price
service) and needs no authentication. Each binds the widget the standard way (``_meta.ui.resourceUri``) and the
ChatGPT way (``openai/outputTemplate``); the widget may itself call ``get_product`` and ``get_live_prices``
(``_meta.ui.visibility`` includes ``app``; ChatGPT's ``openai/widgetAccessible``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

import mcp_types

from skybuyfly_mcp import browse, contract, descriptions, inputs, runtime, summaries
from skybuyfly_mcp.resources import WIDGET_URI
from skybuyfly_mcp.search import SearchQuery, search_products

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from mcp.server.apps import Apps
    from pydantic import JsonValue

    from skybuyfly_mcp.services import Services

SearchAnswer = Annotated[mcp_types.CallToolResult, contract.ProductListResult]
ProductAnswer = Annotated[mcp_types.CallToolResult, contract.ProductResult]
LiveAnswer = Annotated[mcp_types.CallToolResult, contract.LiveResult]
HistoryAnswer = Annotated[mcp_types.CallToolResult, contract.HistoryResult]
BarcodeAnswer = Annotated[mcp_types.CallToolResult, contract.BarcodeResult]
FeaturedAnswer = Annotated[mcp_types.CallToolResult, contract.FeaturedResult]
type ToolFunction = Callable[..., Awaitable[mcp_types.CallToolResult]]


@dataclass(frozen=True, slots=True)
class ToolCard:
    """A tool's listing: its name, title, description and ChatGPT's status lines while it runs and after."""

    name: str
    title: str
    description: str
    invoking: str
    invoked: str

    def annotations(self) -> mcp_types.ToolAnnotations:
        """Return the tool's annotations: its title (the directories list it) and the read-only, closed-world hints.

        Returns:
            The annotations every SkyBuyFly tool carries.
        """
        return mcp_types.ToolAnnotations(
            title=self.title,
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        )

    def meta(self, *, widget: bool = False, from_widget: bool = False) -> dict[str, JsonValue]:
        """Return the tool's ``_meta``: public (no auth), its status lines, and its ChatGPT widget binding.

        Returns:
            The ``_meta`` entries (the standard ``ui`` entry is the Apps extension's own).
        """
        meta: dict[str, JsonValue] = {
            "securitySchemes": [{"type": "noauth"}],
            "openai/toolInvocation/invoking": self.invoking,
            "openai/toolInvocation/invoked": self.invoked,
        }
        if widget:
            meta["openai/outputTemplate"] = WIDGET_URI
        if from_widget:
            meta["openai/widgetAccessible"] = True
        return meta


def _ui_tool[F: ToolFunction](apps: Apps, card: ToolCard, *, from_widget: bool = False) -> Callable[[F], F]:
    return apps.tool(
        resource_uri=WIDGET_URI,
        visibility=["model", "app"] if from_widget else None,
        meta=card.meta(widget=True, from_widget=from_widget),
        name=card.name,
        title=card.title,
        description=card.description,
        annotations=card.annotations(),
        structured_output=True,
    )


def register_widget_tools(apps: Apps, services: Services) -> dict[str, ToolFunction]:
    """Register the six widget tools on ``apps`` (before the server is built from it).

    Returns:
        Each tool's function by name (``arguments`` checks their arguments).
    """
    catalogue, runner = services.catalogue, services.runner

    @_ui_tool(
        apps,
        ToolCard(
            "search_products",
            "Search duty-free prices",
            descriptions.SEARCH_PRODUCTS,
            "Searching airport duty-free shops…",
            "Found duty-free prices",
        ),
    )
    async def search(
        query: inputs.Query,
        airports: inputs.Airports = None,
        currency: inputs.Currency = inputs.DEFAULT_CURRENCY,
        limit: inputs.Limit = inputs.DEFAULT_LIMIT,
        cursor: inputs.Cursor = None,
    ) -> SearchAnswer:
        async def work() -> runtime.Rendered:
            result = await search_products(
                catalogue,
                SearchQuery(query, tuple(airports or ()), currency, limit, cursor),
            )
            text = summaries.product_list_summary(
                result.products,
                f"for {query!r}",
                result.notice,
                more=result.next_cursor is not None,
                nothing=f"No products shown for {query!r} in the results read.",
            )
            return runtime.Rendered(result, text)

        return await runner.run("search_products", work, query=query)

    @_ui_tool(
        apps,
        ToolCard(
            "get_product",
            "Get a product's airport prices",
            descriptions.GET_PRODUCT,
            "Loading the product's offers…",
            "Loaded the product's offers",
        ),
        from_widget=True,
    )
    async def get_product(
        product_id: inputs.ProductId,
        currency: inputs.Currency = inputs.DEFAULT_CURRENCY,
    ) -> ProductAnswer:
        async def work() -> runtime.Rendered:
            result = await catalogue.product(product_id, currency)
            return runtime.Rendered(result, summaries.product_summary(result))

        return await runner.run("get_product", work)

    @_ui_tool(
        apps,
        ToolCard(
            "get_live_prices",
            "Check prices live at the airports",
            descriptions.GET_LIVE_PRICES,
            "Checking prices live at the airport shops…",
            "Checked prices live",
        ),
        from_widget=True,
    )
    async def get_live_prices(
        product_id: inputs.ProductId,
        currency: inputs.Currency = inputs.DEFAULT_CURRENCY,
        wait_seconds: inputs.WaitSeconds = inputs.DEFAULT_WAIT_SECONDS,
    ) -> LiveAnswer:
        async def work() -> runtime.Rendered:
            result = await services.live.check(product_id, currency, wait_seconds)
            return runtime.Rendered(result, summaries.live_summary(result))

        return await runner.run("get_live_prices", work)

    @_ui_tool(
        apps,
        ToolCard(
            "get_price_history",
            "Get a product's price history",
            descriptions.GET_PRICE_HISTORY,
            "Loading the price history…",
            "Loaded the price history",
        ),
    )
    async def get_price_history(
        product_id: inputs.ProductId,
        currency: inputs.Currency = inputs.DEFAULT_CURRENCY,
    ) -> HistoryAnswer:
        async def work() -> runtime.Rendered:
            result = await catalogue.history(product_id, currency)
            return runtime.Rendered(result, summaries.history_summary(result))

        return await runner.run("get_price_history", work)

    @_ui_tool(
        apps,
        ToolCard(
            "lookup_barcode",
            "Look up a barcode",
            descriptions.LOOKUP_BARCODE,
            "Looking up the barcode…",
            "Looked up the barcode",
        ),
    )
    async def lookup_barcode(
        code: inputs.Barcode,
        currency: inputs.Currency = inputs.DEFAULT_CURRENCY,
    ) -> BarcodeAnswer:
        async def work() -> runtime.Rendered:
            result = await browse.lookup_barcode(catalogue, code, currency)
            text = summaries.product_list_summary(result.products, f"for barcode {code}", result.notice)
            return runtime.Rendered(result, text)

        return await runner.run("lookup_barcode", work)

    @_ui_tool(
        apps,
        ToolCard(
            "get_featured_products",
            "Featured duty-free products",
            descriptions.GET_FEATURED_PRODUCTS,
            "Loading featured products…",
            "Loaded featured products",
        ),
    )
    async def get_featured_products(
        currency: inputs.Currency = inputs.DEFAULT_CURRENCY,
    ) -> FeaturedAnswer:
        async def work() -> runtime.Rendered:
            result = await browse.featured_products(catalogue, currency)
            return runtime.Rendered(
                result,
                summaries.product_list_summary(result.products, "among the featured products", result.notice),
            )

        return await runner.run("get_featured_products", work)

    return {
        "search_products": search,
        "get_product": get_product,
        "get_live_prices": get_live_prices,
        "get_price_history": get_price_history,
        "lookup_barcode": lookup_barcode,
        "get_featured_products": get_featured_products,
    }
