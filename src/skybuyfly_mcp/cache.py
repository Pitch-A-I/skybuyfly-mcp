# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""A small bounded TTL cache of upstream answers (one instance per kind of answer, each with its own lifetime).

Only successful loads are kept: a load that raises stores nothing and the error reaches the caller unchanged.
Beyond ``max_entries`` the least recently used entry is evicted.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


@dataclass(slots=True)
class TtlCache[V]:
    """Answers kept for ``ttl_seconds`` under a string key."""

    ttl_seconds: float
    max_entries: int
    clock: Callable[[], float] = time.monotonic
    _entries: OrderedDict[str, tuple[float, V]] = field(default_factory=OrderedDict[str, tuple[float, V]])

    async def get_or_load(self, key: str, load: Callable[[], Awaitable[V]]) -> V:
        """Return the cached answer for ``key``, loading (and keeping) it when absent or expired.

        Returns:
            The fresh cached value, or the value ``load`` returned.
        """
        now = self.clock()
        entry = self._entries.get(key)
        if entry is not None and entry[0] > now:
            self._entries.move_to_end(key)
            return entry[1]
        value = await load()
        self._entries[key] = (self.clock() + self.ttl_seconds, value)
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            _ = self._entries.popitem(last=False)
        return value

    def __len__(self) -> int:
        """Return the number of kept entries (expired ones included until evicted or replaced)."""
        return len(self._entries)
