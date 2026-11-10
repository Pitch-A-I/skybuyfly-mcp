# Copyright (c) 2026 PitchAI. All rights reserved.
"""Choose PR dependency closure while retaining full scheduled and push proofs."""

from __future__ import annotations

from pathlib import Path

from .ratchet_dependencies import dependency_closure
from .ratchet_git import git_output
from .ratchet_selection_proof import prove_selection
from .source_files import NON_SOURCE_DIRECTORY_NAMES, PYTHON_SUFFIXES, REPOSITORY_ROOT, iter_python_files


def source_changes(touched: frozenset[str]) -> frozenset[str]:
    """Return changed Python paths within the existing source-directory contract."""
    python_paths = (path for path in touched if Path(path).suffix in PYTHON_SUFFIXES)
    source_paths = (path for path in python_paths if not NON_SOURCE_DIRECTORY_NAMES.intersection(Path(path).parts))
    return frozenset(source_paths)


def changes_analysis(path: str) -> bool:
    """Return whether a dependency/configuration change affects all Python files."""
    item = Path(path)
    configuration = item.name in {
        "pyproject.toml", "uv.lock", "poetry.lock", "Pipfile", "Pipfile.lock",
        "setup.py", "setup.cfg", "tox.ini", "pyrightconfig.json", "basedpyrightconfig.json",
        "ruff.toml", ".ruff.toml", ".pylintrc", "pylintrc", ".semgrep.yml", ".semgrepignore",
    }
    requirements = item.name.startswith("requirements") and item.suffix in {".txt", ".in"}
    return path.startswith("quality/") or configuration or requirements


async def selected_paths(base: str, touched: frozenset[str]) -> tuple[Path, ...]:
    """Calculate source closure from the working tree and changed predecessor files.

    Returns:
        Existing Python paths; an empty tuple means no source was affected.
    """
    configuration = any(changes_analysis(path) for path in touched)
    changed = source_changes(touched)
    if not (configuration or changed):
        return ()
    paths = iter_python_files((REPOSITORY_ROOT,))
    if configuration:
        return paths
    prove_selection()
    sources = {str(path.relative_to(REPOSITORY_ROOT)): path.read_text(encoding="utf-8") for path in paths}
    ancestor = (await git_output("merge-base", base, "HEAD")).strip()
    old_paths = frozenset((await git_output("ls-tree", "-r", "--name-only", "-z", ancestor)).split("\0"))
    previous: dict[str, str] = {}
    for path in sorted(changed & old_paths):
        previous[path] = await git_output("show", f"{ancestor}:{path}")
    selected = dependency_closure(sources, previous, changed)
    return tuple(REPOSITORY_ROOT / path for path in sorted(selected))
