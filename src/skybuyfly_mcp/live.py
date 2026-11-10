# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""``get_live_prices``: read the live price stream exactly as the website does, within this process's bounds.

The stream is asked to report ``done`` within the tool's wait (``?wait=``: the engine's ``FetchLimits.deadline_for``
answers one second before it); whatever has arrived when the wait ends is the answer. The engine's own admission
and kill switch always apply: its 429 is ``rate_limited`` (no offers: stored prices come from ``get_product``), its
404 ``no_known_offers`` is ``no_offers`` (the engine then searches the shops itself), and a snapshot without live
checks (``live: false``, or the website flag off) is ``unavailable`` with the engine's reason. A product the engine
knows by its identity only opens a run whose snapshot lists no offer (its discovery may add ``discovered`` offers
while it runs): a run that ends, or whose wait ends, with no offer at all is ``no_offers`` too, never a "complete"
check of nothing.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from http import HTTPStatus
from typing import TYPE_CHECKING, Final

from mcp.server.mcpserver.exceptions import ToolError

from skybuyfly_mcp.catalogue import ProductNotFoundError
from skybuyfly_mcp.contract import LiveResult, LiveSummary
from skybuyfly_mcp.live_gate import LiveRefusal
from skybuyfly_mcp.live_merge import LIVE_ROUTE, LiveCollector
from skybuyfly_mcp.retailers import ShopNames
from skybuyfly_mcp.shaping import offer_order, size_of
from skybuyfly_mcp.upstream import ApiRequest, StreamRefused, UpstreamError

if TYPE_CHECKING:
    from collections.abc import Callable

    from skybuyfly_mcp.catalogue import Catalogue
    from skybuyfly_mcp.contract import LiveRunStatus, Offer
    from skybuyfly_mcp.live_gate import LiveGate
    from skybuyfly_mcp.upstream import StreamEnd


class SilentLiveStreamError(ToolError):
    """The live stream sent no snapshot: it closed first, or the wait ran out."""

    def __init__(self, ended: StreamEnd, wait_seconds: float) -> None:
        """Say how the stream ended without a snapshot."""
        why = (
            "closed before sending any price"
            if ended == "closed"
            else f"sent no price within the {wait_seconds:g} s wait"
        )
        super().__init__(f"The SkyBuyFly live price stream {why}; use get_product for the stored prices.")


@dataclass(frozen=True, slots=True)
class LiveOutcome:
    """What one live request found, before it is shown as a product's result."""

    live_status: LiveRunStatus
    checked_at: datetime
    offers: tuple[Offer, ...] = ()
    retry_after_seconds: int | None = None
    reason: str | None = None


utc_now: Final = partial(datetime.now, UTC)
"""The current time in UTC: the live service's wall clock outside tests and the widget harness."""


def _refused(refusal: StreamRefused, product_id: str, now: datetime) -> LiveOutcome:
    if refusal.status == HTTPStatus.TOO_MANY_REQUESTS:
        return LiveOutcome(
            "rate_limited",
            now,
            retry_after_seconds=refusal.error.retry_after,
            reason="upstream_rate_limit",
        )
    if refusal.status == HTTPStatus.NOT_FOUND and refusal.error.error == "no_known_offers":
        return LiveOutcome("no_offers", now)
    if refusal.status == HTTPStatus.NOT_FOUND:
        raise ProductNotFoundError(product_id)
    raise UpstreamError(LIVE_ROUTE, refusal.status, refusal.error)


def _collected(collector: LiveCollector, ended: StreamEnd, wait_seconds: float, now: datetime) -> LiveOutcome:
    snapshot = collector.snapshot
    if snapshot is None:
        raise SilentLiveStreamError(ended, wait_seconds)
    offers = tuple(sorted(collector.offers.values(), key=offer_order))
    if not snapshot.live or not snapshot.website:
        return LiveOutcome("unavailable", now, offers, reason=snapshot.reason or "website_live_disabled")
    if not offers:
        return LiveOutcome("no_offers", now)
    complete = collector.done and collector.checking == 0
    return LiveOutcome("complete" if complete else "partial", now, offers)


@dataclass(frozen=True, slots=True)
class LivePrices:
    """The live price tool's service: the catalogue (product, currency), this process's live gate and wall clock.

    ``checked_at`` is the wall clock's time when the check ended (``utc_now``; the widget harness sets it to the
    recorded run's end).
    """

    catalogue: Catalogue
    gate: LiveGate[LiveOutcome]
    wall_clock: Callable[[], datetime]

    async def check(self, product_id: str, currency: str, wait_seconds: float) -> LiveResult:
        """Check a product's offers live (or answer an identical request's result of the last minute).

        Returns:
            The product's offers, each live-confirmed or stored, and how the check went.
        """
        shaper = await self.catalogue.shaper(currency)
        document = await self.catalogue.product_document(product_id, currency)
        names = ShopNames.from_offers(document.availability.retailer_offers)

        async def start() -> LiveOutcome:
            return await self._stream(product_id, LiveCollector(shaper, names), wait_seconds)

        outcome = await self.gate.run(
            (product_id, currency),
            start,
            reusable=lambda done: done.live_status != "rate_limited",
        )
        if isinstance(outcome, LiveRefusal):
            outcome = LiveOutcome(
                "rate_limited",
                self.wall_clock(),
                retry_after_seconds=outcome.retry_after_seconds,
                reason=outcome.reason,
            )
        offers = list(outcome.offers)
        priced = [offer for offer in offers if offer.display_price is not None]
        statuses = Counter(offer.status for offer in offers)
        failed = statuses["live_check_failed"] + statuses["live_timeout"] + statuses["live_blocked"]
        return LiveResult(
            product=shaper.offers_card(document.product, offers, size_of(document.product)),
            currency=currency,
            checked_at=outcome.checked_at,
            live_status=outcome.live_status,
            retry_after_seconds=outcome.retry_after_seconds,
            reason=outcome.reason,
            offers=offers,
            summary=LiveSummary(
                checked=len(offers) - statuses["stored"],
                live_confirmed=statuses["live_confirmed"],
                failed=failed,
                stored_only=statuses["stored"],
            ),
            cheapest=min(priced, key=offer_order) if priced else None,
        )

    async def _stream(self, product_id: str, collector: LiveCollector, wait_seconds: float) -> LiveOutcome:
        params = {"wait": f"{wait_seconds:g}", "currency": collector.shaper.currency}
        request = ApiRequest(LIVE_ROUTE, f"/api/live/product/{product_id}/stream", params)
        ended = await self.catalogue.upstream.stream_events(request, wait_seconds, collector)
        if isinstance(ended, StreamRefused):
            return _refused(ended, product_id, self.wall_clock())
        return _collected(collector, ended, wait_seconds, self.wall_clock())
