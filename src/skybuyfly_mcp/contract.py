# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The tools' structured output (``structuredContent``), as the user story's tool contract defines it.

Every price is ``{amount, currency}`` with the amount rounded to cents; every link is on SkyBuyFly's own domain
(``links``). ``view`` tells the widget how to render a result. No request, trace, session or client identifier is
ever part of a result. The reference tools' documents are in ``contract_reference``.
"""

from __future__ import annotations

import functools
from datetime import datetime
from typing import Annotated, ClassVar, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

OfferStatus = Literal["live_confirmed", "stored", "live_check_failed", "live_timeout", "live_blocked"]
LiveRunStatus = Literal["complete", "partial", "rate_limited", "unavailable", "no_offers"]
OfferScope = Literal["airport", "online_shop"]
"""``airport``: one airport's shop; ``online_shop``: a retailer-wide online listing serving several airports."""
Timestamp = Annotated[datetime, Field(description="ISO 8601 timestamp (UTC)")]
CENTS = 2
"""Every amount is rounded to two decimals (the API's converted prices carry more: 156.2307522519091)."""


Amount = Annotated[float, AfterValidator(functools.partial(round, ndigits=CENTS))]


def offer_scope(airport_code: str | None) -> OfferScope:
    """Return the scope of an offer with this airport code (none: an online shop serving several airports).

    Returns:
        ``airport`` or ``online_shop``.
    """
    return "online_shop" if airport_code is None else "airport"


class Contract(BaseModel):
    """A tool output document (immutable, no unknown fields)."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)


class Money(Contract):
    """An amount in an ISO 4217 currency, rounded to cents."""

    amount: Amount
    currency: str

    @classmethod
    def shop(cls, amount: float | None, currency: str | None) -> Money | None:
        """Return a shop's own price.

        Returns:
            The price, or ``None`` when the shop has none (or names no currency).
        """
        return None if amount is None or currency is None else cls(amount=amount, currency=currency)


class AirportPrice(Contract):
    """A product's price at one airport, in the requested currency."""

    code: str
    name: str
    price: Money


class ProductCard(Contract):
    """One product with its price at every airport that sells it (cheapest first).

    ``lowest_price``/``highest_price`` span every comparable shop price, online shops included
    (``lowest_price_scope`` says where the lowest is); ``airports`` lists airport prices only. ``offer_count`` is the
    number of shop offers the API knows for the product (null where the answer does not say). ``size`` is the API's
    own measure ("100 ml"; null where the answer carries none).
    """

    product_id: str
    title: str
    brand: str | None
    category: str | None
    image_url: str | None
    size: str | None
    lowest_price: Money | None
    lowest_price_scope: OfferScope | None
    highest_price: Money | None
    offer_count: int | None
    airports: list[AirportPrice]
    price_observed_at: Timestamp | None
    skybuyfly_url: str


class ProductDetail(ProductCard):
    """A product card with its description."""

    description: str | None


class Offer(Contract):
    """One shop's offer: at one airport, or a retailer-wide online shop (``scope``), whose airport fields are null.

    An ``online_shop`` offer is a real shop price, never one of a card's ``airports``.
    """

    airport_code: str | None
    airport_name: str | None
    city: str | None
    country: str | None
    scope: OfferScope
    retailer: str
    """The shop's readable name ("Heinemann", "Heinemann online shop": ``retailers``)."""
    retailer_domain: str
    """The shop's store domain ("www.heinemann-shop.com")."""
    price: Money | None
    display_price: Money | None
    availability: Literal["in_stock", "sold_out_online"] | None
    observed_at: Timestamp
    source: Literal["live", "stored"]
    status: OfferStatus
    skybuyfly_url: str

    @model_validator(mode="after")
    def _scoped(self) -> Self:
        # An airport offer has its airport code, an online-shop offer none.
        if self.scope != offer_scope(self.airport_code):
            message = f"scope {self.scope!r} with airport_code {self.airport_code!r}"
            raise ValueError(message)
        return self


class ProductListResult(Contract):
    """``search_products`` (``notice``: set when tobacco or nicotine products were left out of this answer)."""

    view: Literal["product_list"] = "product_list"
    query: str
    currency: str
    products: list[ProductCard]
    next_cursor: str | None
    notice: str | None


class ProductResult(Contract):
    """``get_product``."""

    view: Literal["product"] = "product"
    currency: str
    product: ProductDetail
    offers: list[Offer]
    similar: list[ProductCard]


class LiveSummary(Contract):
    """How a live check went: offers checked, confirmed, failed, and shown with their stored price only."""

    checked: int
    live_confirmed: int
    failed: int
    stored_only: int


class LiveResult(Contract):
    """``get_live_prices``; ``retry_after_seconds`` is set when rate limited, ``reason`` when unavailable."""

    view: Literal["live_offers"] = "live_offers"
    product: ProductCard
    currency: str
    checked_at: Timestamp
    live_status: LiveRunStatus
    retry_after_seconds: int | None
    reason: str | None
    offers: list[Offer]
    summary: LiveSummary
    cheapest: Offer | None


class HistoryPoint(Contract):
    """One observed price."""

    date: Timestamp
    price: Money


class AirportHistory(Contract):
    """A product's observed prices at one airport (``code`` null: an online shop serving several airports)."""

    code: str | None
    name: str
    points: list[HistoryPoint]
    lowest: Money
    latest: Money


class HistoryResult(Contract):
    """``get_price_history``: the product (for the widget's header) and its recent observations per airport."""

    view: Literal["price_history"] = "price_history"
    product_id: str
    title: str
    brand: str | None
    image_url: str | None
    skybuyfly_url: str
    currency: str
    airports: list[AirportHistory]


class BarcodeResult(Contract):
    """``lookup_barcode`` (an empty list: no catalogue product carries the code)."""

    view: Literal["product_list"] = "product_list"
    code: str
    currency: str
    products: list[ProductCard]
    notice: str | None


class PopularCategory(Contract):
    """A catalogue category and its product count."""

    name: str
    count: int


class FeaturedResult(Contract):
    """``get_featured_products``."""

    view: Literal["product_list"] = "product_list"
    currency: str
    products: list[ProductCard]
    popular_categories: list[PopularCategory]
    notice: str | None
