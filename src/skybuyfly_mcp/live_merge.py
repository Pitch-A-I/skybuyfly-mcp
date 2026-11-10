# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""Merging the live price stream into offers.

The ``snapshot`` gives every known offer at its stored price, each ``offer`` event then gives one offer's terminal
status, and ``done`` ends the run.

An offer confirmed on the retailer's page (``live_ok``: by this run, by a run in flight for the same listing, or
within the engine's reuse window; ``observed_at`` says when) is ``live``/``live_confirmed`` with that price and
links to the snapshot the check wrote. A failed, timed-out or blocked check keeps the stored price
(``live_check_failed``/``live_timeout``/``live_blocked``); an offer still being checked when the wait ends keeps its
stored price as ``stored``. A ``discovered`` offer (a shop found during the run) joins the offers. The stream names a
shop by its store domain only; its offers take the shop names of the product's stored offers (``retailers``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

from mcp.server.mcpserver.exceptions import ToolError

from skybuyfly_mcp.contract import Money, Offer, offer_scope
from skybuyfly_mcp.live_models import LiveOfferEvent, LiveSnapshot
from skybuyfly_mcp.upstream import parse_body

if TYPE_CHECKING:
    from skybuyfly_mcp.contract import OfferStatus
    from skybuyfly_mcp.live_models import LiveSnapshotOffer, TerminalStatus
    from skybuyfly_mcp.retailers import ShopNames
    from skybuyfly_mcp.shaping import Shaper
    from skybuyfly_mcp.sse import SseEvent

LIVE_ROUTE: Final = "/api/live/product/<id>/stream"
_CHECK_FAILED: dict[TerminalStatus, OfferStatus] = {
    "live_ok": "live_confirmed",
    "live_failed": "live_check_failed",
    "timeout": "live_timeout",
    "blocked": "live_blocked",
}


class IncompleteLiveEventError(ToolError):
    """An ``offer`` event the stream contract does not allow (an unknown offer, a confirmation without its facts)."""

    def __init__(self, offer_id: str, problem: str) -> None:
        """Name the offer and what is wrong with its event."""
        super().__init__(f"The SkyBuyFly live stream sent an invalid event for offer {offer_id!r}: {problem}.")


@dataclass(slots=True)
class LiveCollector:
    """The offers of one live stream so far: the ``sink`` of ``UpstreamClient.stream_events``."""

    shaper: Shaper
    names: ShopNames
    snapshot: LiveSnapshot | None = None
    offers: dict[str, Offer] = field(default_factory=dict[str, Offer])
    resolved: set[str] = field(default_factory=set[str])
    done: bool = False

    def __call__(self, event: SseEvent) -> bool:
        """Consume one event.

        Returns:
            ``True`` when no further event is needed: after ``done``, or a snapshot that starts no live checks.
        """
        if event.name == "snapshot":
            snapshot = parse_body(LIVE_ROUTE, event.data, LiveSnapshot)
            self.snapshot = snapshot
            self.offers = {offer.offer_id: self._stored(offer) for offer in snapshot.offers}
            return not (snapshot.live and snapshot.website)
        if event.name == "offer":
            self._merge(parse_body(LIVE_ROUTE, event.data, LiveOfferEvent))
            return False
        self.done = self.done or event.name == "done"
        return self.done

    @property
    def checking(self) -> int:
        """The number of offers still without a terminal status."""
        return len(self.offers.keys() - self.resolved)

    def _stored(self, offer: LiveSnapshotOffer) -> Offer:
        airport = offer.airport
        scope = offer_scope(airport.code)
        return Offer(
            airport_code=airport.code,
            airport_name=airport.name,
            city=airport.city,
            country=airport.country,
            scope=scope,
            retailer=self.names.retailer(offer.shop, scope),
            retailer_domain=offer.shop,
            price=Money.shop(offer.price, offer.currency),
            display_price=self.shaper.money(offer.display_price, offer.display_currency),
            availability=offer.availability,
            observed_at=offer.observed_at,
            source="stored",
            status="stored",
            skybuyfly_url=self.shaper.links.offer(offer.snapshot_id),
        )

    def _merge(self, event: LiveOfferEvent) -> None:
        known = self.offers.get(event.offer_id)
        if known is None:
            known = self._discovered(event)
        self.resolved.add(event.offer_id)
        if event.status == "live_ok":
            self.offers[event.offer_id] = self._confirmed(known, event)
        else:
            self.offers[event.offer_id] = known.model_copy(update={"status": _CHECK_FAILED[event.status]})

    def _discovered(self, event: LiveOfferEvent) -> Offer:
        airport, shop, snapshot_id, observed_at = event.airport, event.shop, event.snapshot_id, event.observed_at
        if not event.discovered or airport is None or shop is None or snapshot_id is None or observed_at is None:
            raise IncompleteLiveEventError(event.offer_id, "the snapshot did not list it")
        scope = offer_scope(airport.code)
        return Offer(
            airport_code=airport.code,
            airport_name=airport.name,
            city=airport.city,
            country=airport.country,
            scope=scope,
            retailer=self.names.retailer(shop, scope),
            retailer_domain=shop,
            price=None,
            display_price=None,
            availability=None,
            observed_at=observed_at,
            source="stored",
            status="stored",
            skybuyfly_url=self.shaper.links.offer(snapshot_id),
        )

    def _confirmed(self, known: Offer, event: LiveOfferEvent) -> Offer:
        if event.observed_at is None:
            raise IncompleteLiveEventError(event.offer_id, "a live_ok without observed_at")
        link = known.skybuyfly_url if event.snapshot_id is None else self.shaper.links.offer(event.snapshot_id)
        return known.model_copy(
            update={
                "price": Money.shop(event.price, event.currency),
                "display_price": self.shaper.money(event.display_price, event.display_currency),
                "availability": event.availability,
                "observed_at": event.observed_at,
                "source": "live",
                "status": "live_confirmed",
                "skybuyfly_url": link,
            },
        )
