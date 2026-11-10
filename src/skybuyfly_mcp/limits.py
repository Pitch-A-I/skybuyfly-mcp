# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""Sliding one-minute call limits: per client address and across the process.

The client address is ``X-Real-IP``, which the reverse proxy in front must overwrite on every request (and the
server's port must be reachable only through it). ChatGPT and Claude call from shared egress addresses, so the
per-client budget is generous; the global budget protects the upstream API. A refused call is an MCP tool error
naming the wait.
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from mcp.server.mcpserver.exceptions import ToolError

if TYPE_CHECKING:
    from collections.abc import Callable

    from skybuyfly_mcp.config import CallLimits

_SWEEP_EVERY = 1000
WINDOW_SECONDS = 60.0
LimitScope = Literal["client", "global"]
_CLIENT: LimitScope = "client"
_GLOBAL: LimitScope = "global"


@dataclass(slots=True)
class SlidingWindow:
    """At most ``limit`` hits per key in any ``window_seconds``."""

    limit: int
    window_seconds: float = WINDOW_SECONDS
    clock: Callable[[], float] = time.monotonic
    _hits: dict[str, deque[float]] = field(default_factory=dict[str, deque[float]])
    _calls: int = 0

    def hit(self, key: str) -> float | None:
        """Count one hit for ``key`` when the window has room.

        Returns:
            ``None`` when admitted (and counted), else the seconds until the oldest hit leaves the window.
        """
        now = self.clock()
        self._calls += 1
        if self._calls % _SWEEP_EVERY == 0:
            self._sweep(now)
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - self.window_seconds:
            _ = hits.popleft()
        if len(hits) >= self.limit:
            return hits[0] + self.window_seconds - now
        hits.append(now)
        return None

    def _sweep(self, now: float) -> None:
        oldest_kept = now - self.window_seconds
        for key in list(self._hits):
            hits = self._hits[key]
            if not hits or hits[-1] <= oldest_kept:
                del self._hits[key]


class RateLimitedError(ToolError):
    """A tool call refused by a call limit."""

    def __init__(self, scope: LimitScope, retry_after: float) -> None:
        """Name the limit and the whole seconds to wait."""
        self.scope: LimitScope = scope
        self.retry_after_seconds: int = max(1, math.ceil(retry_after))
        who = "from this assistant connection" if scope == _CLIENT else "in total"
        super().__init__(
            f"SkyBuyFly is receiving too many requests {who}; try again in {self.retry_after_seconds} seconds.",
        )


@dataclass(slots=True)
class CallGate:
    """The per-client and global tool call budgets."""

    per_client: SlidingWindow
    overall: SlidingWindow

    @classmethod
    def from_limits(cls, limits: CallLimits, clock: Callable[[], float] = time.monotonic) -> CallGate:
        """Build both windows from the configured budgets.

        Returns:
            The gate.
        """
        return cls(
            per_client=SlidingWindow(limits.per_client_per_minute, clock=clock),
            overall=SlidingWindow(limits.global_per_minute, clock=clock),
        )

    def admit(self, client: str) -> None:
        """Count one tool call of ``client`` (its address, or ``direct`` without nginx in front).

        Raises:
            RateLimitedError: The client's or the global budget is spent.
        """
        client_wait = self.per_client.hit(client)
        if client_wait is not None:
            raise RateLimitedError(_CLIENT, client_wait)
        overall_wait = self.overall.hit("all")
        if overall_wait is not None:
            raise RateLimitedError(_GLOBAL, overall_wait)
