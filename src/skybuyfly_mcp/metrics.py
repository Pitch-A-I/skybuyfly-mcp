# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""Aggregate counters for ``/mcp/metrics``: calls per tool and outcome, per client family, live outcomes.

Nothing personal is kept: no address, no query, no identifier; a client is only its user-agent family
(``client_family``).
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

_FAMILIES = (
    ("openai-mcp", "openai-mcp"),
    ("chatgpt", "chatgpt"),
    ("claude-user", "claude-user"),
    ("claude-code", "claude-code"),
    ("claude", "claude"),
    ("cursor", "cursor"),
    ("visual studio code", "vscode"),
    ("vscode", "vscode"),
    ("gemini", "gemini-cli"),
    ("inspector", "mcp-inspector"),
    ("glama", "glama"),
    ("python-httpx", "python-httpx"),
    ("node", "node"),
)


def client_family(user_agent: str | None) -> str:
    """Return the family of a client's User-Agent (``other`` for every unknown one).

    Returns:
        A short family name, never the user agent itself.
    """
    agent = (user_agent or "").casefold()
    return next((family for marker, family in _FAMILIES if marker in agent), "other")


class MetricsDocument(BaseModel):
    """The ``/mcp/metrics`` answer."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    service: str
    version: str
    uptime_seconds: int
    calls_total: int
    calls_by_tool: dict[str, dict[str, int]]
    calls_by_client: dict[str, int]
    live_outcomes: dict[str, int]
    upstream_statuses: dict[str, int]


@dataclass(slots=True)
class Metrics:
    """Process-wide counters (one process per container)."""

    version: str
    started: float = field(default_factory=time.monotonic)
    by_tool: dict[str, Counter[str]] = field(default_factory=dict[str, Counter[str]])
    by_client: Counter[str] = field(default_factory=Counter[str])
    live: Counter[str] = field(default_factory=Counter[str])
    upstream: Counter[str] = field(default_factory=Counter[str])

    def record(self, tool: str, outcome: str, family: str, upstream_statuses: list[int]) -> None:
        """Count one tool call."""
        self.by_tool.setdefault(tool, Counter())[outcome] += 1
        self.by_client[family] += 1
        self.upstream.update(str(status) for status in upstream_statuses)

    def record_live(self, live_status: str) -> None:
        """Count one live price result by its status."""
        self.live[live_status] += 1

    def document(self) -> MetricsDocument:
        """Return the counters so far.

        Returns:
            The metrics document.
        """
        return MetricsDocument(
            service="skybuyfly-mcp",
            version=self.version,
            uptime_seconds=round(time.monotonic() - self.started),
            calls_total=sum(self.by_client.values()),
            calls_by_tool={tool: dict(outcomes) for tool, outcomes in sorted(self.by_tool.items())},
            calls_by_client=dict(self.by_client),
            live_outcomes=dict(self.live),
            upstream_statuses=dict(self.upstream),
        )
