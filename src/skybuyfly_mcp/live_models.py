# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The live price stream's events (schema ``aipc.live-price/v1``): ``snapshot``, then ``offer`` per offer, ``done``.

Every request names a display currency (``?currency=``), so every offer carries ``display_currency`` (and
``display_price``, null without a price or a rate).
"""

from __future__ import annotations

from typing import Literal

from skybuyfly_mcp import upstream_models

LiveStatus = Literal["checking_live", "live_ok", "live_failed", "timeout", "blocked"]
TerminalStatus = Literal["live_ok", "live_failed", "timeout", "blocked"]


class LiveAirport(upstream_models.Upstream):
    """The airport block of a live offer (every field but ``key`` is null for an online shop)."""

    key: str
    name: str | None
    code: str | None
    city: str | None
    country: str | None


class LiveSnapshotOffer(upstream_models.Upstream):
    """One known offer of the ``snapshot`` event."""

    offer_id: str
    snapshot_id: str
    airport: LiveAirport
    shop: str
    price: float | None
    currency: str | None
    availability: upstream_models.Availability | None
    observed_at: upstream_models.UtcDatetime
    status: LiveStatus
    display_price: float | None
    display_currency: str


class LiveSnapshot(upstream_models.Upstream):
    """The ``snapshot`` event; ``reason`` says why ``live`` is false."""

    product_id: str
    live: bool
    reason: str | None
    website: bool
    generated_at: upstream_models.UtcDatetime
    offers: list[LiveSnapshotOffer]


class LiveOfferEvent(upstream_models.Upstream):
    """One ``offer`` event; a ``discovered`` offer (a shop found during the run) also names its airport and shop."""

    offer_id: str
    status: TerminalStatus
    price: float | None
    currency: str | None
    availability: upstream_models.Availability | None
    observed_at: upstream_models.UtcDatetime | None
    snapshot_id: str | None
    source: Literal["stored", "memo", "live", "coalesced", "gate"]
    discovered: bool
    display_price: float | None
    display_currency: str
    airport: LiveAirport | None = None
    shop: str | None = None
