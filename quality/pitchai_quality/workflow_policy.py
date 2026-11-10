# Copyright (c) 2026 PitchAI. All rights reserved.
"""Reject fail-open workflow wiring and alternate quality-tool entrypoints."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pitchai_quality.source_files import REPOSITORY_ROOT
from pitchai_quality.strict_policy import EXPECTED_NORMALIZED_STRICT_WORKFLOW_SHA256, workflow_block

if TYPE_CHECKING:
    from pathlib import Path

STRICT_WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "python-strict.yml"
_ANTI_BYPASS_PATH = "quality/pitchai_quality/check_no_validation_bypasses.py"
_DIRECT_TOOLCHAIN = re.compile(
    r"\b(?:ruff|basedpyright|pyright|pylint|semgrep)\b|"
    r"uv\s+run[^\n]*\b(?:quality|check)\b|pitchai_quality\.check",
    re.IGNORECASE,
)
_ACTION_REFERENCE = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)")
_PINNED_ACTION = re.compile(r"^[^@\s]+@[0-9a-fA-F]{40}$")
_CONTINUE_ON_ERROR_TRUE = re.compile(
    r"^\s*continue-on-error:\s*(?:true|[\"']true[\"'])\s*(?:#.*)?$", re.IGNORECASE,
)
_VERIFIER_DIGEST_ASSIGNMENT = re.compile(
    r'^(?P<prefix>\s*expected_verifier_sha256=")(?P<digest>[0-9a-f]{64})(?P<suffix>"\s*)$', re.MULTILINE,
)
_CONFLICTING_ROOT_CONFIGS = (
    ".ruff.toml", "ruff.toml", "pyrightconfig.json", "basedpyrightconfig.json",
    ".pylintrc", "pylintrc", "setup.cfg", "tox.ini",
)


@dataclass(frozen=True)
class Violation:
    """One validation bypass with source location and explanation."""

    path: Path
    line: int
    reason: str


def _strict_workflow_violations() -> list[Violation]:
    if not STRICT_WORKFLOW_PATH.is_file():
        return []
    workflow_text = STRICT_WORKFLOW_PATH.read_text(encoding="utf-8")
    violations: list[Violation] = []
    if workflow_block(workflow_text, "on") != (
        "pull_request:", "push:", "branches: [staging, main]",
        "schedule:", "- cron: '23 2 * * *'", "workflow_dispatch:",
    ):
        violations.append(Violation(STRICT_WORKFLOW_PATH, 1, "strict workflow event contract differs"))
    if workflow_block(workflow_text, "permissions") != ("contents: read",):
        violations.append(Violation(STRICT_WORKFLOW_PATH, 1, "strict workflow permissions must be read-only contents"))
    stripped_lines = tuple(line.strip() for line in workflow_text.splitlines())
    required_commands = (
        "run: uv sync --project quality --python 3.12 --frozen",
        "run: UV_PROJECT_ENVIRONMENT=quality/analysis/.venv uv sync --python 3.12 --frozen --all-groups",
        "run: uv run --project quality --python 3.12 --frozen python -m pitchai_quality.ratchet",
    )
    for command in required_commands:
        if stripped_lines.count(command) != 1:
            violations.append(Violation(STRICT_WORKFLOW_PATH, 1, "strict workflow frozen commands changed"))
            break
    digest_matches = list(_VERIFIER_DIGEST_ASSIGNMENT.finditer(workflow_text))
    if len(digest_matches) != 1:
        violations.append(Violation(STRICT_WORKFLOW_PATH, 1, "strict workflow verifier trust anchor is missing"))
        return violations
    match = digest_matches[0]
    verifier_path = REPOSITORY_ROOT / _ANTI_BYPASS_PATH
    actual_verifier_digest = hashlib.sha256(verifier_path.read_bytes()).hexdigest()
    if match.group("digest") != actual_verifier_digest:
        violations.append(Violation(STRICT_WORKFLOW_PATH, 1, "strict workflow verifier trust anchor is stale"))
    workflow_before_digest = workflow_text[: match.start("digest")]
    workflow_after_digest = workflow_text[match.end("digest") :]
    normalized_workflow = f"{workflow_before_digest}<VERIFIER_SHA256>{workflow_after_digest}"
    normalized_digest = hashlib.sha256(normalized_workflow.encode()).hexdigest()
    if normalized_digest != EXPECTED_NORMALIZED_STRICT_WORKFLOW_SHA256:
        violations.append(Violation(STRICT_WORKFLOW_PATH, 1, "strict workflow semantics changed"))
    return violations


def workflow_and_toolchain_violations() -> list[Violation]:
    """Check alternate configs, every workflow's toolchain wiring, and the strict workflow contract.

    Returns:
        Every violation found, in a stable order.
    """
    violations: list[Violation] = []
    for relative in _CONFLICTING_ROOT_CONFIGS:
        path = REPOSITORY_ROOT / relative
        if path.exists():
            violations.append(Violation(path, 1, "alternate root quality-tool configuration is forbidden"))
    for workflow in sorted((REPOSITORY_ROOT / ".github" / "workflows").glob("*")):
        if workflow.suffix not in {".yml", ".yaml"}:
            continue
        workflow_text = workflow.read_text(encoding="utf-8")
        if workflow != STRICT_WORKFLOW_PATH and _DIRECT_TOOLCHAIN.search(workflow_text):
            violations.append(Violation(workflow, 1, "alternate workflow quality-tool entrypoint is forbidden"))
        for line_number, line in enumerate(workflow_text.splitlines(), start=1):
            match = _ACTION_REFERENCE.match(line)
            action = match.group(1).strip("\"'") if match is not None else None
            if action is not None and not action.startswith("./") and _PINNED_ACTION.fullmatch(action) is None:
                violations.append(Violation(workflow, line_number, f"mutable workflow action reference: {action}"))
            if _CONTINUE_ON_ERROR_TRUE.match(line):
                violations.append(Violation(workflow, line_number, "workflow continue-on-error is forbidden"))
    return [*violations, *_strict_workflow_violations()]
