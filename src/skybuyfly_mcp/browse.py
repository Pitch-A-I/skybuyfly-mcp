# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""Browsing tools' upstream calls: barcode lookup, featured products and catalogue statistics.

A barcode answers the product the API resolves it to (``/api/barcode/{code}``: the product carrying the GTIN with
the most airport offers) with that product's own active offers. The API links it to no other product (no merge
redirect, canonical id or ``alternative_product_ids`` entry: 3145891165203 resolves to a Chanel Coco Mademoiselle
whose offers are recorded prices, while the catalogue's current Coco Mademoiselle product does not carry the code),
so the card is built from the barcode answer's own offers, observation dates included, and needs no get_product.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from mcp.server.mcpserver.exceptions import ToolError

from skybuyfly_mcp import upstream_browse as browse_api
from skybuyfly_mcp.categories import popular_categories
from skybuyfly_mcp.contract import BarcodeResult, FeaturedResult
from skybuyfly_mcp.contract_reference import StatsResult
from skybuyfly_mcp.screen import notice, screened
from skybuyfly_mcp.shaping import CardFacts, listed_offers, size_of
from skybuyfly_mcp.upstream import ApiRequest

if TYPE_CHECKING:
    from skybuyfly_mcp import upstream_models as api
    from skybuyfly_mcp.catalogue import Catalogue

_ANSWERS: frozenset[int] = frozenset({HTTPStatus.OK, HTTPStatus.NOT_FOUND, HTTPStatus.UNPROCESSABLE_ENTITY})


class InvalidBarcodeError(ToolError):
    """A code that is no valid EAN-8, UPC-A, EAN-13 or GTIN-14 (the API checks its length and check digit)."""

    def __init__(self) -> None:
        """Say so in the traveller's words (the API's reason code, e.g. ``bad_check_digit``, is not shown)."""
        super().__init__("That barcode is not a valid EAN/UPC code.")


async def lookup_barcode(catalogue: Catalogue, code: str, currency: str) -> BarcodeResult:
    """Look a barcode up (``/api/barcode/{code}``); a code no catalogue product carries answers no products.

    A code the API refuses (422: its check digit or length) raises ``InvalidBarcodeError``.

    Returns:
        The product carrying the code (none when not in the catalogue or not shown).
    """
    shaper = await catalogue.shaper(currency)
    request = ApiRequest("/api/barcode/<code>", f"/api/barcode/{code}", {"currency": currency}, {}, _ANSWERS)

    async def load() -> browse_api.BarcodeResponse | None:
        answer = await catalogue.upstream.get(request)
        if answer.status == HTTPStatus.UNPROCESSABLE_ENTITY:
            raise InvalidBarcodeError
        return None if answer.status == HTTPStatus.NOT_FOUND else answer.parsed(browse_api.BarcodeResponse)

    response = await catalogue.caches.barcode.get_or_load(f"{code}&currency={currency}", load)
    if response is None:
        return BarcodeResult(code=code, currency=currency, products=[], notice=None)
    screen = screened([response.product])
    facts = CardFacts(len(response.offers), size_of(response.product))
    cards = [shaper.located_card(product, response.offers, facts) for product in screen.shown]
    return BarcodeResult(code=code, currency=currency, products=cards, notice=notice(screen.withheld))


async def featured_products(catalogue: Catalogue, currency: str) -> FeaturedResult:
    """Return the home screen's featured and recommended products (not personalised: no session).

    The home screen lists a product once per location (one Guylian box at five airports is five entries), so the
    entries are grouped by ``product_id`` into one card per product, in the order each product first appears, with
    its price at each of those airports; its offer count is the number of store domains the API lists for it (one
    per current offer). The popular categories are cleaned (``categories``).

    Returns:
        One card per product and the popular categories.
    """
    shaper = await catalogue.shaper(currency)

    request = ApiRequest("/api/mobile/home", "/api/mobile/home", {}, {"X-Display-Currency": currency})

    async def load() -> browse_api.HomeResponse:
        answer = await catalogue.upstream.get(request)
        return answer.parsed(browse_api.HomeResponse)

    response = await catalogue.reference.home.get_or_load(f"currency={currency}", load)
    screen = screened([*response.featured_products, *response.recommended_products])
    grouped: dict[str, list[api.CatalogueEntry]] = {}
    for entry in screen.shown:
        grouped.setdefault(entry.product_id, []).append(entry)
    groups = grouped.values()
    cards = [
        shaper.located_card(entries[0], entries, CardFacts(listed_offers(entries[0].available_domains), None))
        for entries in groups
    ]
    categories = popular_categories(response.popular_categories)
    return FeaturedResult(
        currency=currency,
        products=cards,
        popular_categories=categories,
        notice=notice(screen.withheld),
    )


async def catalogue_stats(catalogue: Catalogue) -> StatsResult:
    """Return the catalogue's size and freshness (``/api/system_status``) and the number of airports.

    Returns:
        The catalogue statistics.
    """

    async def load() -> browse_api.StatusResponse:
        answer = await catalogue.upstream.get(ApiRequest("/api/system_status", "/api/system_status"))
        return answer.parsed(browse_api.StatusResponse)

    status = await catalogue.reference.stats.get_or_load("status", load)
    airports = await catalogue.airports()
    return StatsResult(
        total_products=status.total_products,
        airports=len(airports.airports),
        generated_at=status.timestamp,
    )
