# Copyright (c) 2026 PitchAI. All rights reserved.
"""Immutable values that define the repository Python quality policy."""

from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

type TomlScalar = str | int | float | bool | date | datetime | time
type TomlValue = TomlScalar | list[TomlValue] | dict[str, TomlValue]


class PolicyConfigurationError(TypeError):
    """A malformed value in the immutable strict quality policy."""

    def __init__(self, name: str, expected: str) -> None:
        """Initialize a policy-shape failure."""
        message = f"{name} must be {expected}"
        super().__init__(message)


# Ruff honours isort's skip directives even under --ignore-noqa (isort: skip_file switches I001 off for a file).
INLINE_BYPASS = re.compile(
    r"#\s*(?:noqa\b|type:\s*ignore\b|ruff:\s*(?:ignore|noqa)\b|isort\s*:\s*(?:skip_file|skip|off)\b|"
    r"pylint:\s*(?:disable(?:-next)?|skip-file)\b|nosem(?:grep)?\b|pyright:\s*)",
    re.IGNORECASE,
)
EXPECTED_GATES = (
    "no-validation-bypasses",
    "nested-event-loops",
    "no-vague-signatures",
    "no-single-use-one-line-functions",
    "no-pure-wrapper-functions",
    "no-dense-inline-comprehensions",
    "process-edges",
    "ruff",
    "basedpyright",
    "pylint",
    "semgrep",
)
EXPECTED_NON_SOURCE_DIRECTORIES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".semgrep",
        ".venv",
        ".vscode",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "venv",
    },
)
EXPECTED_RUFF: Mapping[str, TomlValue] = {
    "line-length": 120,
    "target-version": "py312",
    "preview": True,
    "indent-width": 4,
    "lint": {
        "select": ["ALL"],
        "preview": True,
        "fixable": ["ALL"],
        "unfixable": [],
        "mccabe": {"max-complexity": 20},
        "pydocstyle": {"convention": "google"},
        "flake8-annotations": {"mypy-init-return": True},
        "flake8-type-checking": {"quote-annotations": True, "strict": True},
        "pylint": {"max-nested-blocks": 4, "max-locals": 30},
    },
    "format": {"docstring-code-format": False},
}
EXPECTED_BASEDPYRIGHT_CORE: Mapping[str, TomlValue] = {
    "typeCheckingMode": "strict",
    "failOnWarnings": True,
    "include": [".."],
    "pythonVersion": "3.12",
    "pythonPlatform": "All",
    "venvPath": "analysis",
    "venv": ".venv",
    "allowedUntypedLibraries": [],
    "reportAny": "error",
    "reportExplicitAny": "error",
    "reportInvalidCast": "error",
    "reportImplicitRelativeImport": "error",
    "reportPrivateLocalImportUsage": "error",
    "reportUnusedParameter": "error",
    "reportImplicitAbstractClass": "error",
    "reportInvalidAbstractMethod": "error",
    "reportIncompatibleUnannotatedOverride": "error",
    "reportUnannotatedClassAttribute": "error",
}
EXPECTED_PYLINT: Mapping[str, TomlValue] = {
    "main": {
        "jobs": 0,
        "reports": "no",
        "init-hook": "import glob,sys;sys.path+=sorted(glob.glob('quality/analysis/.venv/lib/*/site-packages'))",
        "load-plugins": [
            "pylint.extensions.broad_try_clause",
            "pylint.extensions.overlapping_exceptions",
            "pitchai_quality.pylint_similarity_index",
        ],
    },
    "design": {"exclude-too-few-public-methods": ["typing\\.Protocol", "typing_extensions\\.Protocol"]},
    "similarities": {"min-similarity-lines": 6},
    "format": {"max-line-length": 120, "max-module-lines": 250},
}
EXPECTED_PROJECT: Mapping[str, TomlValue] = {
    "name": "pitchai-repository-quality",
    "version": "1.0.0",
    "description": "Fail-closed PitchAI Python quality gate",
    "requires-python": ">=3.12,<3.13",
    "dependencies": [
        "anyio==4.13.0",
        "basedpyright==1.39.8",
        "pylint==4.0.5",
        "ruff==0.15.17",
        "semgrep==1.166.0",
    ],
    "scripts": {"check": "pitchai_quality.check:main"},
}
EXPECTED_BUILD_SYSTEM: Mapping[str, TomlValue] = {
    "requires": ["setuptools==80.10.2"],
    "build-backend": "setuptools.build_meta",
}
EXPECTED_NORMALIZED_STRICT_WORKFLOW_SHA256 = "1cdf3d84aa7b0fb0ffec3d23e2e728dfc824d36065ce53055bad87b8a2fdd82b"
RUFF_ARGUMENTS = (
    "check",
    "--no-cache",
    "--ignore-noqa",
    "--no-respect-gitignore",
    "--no-force-exclude",
    "--select",
    "ALL",
    "--config",
    "quality/pyproject.toml",
)
SEMGREP_ARGUMENTS = (
    "--error",
    "--strict",
    "--disable-nosem",
    "--no-git-ignore",
    "--x-ignore-semgrepignore-files",
    "--max-target-bytes=0",
    "--timeout=0",
    "--timeout-threshold=0",
    "--disable-version-check",
    "--metrics=off",
)


def workflow_block(workflow_text: str, heading: str) -> tuple[str, ...] | None:
    """Read an exact top-level workflow block.

    Returns:
        Non-comment entries, or None for a missing/duplicate heading.
    """
    lines = workflow_text.splitlines()
    indexes: list[int] = []
    for index, line in enumerate(lines):
        if line == f"{heading}:":
            indexes.append(index)
    if len(indexes) != 1:
        return None
    block: list[str] = []
    for line in lines[indexes[0] + 1 :]:
        if line and not line.startswith(" "):
            break
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            block.append(stripped)
    return tuple(block)
