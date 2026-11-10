# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The public SkyBuyFly API's JSON documents, as far as the tools read them (every other field is ignored).

A field the API always sends is required (nullable where the API sends ``null``), so a changed API fails the
tool call loudly at the edge (``upstream.UpstreamContractError``) instead of shaping half a document. The API's
database keeps naive UTC timestamps (``last_updated`` of a product offer, ``crawl_date`` of a snapshot): a
timestamp without an offset is UTC (``UtcDatetime``). The home screen, barcode and status documents are in
``upstream_browse``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, ClassVar, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]
Availability = Literal["in_stock", "sold_out_online"]


class Upstream(BaseModel):
    """An API document: unknown fields are ignored, read fields are validated."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", frozen=True)


class ProductImages(Upstream):
    """The image fields every product document carries."""

    canonical_image: str | None
    image_url: str | None
    duckduckgo_img: str | None = None
    """Absent from barcode answers; elsewhere always sent (often null)."""


class ProductHead(ProductImages):
    """A product document's identity, as every product-bearing answer carries it."""

    product_id: str
    title: str
    brand: str | None
    category: str | None
    description: str | None = None
    """The product's own text (the restricted-goods screen reads it): absent from barcode answers, elsewhere always
    sent (often null)."""


class AirportDisplayPrice(Upstream):
    """A product's price at one location in the requested display currency (null without a rate)."""

    airport_code: str | None
    airport_name: str | None
    price: float | None
    price_unit: str | None
    display_price: float | None
    display_currency: str
    observed_at: UtcDatetime | None

    @property
    def online_listing(self) -> bool:
        """Whether the price is a retailer-wide online listing serving several airports (no airport fields)."""
        return self.airport_code is None


class SearchOffer(ProductHead, AirportDisplayPrice):
    """One offer of a search card; ``serving_state`` says whether it is current or a recorded (older) price."""

    serving_state: Literal["current_snapshot", "recorded_price"]

    @property
    def online_listing(self) -> bool:
        """A current offer without airport fields; a recorded price without them is at an unknown location."""
        return self.airport_code is None and self.serving_state == "current_snapshot"


class CatalogueEntry(ProductHead, AirportDisplayPrice):
    """A home or similar product entry: one product at one location, observed at ``last_updated``.

    ``available_domains`` lists the store domain of every current offer of the product (one per offer).
    """

    observed_at: UtcDatetime | None = Field(validation_alias="last_updated")
    available_domains: list[str] | None


class SearchCard(ProductHead):
    """One product of ``/api/search?group=product`` with every offer it has (``offer_count`` of them)."""

    offers: list[SearchOffer]
    offer_count: int


class SearchResults(Upstream):
    """The ``results`` block of a search."""

    products: list[SearchCard]


class SearchPagination(Upstream):
    """The ``pagination`` block of a cursor search."""

    next_cursor: str | None


class SearchResponse(Upstream):
    """``GET /api/search?group=product``."""

    results: SearchResults
    pagination: SearchPagination


class Measured(Upstream):
    """A product's size: the API serves a volume, or a mass, in the ``volume`` pair ("100 ml", "0.261 kg")."""

    volume: float | None
    volume_unit: str | None


class DetailProduct(ProductHead, Measured):
    """The ``product`` block of ``/api/mobile/product/{id}`` (its ``description`` is always sent)."""


class RetailerOffer(Upstream):
    """One stored offer of a product; an online shop serving several airports has no airport fields.

    ``retailer_name`` labels the offer ("Vienna International Airport (VIE) · Austria — Heinemann", "Heinemann Duty
    Free (multiple locations)": ``retailers``).
    """

    retailer_key: str
    retailer_name: str | None
    snapshot_id: str
    price: float | None
    price_unit: str | None
    display_price: float | None
    display_currency: str
    source_domain: str
    last_updated: UtcDatetime
    airport_code: str | None = None
    airport_name: str | None = None
    airport_city: str | None = None
    airport_country: str | None = None


class ProductAvailability(Upstream):
    """The ``availability`` block of a product."""

    retailer_offers: list[RetailerOffer]


class ProductDetailResponse(Upstream):
    """``GET /api/mobile/product/{id}``."""

    product: DetailProduct
    availability: ProductAvailability
    similar_products: list[CatalogueEntry]


class HistorySnapshot(Upstream):
    """One observed price (``location`` is null for an online shop serving several airports)."""

    domain: str
    location: str | None
    price: float | None
    price_unit: str
    crawl_date: UtcDatetime | None


class HistoryResponse(Upstream):
    """``GET /api/mobile/product/{id}/snapshots``."""

    product_id: str
    currency_code: str
    snapshots: list[HistorySnapshot]


class AirportEntry(Upstream):
    """One airport shop of ``/api/mobile/airports`` (``name`` ends with the IATA code in parentheses)."""

    iata_code: str
    name: str
    city: str
    domain: str


class AirportsResponse(Upstream):
    """``GET /api/mobile/airports``."""

    airports: list[AirportEntry]


class CurrencyEntry(Upstream):
    """One display currency."""

    code: str
    name: str
    symbol: str


class CurrenciesResponse(Upstream):
    """``GET /api/mobile/currencies``."""

    available_currencies: list[CurrencyEntry]


class ErrorBody(Upstream):
    """The JSON error documents of the API's routes (each names its cause in one of these fields)."""

    error: str | None = None
    error_code: str | None = None
    reason: str | None = None
    retry_after: int | None = None
