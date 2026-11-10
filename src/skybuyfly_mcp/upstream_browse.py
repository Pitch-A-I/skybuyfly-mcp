# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The browsing routes' JSON documents: home screen, barcode and catalogue status (``upstream_models``' rules)."""

from __future__ import annotations

from pydantic import Field

from skybuyfly_mcp import upstream_models as api


class HomeCategory(api.Upstream):
    """One popular category of the home screen."""

    name: str
    count: int


class HomeResponse(api.Upstream):
    """``GET /api/mobile/home`` (one entry per product and location)."""

    featured_products: list[api.CatalogueEntry]
    recommended_products: list[api.CatalogueEntry]
    popular_categories: list[HomeCategory]


class BarcodeProduct(api.ProductHead, api.Measured):
    """The ``product`` block of a barcode answer."""


class BarcodeOffer(api.AirportDisplayPrice):
    """One active offer of a barcode answer, observed at ``last_updated``."""

    observed_at: api.UtcDatetime | None = Field(validation_alias="last_updated")


class BarcodeResponse(api.Upstream):
    """``GET /api/barcode/{code}`` (200)."""

    product: BarcodeProduct
    offers: list[BarcodeOffer]


class StatusResponse(api.Upstream):
    """``GET /api/system_status``."""

    total_products: int
    timestamp: api.UtcDatetime
