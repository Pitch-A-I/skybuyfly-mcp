# Copyright (c) 2026 PitchAI. All rights reserved.
"""Exact diagnostic identities and the monotonically shrinking debt contract."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import cast

from .strict_policy import EXPECTED_GATES

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None
type Baseline = dict[str, frozenset[str]]
_FINGERPRINT_FIELDS = 5
_DIGEST_LENGTH = hashlib.sha256().digest_size * 2


def json_object(value: JsonValue) -> dict[str, JsonValue]:
    """Decode an object at the analyzer/manifest input boundary.

    Returns:
        The checked object.

    Raises:
        TypeError: The input is not a JSON object.
    """
    if not isinstance(value, dict):
        message = "expected JSON object"
        raise TypeError(message)
    return value


def json_array(value: JsonValue) -> list[JsonValue]:
    """Decode an array at the analyzer/manifest input boundary.

    Returns:
        The checked array.

    Raises:
        TypeError: The input is not an array.
    """
    if not isinstance(value, list):
        message = "expected JSON array"
        raise TypeError(message)
    return value


def json_string(value: JsonValue) -> str:
    """Decode a string at the analyzer/manifest input boundary.

    Returns:
        The checked string.

    Raises:
        TypeError: The input is not a string.
    """
    if not isinstance(value, str):
        message = "expected JSON string"
        raise TypeError(message)
    return value


def json_integer(value: JsonValue) -> int:
    """Decode a coordinate at the analyzer input boundary.

    Returns:
        The checked integer.

    Raises:
        TypeError: The input is not an integer.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        message = "expected JSON integer"
        raise TypeError(message)
    return value


@dataclass(frozen=True)
class Finding:
    """One diagnostic, before its message is represented by a SHA-256 digest."""

    path: str
    line: int
    column: int
    rule: str
    message: str

    @property
    def fingerprint(self) -> str:
        """Exact identity with inspectable path, position and rule."""
        digest = hashlib.sha256(self.message.encode()).hexdigest()
        return f"{self.path}\t{self.line}\t{self.column}\t{self.rule}\t{digest}"


def _validate_fingerprint(analyzer: str, entry: str) -> None:
    parts = entry.split("\t")
    if len(parts) != _FINGERPRINT_FIELDS:
        message = f"{analyzer}: malformed fingerprint"
        raise ValueError(message)
    path, line, column, rule, digest = parts
    valid_path = bool(path) and not PurePosixPath(path).is_absolute() and ".." not in PurePosixPath(path).parts
    valid_location = line.isdecimal() and column.isdecimal()
    valid_digest = len(digest) == _DIGEST_LENGTH and all(char in "0123456789abcdef" for char in digest)
    if not (valid_path and valid_location and valid_digest and rule):
        message = f"{analyzer}: invalid fingerprint fields"
        raise ValueError(message)


def read_baseline(source: str, *, partial: bool = False) -> Baseline:
    """Read a canonical baseline, rejecting malformed or duplicated entries.

    A partial read accepts a target-branch baseline that predates a newly added
    gate; the ceiling then treats that gate as unseeded.

    Returns:
        Exact finding sets for every analyzer present, including empty control gates.

    Raises:
        ValueError: Schema, analyzer membership or finding identity is invalid.
    """
    payload = json_object(cast("JsonValue", json.loads(source)))
    if set(payload) != {"schema", "analyzers"} or payload["schema"] != 1:
        message = "invalid baseline schema"
        raise ValueError(message)
    analyzers = json_object(payload["analyzers"])
    present = set(analyzers)
    if present - set(EXPECTED_GATES) or (not partial and present != set(EXPECTED_GATES)):
        message = "baseline must contain every analyzer"
        raise ValueError(message)
    baseline: Baseline = {}
    for analyzer, raw in analyzers.items():
        raw_entries = json_array(raw)
        entries = [json_string(entry) for entry in raw_entries]
        if entries != sorted(set(entries)):
            message = f"{analyzer}: baseline entries must be unique and sorted"
            raise ValueError(message)
        for entry in entries:
            _validate_fingerprint(analyzer, entry)
        baseline[analyzer] = frozenset(entries)
    for control in ("no-validation-bypasses", "analysis-environment"):
        if baseline.get(control):
            message = f"{control}: control failures cannot be baselined"
            raise ValueError(message)
    return baseline


def baseline_text(baseline: Baseline) -> str:
    """Serialize the complete baseline deterministically.

    Returns:
        Canonical JSON suitable for review in Git.
    """
    ordered = sorted(baseline.items())
    analyzers = {name: sorted(entries) for name, entries in ordered}
    return json.dumps({"schema": 1, "analyzers": analyzers}, indent=2) + "\n"


def ratchet_errors(
    trusted: Baseline, proposed: Baseline, current: Baseline, touched: frozenset[str],
    examined: frozenset[str] | None = None,
) -> list[str]:
    """Reject growth, new findings, touched-file debt and retained obsolete debt.

    Returns:
        All violations; an empty list means the debt ratchet passes.
    """
    errors: list[str] = []
    for analyzer in EXPECTED_GATES:
        additions = proposed[analyzer] - trusted[analyzer]
        new = current[analyzer] - proposed[analyzer]
        stale = proposed[analyzer] - current[analyzer]
        if examined is not None:
            stale = frozenset(key for key in stale if key.split("\t", maxsplit=1)[0] in examined)
        dirty = {key for key in current[analyzer] if key.split("\t", maxsplit=1)[0] in touched}
        for category, findings in (
            ("baseline addition", additions),
            ("new finding", new),
            ("touched-file finding", dirty),
            ("remove obsolete baseline entry", stale),
        ):
            errors.extend(f"{analyzer}: {category}: {key}" for key in sorted(findings))
    return errors
