# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The process's services the tools share: the upstream client, the caches, the gates and the counters."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from skybuyfly_mcp.cache import TtlCache
from skybuyfly_mcp.catalogue import Caches, Catalogue, ReferenceCaches
from skybuyfly_mcp.limits import CallGate
from skybuyfly_mcp.links import Links
from skybuyfly_mcp.live import LiveOutcome, LivePrices, utc_now
from skybuyfly_mcp.live_gate import LiveGate
from skybuyfly_mcp.metrics import Metrics
from skybuyfly_mcp.runtime import ToolRunner
from skybuyfly_mcp.upstream import UpstreamClient

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    import httpx

    from skybuyfly_mcp.config import Settings


@dataclass(frozen=True, slots=True)
class Services:
    """What every tool call uses."""

    settings: Settings
    upstream: UpstreamClient
    catalogue: Catalogue
    live: LivePrices
    runner: ToolRunner
    metrics: Metrics

    @classmethod
    def build(
        cls,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = utc_now,
    ) -> Services:
        """Wire the services from the settings.

        ``transport``, ``clock`` and ``wall_clock`` replace the network, the monotonic time and the wall time in tests.

        Returns:
            The services.
        """
        upstream = UpstreamClient(settings.api_base_url, settings.user_agent, transport)
        lifetimes = settings.cache

        def cache[V](ttl: float) -> TtlCache[V]:
            return TtlCache[V](ttl, lifetimes.max_entries, clock)

        caches = Caches(
            search=cache(lifetimes.search_seconds),
            product=cache(lifetimes.product_seconds),
            history=cache(lifetimes.history_seconds),
            barcode=cache(lifetimes.product_seconds),
        )
        reference = ReferenceCaches(
            airports=cache(lifetimes.reference_seconds),
            currencies=cache(lifetimes.reference_seconds),
            home=cache(lifetimes.reference_seconds),
            stats=cache(lifetimes.reference_seconds),
        )
        catalogue = Catalogue(upstream, Links(settings.public_base_url), caches, reference)
        metrics = Metrics(settings.version)
        calls = CallGate.from_limits(settings.calls, clock)
        live = LivePrices(catalogue, LiveGate[LiveOutcome].from_limits(settings.live, clock), wall_clock)
        return cls(settings, upstream, catalogue, live, ToolRunner(calls, metrics), metrics)
