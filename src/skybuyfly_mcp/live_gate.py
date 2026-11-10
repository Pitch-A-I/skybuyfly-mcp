# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""This process's own bounds on live price streams, inside the live engine's admission.

All MCP traffic reaches the live API from one address (the MCP server's own), so the engine's per-client
bucket (30 requests a minute) is the hard ceiling. Here at most ``max_concurrent`` streams are open at once and at
most ``runs_per_minute`` start per minute; identical requests (same product and currency) share one stream while it
runs and its result for ``coalesce_seconds`` afterwards. A request beyond a bound is refused at once (never queued),
and the tool answers ``rate_limited``. A shared stream's failure reaches every caller still waiting; the stream task
also retrieves its own failure when it ends (``_retrieved``), so a failure is never reported as unretrieved, however
its callers went away.
"""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from skybuyfly_mcp.limits import SlidingWindow

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from skybuyfly_mcp.config import LiveLimits

BUSY_RETRY_SECONDS = 15
"""How long a request refused for concurrency should wait: about one stream's length (wait at most 20 s)."""
LiveKey = tuple[str, str]
"""``(product_id, currency)``."""


def _retrieved[R](task: asyncio.Task[R]) -> None:
    """Retrieve a finished stream's failure (its waiting callers get it themselves; a gone caller does not)."""
    if not task.cancelled():
        _ = task.exception()


@dataclass(frozen=True, slots=True)
class LiveRefusal:
    """A live request refused by this process's bounds, and how long to wait."""

    reason: Literal["mcp_concurrency", "mcp_rate"]
    retry_after_seconds: int


@dataclass(slots=True)
class LiveGate[R]:
    """Admits, shares and briefly reuses live streams."""

    max_concurrent: int
    runs: SlidingWindow
    coalesce_seconds: float
    clock: Callable[[], float] = time.monotonic
    _inflight: dict[LiveKey, asyncio.Task[R]] = field(default_factory=dict[LiveKey, "asyncio.Task[R]"])
    _recent: dict[LiveKey, tuple[float, R]] = field(default_factory=dict[LiveKey, tuple[float, R]])

    @classmethod
    def from_limits(cls, limits: LiveLimits, clock: Callable[[], float] = time.monotonic) -> LiveGate[R]:
        """Build the gate from the configured live limits.

        Returns:
            The gate.
        """
        return cls(
            limits.max_concurrent,
            SlidingWindow(limits.runs_per_minute, clock=clock),
            limits.coalesce_seconds,
            clock,
        )

    @property
    def active(self) -> int:
        """Streams open now."""
        return len(self._inflight)

    async def run(
        self,
        key: LiveKey,
        start: Callable[[], Awaitable[R]],
        *,
        reusable: Callable[[R], bool],
    ) -> R | LiveRefusal:
        """Return ``key``'s recent or running result, or start ``start`` when the bounds allow.

        A result ``reusable`` accepts answers identical requests for ``coalesce_seconds``. A caller that goes away
        does not cancel a stream other callers share.

        Returns:
            The live result, or the refusal when a bound is reached.
        """
        now = self.clock()
        for known in list(self._recent):
            if self._recent[known][0] <= now:
                del self._recent[known]
        recent = self._recent.get(key)
        if recent is not None:
            return recent[1]
        running = self._inflight.get(key)
        if running is not None:
            return await asyncio.shield(running)
        if self.active >= self.max_concurrent:
            return LiveRefusal("mcp_concurrency", BUSY_RETRY_SECONDS)
        wait = self.runs.hit("live")
        if wait is not None:
            return LiveRefusal("mcp_rate", max(1, math.ceil(wait)))
        task = asyncio.get_running_loop().create_task(self._stream(key, start, reusable))
        task.add_done_callback(_retrieved)
        self._inflight[key] = task
        return await asyncio.shield(task)

    async def _stream(self, key: LiveKey, start: Callable[[], Awaitable[R]], reusable: Callable[[R], bool]) -> R:
        try:
            result = await start()
        finally:
            del self._inflight[key]
        if reusable(result):
            self._recent[key] = (self.clock() + self.coalesce_seconds, result)
        return result
