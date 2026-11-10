# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The catalogue's upstream calls: reference data, products and price history, cached, validated and shaped.

``search_products`` pages through the catalogue in ``search``; barcode, featured products and statistics are in
``browse``.

Every price is requested in the tool's display currency (``X-Display-Currency``, ``?currency=``,
``?currency_code=``), validated first against ``/api/mobile/currencies`` (the snapshots route would silently
answer USD for an unknown one).
"""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING

from mcp.server.mcpserver.exceptions import ToolError

from skybuyfly_mcp import upstream_models as api
from skybuyfly_mcp.contract import ProductResult
from skybuyfly_mcp.history import price_history
from skybuyfly_mcp.reference import AirportDirectory, CurrencyBook
from skybuyfly_mcp.retailers import ShopNames
from skybuyfly_mcp.screen import require_admitted, screened
from skybuyfly_mcp.shaping import CardFacts, Shaper, listed_offers, offer_order
from skybuyfly_mcp.upstream import ApiRequest

if TYPE_CHECKING:
    from skybuyfly_mcp import upstream_browse as browse_api
    from skybuyfly_mcp.cache import TtlCache
    from skybuyfly_mcp.contract import HistoryResult
    from skybuyfly_mcp.links import Links
    from skybuyfly_mcp.upstream import UpstreamClient

_FOUND_OR_NOT: frozenset[int] = frozenset({HTTPStatus.OK, HTTPStatus.NOT_FOUND})
HISTORY_SNAPSHOTS = 50
"""The snapshots route's cap (``limit`` at most 50, newest first; no older-page, date or de-duplication parameter):
the 50 most recent observations across every airport."""


class ProductNotFoundError(ToolError):
    """No catalogue product has the id."""

    def __init__(self, product_id: str) -> None:
        """Name the id."""
        super().__init__(f"No SkyBuyFly product has the id {product_id}; find products with search_products first.")


@dataclass(frozen=True, slots=True)
class Caches:
    """One cache per kind of product answer."""

    search: TtlCache[api.SearchResponse]
    product: TtlCache[api.ProductDetailResponse | None]
    history: TtlCache[api.HistoryResponse]
    barcode: TtlCache[browse_api.BarcodeResponse | None]


@dataclass(frozen=True, slots=True)
class ReferenceCaches:
    """One cache per kind of reference answer (airports, currencies, home screen, catalogue status)."""

    airports: TtlCache[AirportDirectory]
    currencies: TtlCache[CurrencyBook]
    home: TtlCache[browse_api.HomeResponse]
    stats: TtlCache[browse_api.StatusResponse]


@dataclass(frozen=True, slots=True)
class Catalogue:
    """The read-only public API behind the catalogue tools."""

    upstream: UpstreamClient
    links: Links
    caches: Caches
    reference: ReferenceCaches

    async def airports(self) -> AirportDirectory:
        """Return every compared airport (``/api/mobile/airports``).

        Returns:
            The airport directory.
        """

        async def load() -> AirportDirectory:
            answer = await self.upstream.get(ApiRequest("/api/mobile/airports", "/api/mobile/airports"))
            return AirportDirectory.from_response(answer.parsed(api.AirportsResponse))

        return await self.reference.airports.get_or_load("airports", load)

    async def currencies(self) -> CurrencyBook:
        """Return every display currency (``/api/mobile/currencies``).

        Returns:
            The currency book.
        """

        async def load() -> CurrencyBook:
            answer = await self.upstream.get(ApiRequest("/api/mobile/currencies", "/api/mobile/currencies"))
            return CurrencyBook.from_response(answer.parsed(api.CurrenciesResponse))

        return await self.reference.currencies.get_or_load("currencies", load)

    async def shaper(self, currency: str) -> Shaper:
        """Return the shaper of a validated display currency (``UnsupportedCurrencyError`` otherwise).

        Returns:
            The shaper for ``currency``.
        """
        book = await self.currencies()
        return Shaper(self.links, book.require(currency))

    async def product_document(self, product_id: str, currency: str) -> api.ProductDetailResponse:
        """Return a product's detail document (``/api/mobile/product/{id}``) when it may be shown.

        Returns:
            The document.

        Raises:
            ProductNotFoundError: No product has the id.
        """
        path = f"/api/mobile/product/{product_id}"
        request = ApiRequest("/api/mobile/product/<id>", path, {}, {"X-Display-Currency": currency}, _FOUND_OR_NOT)

        async def load() -> api.ProductDetailResponse | None:
            answer = await self.upstream.get(request)
            return None if answer.status == HTTPStatus.NOT_FOUND else answer.parsed(api.ProductDetailResponse)

        document = await self.caches.product.get_or_load(f"{product_id}&currency={currency}", load)
        if document is None:
            raise ProductNotFoundError(product_id)
        _ = require_admitted(document.product)
        return document

    async def product(self, product_id: str, currency: str) -> ProductResult:
        """Return a product with every stored offer (cheapest first) and its similar products.

        Returns:
            The product view.
        """
        shaper = await self.shaper(currency)
        document = await self.product_document(product_id, currency)
        retailer_offers = document.availability.retailer_offers
        names = ShopNames.from_offers(retailer_offers)
        offers = sorted((shaper.stored_offer(offer, names) for offer in retailer_offers), key=offer_order)
        similar = [
            shaper.located_card(entry, [entry], CardFacts(listed_offers(entry.available_domains), None))
            for entry in screened(document.similar_products).shown
        ]
        detail = shaper.detail(document.product, offers)
        return ProductResult(currency=currency, product=detail, offers=offers, similar=similar)

    async def history(self, product_id: str, currency: str) -> HistoryResult:
        """Return a product and its observed prices per airport (``/api/mobile/product/{id}/snapshots``, last 50).

        Returns:
            The price history.
        """
        _ = await self.shaper(currency)
        document = await self.product_document(product_id, currency)
        params = {"limit": str(HISTORY_SNAPSHOTS), "currency_code": currency}
        path = f"/api/mobile/product/{product_id}/snapshots"
        request = ApiRequest("/api/mobile/product/<id>/snapshots", path, params)

        async def load() -> api.HistoryResponse:
            answer = await self.upstream.get(request)
            return answer.parsed(api.HistoryResponse)

        response = await self.caches.history.get_or_load(f"{product_id}&currency={currency}", load)
        return price_history(response, currency, document.product, self.links)
