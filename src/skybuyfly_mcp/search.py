# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""``search_products``: catalogue search pages (``/api/search?group=product``), screened and filled to the limit.

The search API pages by an opaque cursor bound to the page size; ``airports`` (store domains) keeps the products the
catalogue lists at every one of them (the API's filter is an intersection). A page loses the products the
restricted-goods screen withholds (``screen``) and, with ``airports``, those without a current price at any of
them (listed there, no price: nothing to compare). The rule:

1. Read the page at the cursor and keep its shown products after the cursor's offset into that page.
2. While fewer than ``limit`` products are kept and the API has a next page, read it (at most ``EXTRA_PAGES`` more
   pages per call) and keep as many of its shown products as still fit.
3. ``next_cursor`` continues right after the last product returned: the page it is on and how many of that page's
   shown products are returned (``SearchCursor``, written ``<offset>:<API cursor>``), so no product is skipped or
   repeated. It is ``null`` when the API has no further page, and when the last page read showed no product at all
   (the window turned into withheld products: a further page would most likely show none either).

``notice`` is set when the screen withheld a product of a page read for this answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from mcp.server.mcpserver.exceptions import ToolError

from skybuyfly_mcp import upstream_models as api
from skybuyfly_mcp.contract import ProductListResult
from skybuyfly_mcp.screen import notice, screened
from skybuyfly_mcp.shaping import CardFacts
from skybuyfly_mcp.upstream import ApiRequest

if TYPE_CHECKING:
    from skybuyfly_mcp.catalogue import Catalogue
    from skybuyfly_mcp.contract import ProductCard
    from skybuyfly_mcp.screen import Screened
    from skybuyfly_mcp.shaping import Shaper

EXTRA_PAGES: Final = 2
"""Further API pages one call may read to fill its page (three API pages at most)."""
_CURSOR = re.compile(r"(?P<offset>\d{1,2}):(?P<page>.*)", re.DOTALL)


class InvalidCursorError(ToolError):
    """A cursor that no search_products answer issued."""

    def __init__(self) -> None:
        """Say what a cursor is."""
        super().__init__("Invalid cursor: pass the next_cursor of the previous search_products answer unchanged.")


@dataclass(frozen=True, slots=True)
class SearchCursor:
    """Where a search continues: an API page (``None``: the first) and how many of its shown products came before."""

    page: str | None
    offset: int

    @classmethod
    def parse(cls, cursor: str | None) -> SearchCursor:
        """Read a ``next_cursor`` this tool issued (``None``: the start of the search).

        Returns:
            The position.

        Raises:
            InvalidCursorError: The cursor is not ``<offset>:<API cursor>``.
        """
        if cursor is None:
            return cls(None, 0)
        match = _CURSOR.fullmatch(cursor)
        if match is None:
            raise InvalidCursorError
        return cls(match["page"] or None, int(match["offset"]))

    def text(self) -> str:
        """Return the cursor as the tool answers it.

        Returns:
            ``<offset>:<API cursor>``.
        """
        return f"{self.offset}:{self.page or ''}"


@dataclass(frozen=True, slots=True)
class SearchQuery:
    """A catalogue search: text, IATA codes (the catalogue lists the product at each), currency, page size, cursor."""

    text: str
    airports: tuple[str, ...]
    currency: str
    limit: int
    cursor: str | None

    @property
    def requested(self) -> frozenset[str] | None:
        """Return the requested airports' IATA codes, upper-cased.

        Returns:
            The codes, or ``None`` without an airport filter.
        """
        codes = frozenset(code.strip().upper() for code in self.airports)
        return codes or None

    def params(self, domains: tuple[str, ...], page: str | None) -> dict[str, str]:
        """Return the search API's query for these airports' store domains and API page.

        Returns:
            ``q``, ``limit``, ``group=product`` and, when given, ``airports`` and ``cursor``.
        """
        params = {"q": self.text, "limit": str(self.limit), "group": "product"}
        if domains:
            params["airports"] = ",".join(domains)
        if page:
            params["cursor"] = page
        return params


async def _page(
    catalogue: Catalogue,
    query: SearchQuery,
    domains: tuple[str, ...],
    page: str | None,
) -> api.SearchResponse:
    params = query.params(domains, page)
    request = ApiRequest("/api/search", "/api/search", params, {"X-Display-Currency": query.currency})
    key = "&".join([*(f"{name}={value}" for name, value in sorted(params.items())), f"currency={query.currency}"])

    async def load() -> api.SearchResponse:
        answer = await catalogue.upstream.get(request)
        return answer.parsed(api.SearchResponse)

    return await catalogue.caches.search.get_or_load(key, load)


async def _screened_page(
    catalogue: Catalogue,
    query: SearchQuery,
    domains: tuple[str, ...],
    page: str | None,
) -> tuple[Screened[api.SearchCard], str | None]:
    """Read one API page through the restricted-goods screen.

    Returns:
        The page's screened products and the API's cursor of the next page (``None``: the last page).
    """
    response = await _page(catalogue, query, domains, page)
    return screened(response.results.products), response.pagination.next_cursor


def _shown(shaper: Shaper, hits: list[api.SearchCard], requested: frozenset[str] | None) -> list[ProductCard]:
    cards = [shaper.located_card(hit, hit.offers, CardFacts(hit.offer_count, None), requested) for hit in hits]
    return [card for card in cards if requested is None or card.airports]


async def search_products(catalogue: Catalogue, query: SearchQuery) -> ProductListResult:
    """Search the catalogue: one card per product, filled to ``limit`` by the module docstring's rule.

    Returns:
        The products, the cursor of the next page and the restricted-goods notice.
    """
    shaper = await catalogue.shaper(query.currency)
    domains = (await catalogue.airports()).store_domains(query.airports)
    position = SearchCursor.parse(query.cursor)
    cards: list[ProductCard] = []
    withheld, following = 0, None
    for read in range(1 + EXTRA_PAGES):
        screen, api_next = await _screened_page(catalogue, query, domains, position.page)
        withheld += screen.withheld
        shown = _shown(shaper, screen.shown, query.requested)
        remaining, room = shown[position.offset :], query.limit - len(cards)
        cards.extend(remaining[:room])
        if len(remaining) > room:
            following = SearchCursor(position.page, position.offset + room)
            break
        last_read = read == EXTRA_PAGES
        if api_next is None or len(cards) == query.limit or last_read:
            following = None if api_next is None or (last_read and not shown) else SearchCursor(api_next, 0)
            break
        position = SearchCursor(api_next, 0)
    return ProductListResult(
        query=query.text,
        currency=query.currency,
        products=cards,
        next_cursor=None if following is None else following.text(),
        notice=notice(withheld),
    )
