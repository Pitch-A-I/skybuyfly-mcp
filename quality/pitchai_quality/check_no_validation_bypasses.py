# Copyright (c) 2026 PitchAI. All rights reserved.
"""Reject validation suppressions, source exclusions, and fail-open wiring."""

from __future__ import annotations

import hashlib
import json
import sys
from typing import cast

from pitchai_quality.source_files import NON_SOURCE_DIRECTORY_NAMES, REPOSITORY_ROOT, iter_python_files
from pitchai_quality.strict_policy import INLINE_BYPASS
from pitchai_quality.workflow_policy import STRICT_WORKFLOW_PATH, Violation, workflow_and_toolchain_violations

_QUALITY_ROOT = REPOSITORY_ROOT / "quality"
_MANIFEST_PATH = _QUALITY_ROOT / "portable-enforcement-manifest.json"
_ANTI_BYPASS_PATH = "quality/pitchai_quality/check_no_validation_bypasses.py"
_MANIFEST_RELATIVE_PATH = "quality/portable-enforcement-manifest.json"
_STRICT_WORKFLOW_RELATIVE_PATH = ".github/workflows/python-strict.yml"
_EXPECTED_PORTABLE_MANIFEST_SHA256 = "3d991623646f0061e13b8b445331ee91c7dbe6d9557b08dfb0d9461eb050c95f"
_EXPECTED_MANIFESTED_PATHS = (
    "QUALITY.md",
    "quality/.gitignore",
    "quality/.semgrep.yml",
    "quality/.semgrepignore",
    "quality/pitchai_quality/__init__.py",
    "quality/pitchai_quality/analysis_support.py",
    "quality/pitchai_quality/check.py",
    "quality/pitchai_quality/check_nested_event_loops.py",
    "quality/pitchai_quality/check_no_dense_inline_comprehensions.py",
    "quality/pitchai_quality/check_no_pure_wrapper_functions.py",
    "quality/pitchai_quality/check_no_single_use_one_line_functions.py",
    "quality/pitchai_quality/check_no_vague_signatures.py",
    "quality/pitchai_quality/check_process_edges.py",
    "quality/pitchai_quality/command_display.py",
    "quality/pitchai_quality/gates.py",
    "quality/pitchai_quality/process_edge_marker.py",
    "quality/pitchai_quality/process_edge_model.py",
    "quality/pitchai_quality/process_edge_reraise.py",
    "quality/pitchai_quality/pure_wrapper_index.py",
    "quality/pitchai_quality/pylint_similarity_index.py",
    "quality/pitchai_quality/pure_wrapper_resolution.py",
    "quality/pitchai_quality/ratchet.py",
    "quality/pitchai_quality/ratchet_bootstrap.py",
    "quality/pitchai_quality/ratchet_dependencies.py",
    "quality/pitchai_quality/ratchet_git.py",
    "quality/pitchai_quality/ratchet_model.py",
    "quality/pitchai_quality/ratchet_reports.py",
    "quality/pitchai_quality/ratchet_scope.py",
    "quality/pitchai_quality/ratchet_selection_proof.py",
    "quality/pitchai_quality/single_use_reporting.py",
    "quality/pitchai_quality/source_files.py",
    "quality/pitchai_quality/strict_policy.py",
    "quality/pitchai_quality/workflow_policy.py",
    "quality/pyproject.toml",
    "quality/uv.lock",
)
_CONFIG_PATHS = (
    _QUALITY_ROOT / "pyproject.toml", _QUALITY_ROOT / ".semgrep.yml",
    _QUALITY_ROOT / ".semgrepignore", STRICT_WORKFLOW_PATH,
)


