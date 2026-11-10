# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""API documents to contract objects: product cards, offers and money.

Products reach here screened (``screen``). Prices are compared in the requested display currency only
(``display_price``); a location the API could not convert (no rate for the shop's currency) keeps its shop price
on its offer but has no comparable price on the card.

A card's ``airports`` are its airport prices (the cheapest per airport, cheapest first); its ``lowest_price`` and
``highest_price`` span those and its retailer-wide online listings ("Heinemann online shop"), so a card, its product
and its live check name the same lowest price, and ``lowest_price_scope`` says which kind it is. A card restricted
to some airports (a search's ``airports``) compares those airports' prices only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from mcp.server.mcpserver.exceptions import ToolError

from skybuyfly_mcp.contract import AirportPrice, Money, Offer, ProductCard, ProductDetail, offer_scope

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from skybuyfly_mcp.links import Links
    from skybuyfly_mcp.retailers import ShopNames
    from skybuyfly_mcp.upstream_models import (
        AirportDisplayPrice,
        DetailProduct,
        Measured,
        ProductHead,
        RetailerOffer,
    )


class CurrencyMismatchError(ToolError):
    """The API answered prices in another currency than requested."""

    def __init__(self, requested: str, answered: str) -> None:
        """Name both currencies."""
        super().__init__(f"The SkyBuyFly API answered prices in {answered} instead of {requested}; try again later.")


def size_of(measured: Measured) -> str | None:
    """Return a product's size as the API measures it ("100 ml", "0.261 kg"); never read from its title.

    Returns:
        The amount and its unit, or ``None`` when the API gives none.
    """
    volume, unit = measured.volume, measured.volume_unit
    return None if volume is None or not unit else f"{volume:g} {unit}"


def listed_offers(domains: list[str] | None) -> int | None:
    """Return a catalogue entry's offer count: one current offer per store domain it lists (none listed: unknown).

    Returns:
        The number of offers, or ``None``.
    """
    return None if domains is None else len(domains)


@dataclass(frozen=True, slots=True)
class LocatedPrice:
    """A comparable price at one airport, or at an online listing (no ``code``/``name``), and when it was observed."""

    code: str | None
    name: str | None
    price: Money
    observed_at: datetime | None


@dataclass(frozen=True, slots=True)
class CardFacts:
    """What a card states besides its prices, as the answer gives it: the offer count and the size (or ``None``)."""

    offer_count: int | None
    size: str | None


def _order(price: LocatedPrice) -> tuple[float, bool, str]:
    """Sort key: cheapest first; on a tie an airport before an online listing, then by airport code.

    Returns:
        ``(amount, online, code)``.
    """
    return price.price.amount, price.code is None, price.code or ""


@dataclass(frozen=True, slots=True)
class Shaper:
    """Builds contract objects for one requested display currency."""

    links: Links
    currency: str

    def money(self, amount: float | None, answered: str) -> Money | None:
        """Return a display price in the requested currency.

        Returns:
            The price, or ``None`` when the API could not convert it.

        Raises:
            CurrencyMismatchError: The API answered another display currency.
        """
        if answered != self.currency:
            raise CurrencyMismatchError(self.currency, answered)
        return None if amount is None else Money(amount=amount, currency=self.currency)

    def located_card(
        self,
        head: ProductHead,
        entries: Sequence[AirportDisplayPrice],
        facts: CardFacts,
        only: frozenset[str] | None = None,
    ) -> ProductCard:
        """Return the card of a product priced per location (search offers, home entries, barcode offers).

        A location the API could not convert, or a price without airport fields that is no online listing (a
        recorded price at an unknown location), is no comparable price.

        Returns:
            The card (only ``only``'s airports when given).
        """
        prices: list[LocatedPrice] = []
        for entry in entries:
            price = self.money(entry.display_price, entry.display_currency)
            located = entry.airport_code is not None and entry.airport_name is not None
            if price is not None and (located or entry.online_listing):
                prices.append(LocatedPrice(entry.airport_code, entry.airport_name, price, entry.observed_at))
        return self._card(head, prices, facts, only)

    def offers_card(self, head: ProductHead, offers: Sequence[Offer], size: str | None) -> ProductCard:
        """Return the card of a product from its offers (stored or live).

        Returns:
            The card; its offer count is the number of offers.
        """
        prices: list[LocatedPrice] = []
        for offer in offers:
            price = offer.display_price
            if price is not None:
                prices.append(LocatedPrice(offer.airport_code, offer.airport_name, price, offer.observed_at))
        return self._card(head, prices, CardFacts(len(offers), size), None)

    def detail(self, product: DetailProduct, offers: Sequence[Offer]) -> ProductDetail:
        """Return a product's card with its description and size (``100 ml``).

        Returns:
            The product detail.
        """
        card = self.offers_card(product, offers, size_of(product))
        return ProductDetail(
            product_id=card.product_id,
            title=card.title,
            brand=card.brand,
            category=card.category,
            image_url=card.image_url,
            size=card.size,
            lowest_price=card.lowest_price,
            lowest_price_scope=card.lowest_price_scope,
            highest_price=card.highest_price,
            offer_count=card.offer_count,
            airports=card.airports,
            price_observed_at=card.price_observed_at,
            skybuyfly_url=card.skybuyfly_url,
            description=product.description,
        )

    def _card(
        self,
        head: ProductHead,
        prices: Sequence[LocatedPrice],
        facts: CardFacts,
        only: frozenset[str] | None,
    ) -> ProductCard:
        """Return a product card (the module docstring's rule; only ``only``'s airports when given).

        Returns:
            The card.
        """
        cheapest: dict[str, LocatedPrice] = {}
        listings: list[LocatedPrice] = []
        for price in prices:
            if price.code is None:
                if only is None:
                    listings.append(price)
                continue
            known = cheapest.get(price.code)
            if (only is None or price.code in only) and (known is None or _order(price) < _order(known)):
                cheapest[price.code] = price
        airports = sorted(cheapest.values(), key=_order)
        compared = sorted([*airports, *listings], key=_order)
        lowest = compared[0] if compared else None
        return ProductCard(
            product_id=head.product_id,
            title=head.title,
            brand=head.brand,
            category=head.category,
            image_url=self.links.image(head),
            size=facts.size,
            lowest_price=None if lowest is None else lowest.price,
            lowest_price_scope=None if lowest is None else offer_scope(lowest.code),
            highest_price=compared[-1].price if compared else None,
            offer_count=facts.offer_count,
            airports=[
                AirportPrice(code=price.code, name=price.name, price=price.price)
                for price in airports
                if price.code is not None and price.name is not None
            ],
            price_observed_at=None if lowest is None else lowest.observed_at,
            skybuyfly_url=self.links.product(head.product_id),
        )

    def stored_offer(self, offer: RetailerOffer, names: ShopNames) -> Offer:
        """Return a stored offer of a product, its retailer named by the product's offer labels (``retailers``).

        Returns:
            The offer, linked to its SkyBuyFly deal page.
        """
        scope = offer_scope(offer.airport_code)
        return Offer(
            airport_code=offer.airport_code,
            airport_name=offer.airport_name,
            city=offer.airport_city,
            country=offer.airport_country,
            scope=scope,
            retailer=names.retailer(offer.source_domain, scope),
            retailer_domain=offer.source_domain,
            price=Money.shop(offer.price, offer.price_unit),
            display_price=self.money(offer.display_price, offer.display_currency),
            availability=None,
            observed_at=offer.last_updated,
            source="stored",
            status="stored",
            skybuyfly_url=self.links.offer(offer.snapshot_id),
        )


def offer_order(offer: Offer) -> tuple[bool, float, str]:
    """Sort key: priced offers first, cheapest display price first, then by airport.

    Returns:
        ``(unpriced, amount, airport)``.
    """
    price = offer.display_price
    return price is None, 0.0 if price is None else price.amount, offer.airport_code or ""
