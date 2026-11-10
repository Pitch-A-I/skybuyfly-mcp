# Copyright (c) 2026 PitchAI. All rights reserved.
"""Bind ratchet comparisons to Git history and the CI event's target commit."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, cast

import anyio

from .ratchet_model import json_object, json_string, read_baseline
from .source_files import REPOSITORY_ROOT

if TYPE_CHECKING:
    from .ratchet_model import Baseline, JsonValue

BASELINE_PATH = "quality-baseline.json"


async def git_output(*arguments: str) -> str:
    """Execute a read-only Git query, preserving its failure at the process edge.

    Returns:
        UTF-8 command output.
    """
    result = await anyio.run_process(("git", *arguments), cwd=REPOSITORY_ROOT)
    return result.stdout.decode()


def event_base() -> str:
    """Resolve the trusted GitHub event base; local callers must provide a base.

    Returns:
        The target SHA, never an arbitrary ref supplied by the candidate source.
    """
    event_path = Path(os.environ["GITHUB_EVENT_PATH"])
    event = json_object(cast("JsonValue", json.loads(event_path.read_text(encoding="utf-8"))))
    if "pull_request" in event:
        return json_string(json_object(json_object(event["pull_request"])["base"])["sha"])
    before = json_string(event.get("before", ""))
    if before and set(before) != {"0"}:
        return before
    if os.environ.get("GITHUB_EVENT_NAME") in {"schedule", "workflow_dispatch"}:
        return "HEAD"
    return "origin/staging"


async def trusted_baseline(revision: str) -> Baseline | None:
    """Read the target branch's committed ceiling.

    Returns:
        Trusted finding sets, or None when the target has never been seeded.
    """
    if not await git_output("ls-tree", revision, "--", BASELINE_PATH):
        return None
    return read_baseline(await git_output("show", f"{revision}:{BASELINE_PATH}"), partial=True)


async def comparison(base: str) -> tuple[Baseline | None, frozenset[str], str]:
    """Load the target ceiling and all modified/renamed/uncommitted paths.

    Returns:
        The trusted baseline, complete changed-file set and merge base.
    """
    revision = (await git_output("rev-parse", "--verify", f"{base}^{{commit}}")).strip()
    trusted = await trusted_baseline(revision)
    ancestor = (await git_output("merge-base", revision, "HEAD")).strip()
    changed = await git_output("diff", "--no-renames", "--name-only", "-z", ancestor)
    untracked = await git_output("ls-files", "--others", "--exclude-standard", "-z")
    touched = frozenset(path for path in (changed + untracked).split("\0") if path)
    return trusted, touched, ancestor
