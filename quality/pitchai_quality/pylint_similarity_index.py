# Copyright (c) 2026 PitchAI. All rights reserved.
"""Make Pylint's duplicate-code check deterministic, and index its candidate pairs.

With parallel jobs, Pylint hands each worker's files to the similarity step in
the order the workers finish, and which duplicate groups it reports depends on
that order: two scans of the same tree differed in about half of their R0801
findings, which no finding baseline can hold. This checker sorts the files by
module name and content before comparing, so every run and every worker split
reports the same groups. Two files can only produce a similarity when they share
a hashed chunk, so it compares exactly those pairs, in that sorted order, with
Pylint's unchanged comparison routine (potAIto's index). Messages, options and
thresholds are those of the stock checker.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pylint.checkers.symilar import SimilaritiesChecker, hash_lineset

if TYPE_CHECKING:
    from collections.abc import Generator

    from pylint.checkers.symilar import Commonality, LinesChunk, LineSet
    from pylint.lint import PyLinter


# The kit requires byte-identical copies of its process-edge marker inside each package and checks them by hash, so
# extra identical copies are not duplication. One copy stays, so a modified copy is still compared with the original.
MARKER = Path(__file__).with_name("process_edge_marker.py")


def _without_extra_marker_copies(linesets: list[LineSet]) -> list[LineSet]:
    """Drop every lineset byte-identical to the kit marker except the first.

    Returns:
        The linesets to compare, in their original order.
    """
    marker = MARKER.read_text(encoding="utf-8") if MARKER.is_file() else None
    kept: list[LineSet] = []
    seen = False
    for lineset in linesets:
        identical = marker is not None and "".join(lineset.real_lines) == marker
        if identical and seen:
            continue
        seen = seen or identical
        kept.append(lineset)
    return kept


class IndexedSimilaritiesChecker(SimilaritiesChecker):
    """Stock duplicate-code checker over sorted files that skips pairs without a common chunk."""

    def _iter_sims(self) -> Generator[Commonality]:
        self.linesets.sort(key=lambda lineset: (lineset.name, "".join(lineset.real_lines)))
        self.linesets[:] = _without_extra_marker_copies(self.linesets)
        minimum = cast("int", self.namespace.min_similarity_lines)
        owners: defaultdict[LinesChunk, list[int]] = defaultdict(list)
        for position, lineset in enumerate(self.linesets):
            for chunk in hash_lineset(lineset, minimum)[0]:
                owners[chunk].append(position)
        partners: list[set[int]] = [set() for _ in self.linesets]
        for positions in owners.values():
            for offset, position in enumerate(positions):
                partners[position].update(positions[offset + 1 :])
        for position, lineset in enumerate(self.linesets):
            for partner in sorted(partners[position]):
                yield from self._find_common(lineset, self.linesets[partner])


def register(linter: PyLinter) -> None:
    """Replace the registered stock similarity checker with the indexed one."""
    for checker in linter.get_checkers():
        if isinstance(checker, SimilaritiesChecker) and not isinstance(checker, IndexedSimilaritiesChecker):
            checker.__class__ = IndexedSimilaritiesChecker
