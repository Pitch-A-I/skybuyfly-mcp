# Copyright (c) 2026 PitchAI. All rights reserved.
"""Accept a repository's first baseline only when a full scan proves it exact.

A target branch without quality-baseline.json, or whose baseline predates a
newly added gate, has no reviewed ceiling for those gates. The
candidate's first baseline is accepted only when the change cannot move a
finding into an untouched file: it edits portable kit files, or removes inline
validation suppressions and changes nothing else. Such a run is forced to a
full scan, where the new-finding and obsolete-entry checks require the
baseline to equal the analyzers' findings exactly. Every other change to an
unseeded target keeps an empty ceiling.

Run ``python -m pitchai_quality.ratchet_bootstrap PATH...`` to remove the
suppressions from files in exactly the form this verification accepts.
"""

from __future__ import annotations

import ast
import io
import sys
import tokenize
from pathlib import Path
from typing import TYPE_CHECKING, cast

from .ratchet_git import BASELINE_PATH, comparison, git_output
from .source_files import PYTHON_SUFFIXES, REPOSITORY_ROOT
from .strict_policy import EXPECTED_GATES, INLINE_BYPASS

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .ratchet_model import Baseline

KIT_PATHS = frozenset({BASELINE_PATH, "QUALITY.md", ".github/workflows/python-strict.yml"})


def strip_suppressions(source: str) -> str:
    """Cut each suppression comment from its directive to the end of its line.

    Returns:
        The same code; only comment text from each directive onwards is removed.
    """
    lines = source.splitlines(keepends=True)
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        match = INLINE_BYPASS.search(token.string) if token.type == tokenize.COMMENT else None
        if match is None:
            continue
        row, column = token.start
        line = lines[row - 1]
        ending = line[len(line.rstrip("\r\n")) :]
        lines[row - 1] = line[: column + match.start()].rstrip() + ending
    return "".join(lines)


async def seeded_files(ancestor: str, touched: frozenset[str]) -> frozenset[str] | None:
    """Classify a change to an unseeded target for one-time baseline adoption.

    Returns:
        Source files whose only change removes suppressions, or None when any
        other non-kit path changed and the first baseline cannot be trusted.
    """
    tracked = frozenset((await git_output("ls-tree", "-r", "--name-only", "-z", ancestor)).split("\0"))
    stripped: set[str] = set()
    for path in sorted(touched):
        if path in KIT_PATHS or path.startswith("quality/"):
            continue
        candidate = REPOSITORY_ROOT / path
        if Path(path).suffix not in PYTHON_SUFFIXES or path not in tracked or not candidate.is_file():
            return None
        before = await git_output("show", f"{ancestor}:{path}")
        if strip_suppressions(before) != candidate.read_bytes().decode():
            return None
        stripped.add(path)
    return frozenset(stripped)


STRICT_POLICY_PATH = "quality/pitchai_quality/strict_policy.py"


def gates_in_policy(source: str) -> frozenset[str]:
    """Return the EXPECTED_GATES a strict_policy.py source declares.

    Returns:
        The declared gate names, or none when the source declares no gate set.
    """
    for node in ast.parse(source).body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == "EXPECTED_GATES" for target in node.targets):
            return frozenset(cast("tuple[str, ...]", ast.literal_eval(node.value)))
    return frozenset()


def unseeded_gates(target: Baseline | None, base_gates: frozenset[str]) -> list[str]:
    """Return the gates the target baseline has never seeded.

    Only a first adoption (no target baseline) or a gate that the target's own
    strict policy did not yet declare may be unseeded.

    Returns:
        The unseeded gate names, in gate order.

    Raises:
        ValueError: The target baseline lacks a gate that already existed there.
    """
    if target is None:
        return list(EXPECTED_GATES)
    missing = [name for name in EXPECTED_GATES if name not in target]
    existing = [name for name in missing if name in base_gates]
    if existing:
        message = f"target baseline lacks existing gate(s) {', '.join(existing)}; a missing key is never accepted"
        raise ValueError(message)
    return missing


def seeded_ceiling(
    target: Baseline | None, unseeded: list[str], proposed: Baseline, *, kit_only: bool,
) -> Baseline:
    """Combine the target ceiling with the candidate's entries for unseeded gates.

    Returns:
        The candidate's entries for unseeded gates when the change is kit-only (a forced full scan must then
        reproduce them exactly); otherwise an empty ceiling for those gates.
    """
    trusted = dict(target or {})
    for name in unseeded:
        trusted[name] = proposed[name] if kit_only else frozenset[str]()
    return trusted


async def ceiling(base: str, proposed: Baseline) -> tuple[Baseline, frozenset[str], frozenset[str] | None]:
    """Choose this run's trusted ceiling from the target or a first adoption.

    Returns:
        The ceiling, every changed path, and suppression-only files when the
        candidate baseline seeds a gate that a full scan must reproduce.
    """
    target, touched, ancestor = await comparison(base)
    declared = await git_output("ls-tree", base, "--", STRICT_POLICY_PATH)
    base_policy = await git_output("show", f"{base}:{STRICT_POLICY_PATH}") if declared else ""
    unseeded = unseeded_gates(target, gates_in_policy(base_policy))
    if not unseeded:
        return cast("Baseline", target), touched, None
    seeded = await seeded_files(ancestor, touched)
    return seeded_ceiling(target, unseeded, proposed, kit_only=seeded is not None), touched, seeded


def main(argv: Sequence[str] | None = None) -> int:
    """Remove inline suppressions from the named Python files in place.

    Returns:
        Zero after rewriting every named file.
    """
    for raw in argv if argv is not None else sys.argv[1:]:
        path = Path(raw)
        source = path.read_bytes().decode()
        _ = path.write_bytes(strip_suppressions(source).encode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
