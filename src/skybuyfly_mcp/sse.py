# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""Server-Sent Events framing (the subset the live price stream uses): ``event:``, ``data:``, comments, blank line."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SseEvent:
    """One dispatched event: its name (``message`` when unnamed) and its data lines joined by newlines."""

    name: str
    data: str


@dataclass(slots=True)
class SseParser:
    """Turns stream lines (without their line ending) into events; a blank line dispatches the pending event."""

    _name: str = ""
    _data: list[str] = field(default_factory=list[str])

    def feed(self, line: str) -> SseEvent | None:
        """Consume one line.

        Returns:
            The event a blank line completes, else ``None`` (comment lines, ``: keep-alive``, are skipped).
        """
        if not line:
            event = SseEvent(self._name or "message", "\n".join(self._data)) if self._data else None
            self._name, self._data = "", []
            return event
        if line.startswith(":"):
            return None
        key, _, value = line.partition(":")
        value = value.removeprefix(" ")
        if key == "event":
            self._name = value
        elif key == "data":
            self._data.append(value)
        return None