def _portable_disk_paths() -> set[str]:
    paths: set[str] = set()
    for path in _QUALITY_ROOT.rglob("*"):
        relative_parts = path.relative_to(_QUALITY_ROOT).parts
        generated = NON_SOURCE_DIRECTORY_NAMES.intersection(relative_parts) or any(
            part.endswith(".egg-info") for part in relative_parts
        )
        if not generated and (path.is_file() or path.is_symlink()):
            paths.add(path.relative_to(REPOSITORY_ROOT).as_posix())
    for relative in (_STRICT_WORKFLOW_RELATIVE_PATH, "QUALITY.md"):
        path = REPOSITORY_ROOT / relative
        if path.is_file() or path.is_symlink():
            paths.add(relative)
    return paths


def _manifest_files(manifest_bytes: bytes) -> dict[str, str] | None:
    payload_value = cast("object", json.loads(manifest_bytes))
    if not isinstance(payload_value, dict):
        return None
    payload = cast("dict[object, object]", payload_value)
    if set(payload) != {"schema", "files"} or payload.get("schema") != 1:
        return None
    raw_files_value = payload.get("files")
    if not isinstance(raw_files_value, dict):
        return None
    raw_files = cast("dict[object, object]", raw_files_value)
    if not all(isinstance(path, str) and isinstance(digest, str) for path, digest in raw_files.items()):
        return None
    return cast("dict[str, str]", raw_files)


def _portable_manifest_violations() -> list[Violation]:
    if not _MANIFEST_PATH.is_file():
        return [Violation(_MANIFEST_PATH, 1, "portable enforcement manifest is missing")]
    manifest_bytes = _MANIFEST_PATH.read_bytes()
    violations: list[Violation] = []
    if hashlib.sha256(manifest_bytes).hexdigest() != _EXPECTED_PORTABLE_MANIFEST_SHA256:
        violations.append(Violation(_MANIFEST_PATH, 1, "portable enforcement manifest digest changed"))
    files = _manifest_files(manifest_bytes)
    if files is None:
        return [*violations, Violation(_MANIFEST_PATH, 1, "portable enforcement manifest is malformed")]
    if set(files) != set(_EXPECTED_MANIFESTED_PATHS):
        violations.append(Violation(_MANIFEST_PATH, 1, "portable enforcement manifest membership changed"))
    unmanifested = {_ANTI_BYPASS_PATH, _MANIFEST_RELATIVE_PATH, _STRICT_WORKFLOW_RELATIVE_PATH}
    expected_disk_paths = {*_EXPECTED_MANIFESTED_PATHS, *unmanifested}
    disk_paths = _portable_disk_paths()
    violations.extend(
        Violation(REPOSITORY_ROOT / path, 1, "unexpected portable enforcement file")
        for path in sorted(disk_paths - expected_disk_paths)
    )
    violations.extend(
        Violation(REPOSITORY_ROOT / path, 1, "required portable enforcement file is missing")
        for path in sorted(expected_disk_paths - disk_paths)
    )
    for relative in sorted(expected_disk_paths):
        path = REPOSITORY_ROOT / relative
        if path.is_symlink():
            violations.append(Violation(path, 1, "portable enforcement file may not be a symlink"))
    for relative, expected_digest in files.items():
        path = REPOSITORY_ROOT / relative
        actual_digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if not path.is_symlink() and actual_digest is not None and actual_digest != expected_digest:
            violations.append(Violation(path, 1, "portable enforcement file hash changed"))
    return violations


def _inline_violations() -> list[Violation]:
    violations: list[Violation] = []
    for path in (*iter_python_files((REPOSITORY_ROOT,)), *_CONFIG_PATHS):
        if not path.is_file():
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if INLINE_BYPASS.search(line):
                violations.append(Violation(path, line_number, "inline validation suppression is forbidden"))
    return violations


def main() -> int:
    """Validate that every strict gate is complete and fail-closed.

    Returns:
        Zero when the complete policy is intact; otherwise one.
    """
    violations = [
        *_portable_manifest_violations(), *workflow_and_toolchain_violations(), *_inline_violations(),
    ]
    if violations:
        for violation in violations:
            relative = violation.path.relative_to(REPOSITORY_ROOT)
            sys.stderr.write(f"{relative}:{violation.line}: {violation.reason}\n")
        return 1
    sys.stdout.write("ok no_validation_bypasses\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
