# Copyright (c) 2026 PitchAI. All rights reserved.
"""Discover the repository's complete first-party Python source surface."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pitchai_quality.strict_policy import EXPECTED_NON_SOURCE_DIRECTORIES

if TYPE_CHECKING:
    from collections.abc import Iterable

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SUFFIXES = frozenset({".py", ".pyi"})
RUNTIME_PYTHON_SUFFIXES = frozenset({".py"})
NON_SOURCE_DIRECTORY_NAMES = EXPECTED_NON_SOURCE_DIRECTORIES
# Third-party trees vendored at the repository root only: the installer-managed Codex system skills.
# A directory of the same name anywhere else is still first-party source (QUALITY.md, "Vendored code").
VENDORED_ROOT_DIRECTORIES = frozenset({".system"})


def is_repository_source(path: Path, *, suffixes: frozenset[str] = PYTHON_SUFFIXES) -> bool:
    """Return whether a file belongs to the checked first-party source surface."""
    resolved = path.resolve(strict=False)
    inside = resolved.is_relative_to(REPOSITORY_ROOT)
    relative_parts = resolved.relative_to(REPOSITORY_ROOT).parts if inside else resolved.parts
    is_source_file = resolved.is_file() and resolved.suffix in suffixes
    first_party = not (inside and bool(VENDORED_ROOT_DIRECTORIES.intersection(relative_parts[:1])))
    return is_source_file and first_party and not NON_SOURCE_DIRECTORY_NAMES.intersection(relative_parts)


def iter_python_files(
    paths: Iterable[Path],
    *,
    suffixes: frozenset[str] = PYTHON_SUFFIXES,
) -> tuple[Path, ...]:
    """Return every unique checked Python file below files or directories."""
    discovered: list[Path] = []
    for path in paths:
        resolved = path.resolve(strict=False)
        if is_repository_source(resolved, suffixes=suffixes):
            discovered.append(resolved)
            continue
        if not resolved.is_dir():
            continue
        descendants = resolved.rglob("*")
        candidates = (candidate for candidate in descendants if candidate.suffix in suffixes)
        source_candidates = (
            candidate for candidate in candidates if is_repository_source(candidate, suffixes=suffixes)
        )
        discovered.extend(source_candidates)
    return tuple(dict.fromkeys(sorted(discovered)))
