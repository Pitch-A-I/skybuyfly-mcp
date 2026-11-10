# Copyright (c) 2026 PitchAI. All rights reserved.
"""Decode full analyzer reports without discarding failed analyses."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, cast

from .check_no_dense_inline_comprehensions import ADVICE
from .ratchet_model import Finding, json_array, json_integer, json_object, json_string
from .source_files import REPOSITORY_ROOT

if TYPE_CHECKING:
    from .ratchet_model import JsonValue

_PYLINT_USAGE_ERROR = 32


def _path(raw: str) -> str:
    path = Path(raw)
    return path.relative_to(REPOSITORY_ROOT).as_posix() if path.is_absolute() else path.as_posix()


def _ruff(value: JsonValue) -> list[Finding]:
    findings: list[Finding] = []
    for raw in json_array(value):
        row = json_object(raw)
        location = json_object(row["location"])
        findings.append(
            Finding(
                _path(json_string(row["filename"])),
                json_integer(location["row"]),
                json_integer(location["column"]),
                json_string(row["code"]),
                json_string(row["message"]),
            ),
        )
    return findings


def _basedpyright(value: JsonValue) -> list[Finding]:
    report = json_object(value)
    findings: list[Finding] = []
    for raw in json_array(report["generalDiagnostics"]):
        row = json_object(raw)
        location = json_object(json_object(row["range"])["start"])
        severity = json_string(row["severity"])
        findings.append(
            Finding(
                _path(json_string(row["file"])),
                json_integer(location["line"]) + 1,
                json_integer(location["character"]) + 1,
                severity + ":" + json_string(row.get("rule", "diagnostic")),
                json_string(row["message"]),
            ),
        )
    return findings


DUPLICATE_CODE = "R0801"


def _duplicate_code(message: str) -> Finding:
    """Key an R0801 group by its sorted "==module:[start:end]" lines alone.

    Pylint attaches every group to whichever module it linted last and prints the code of either copy, so neither
    the reported path nor the excerpt is stable between runs; the duplicated ranges are.

    Returns:
        The group under the pseudo-path "duplicate-code:<first module>".
    """
    ranges = sorted(line for line in message.splitlines() if line.startswith("=="))
    first = ranges[0].removeprefix("==").split(":", 1)[0] if ranges else "unknown"
    return Finding(f"duplicate-code:{first}", 0, 0, DUPLICATE_CODE, "\n".join(ranges))


def _pylint(value: JsonValue) -> list[Finding]:
    report = json_object(value)
    findings: list[Finding] = []
    for raw in json_array(report["messages"]):
        row = json_object(raw)
        if row["type"] == "fatal":
            message = f"Pylint analysis failed: {row['message']}"
            raise RuntimeError(message)
        message_id, message = json_string(row["messageId"]), json_string(row["message"])
        if message_id == DUPLICATE_CODE:
            findings.append(_duplicate_code(message))
            continue
        findings.append(
            Finding(_path(json_string(row["path"])), json_integer(row["line"]), json_integer(row["column"]) + 1,
                    message_id, message),
        )
    return findings


def _semgrep(value: JsonValue) -> list[Finding]:
    report = json_object(value)
    if json_array(report["errors"]):
        message = f"Semgrep analysis incomplete: {report['errors']}"
        raise RuntimeError(message)
    findings: list[Finding] = []
    for raw in json_array(report["results"]):
        row = json_object(raw)
        start = json_object(row["start"])
        extra = json_object(row["extra"])
        findings.append(
            Finding(
                _path(json_string(row["path"])),
                json_integer(start["line"]),
                json_integer(start["col"]),
                json_string(row["check_id"]),
                json_string(extra["message"]),
            ),
        )
    return findings


def _preference(analyzer: str, output: str) -> list[Finding]:
    findings: list[Finding] = []
    if analyzer == "no-dense-inline-comprehensions":
        output = output.removesuffix(f"\n{ADVICE}\n")
    for line in output.splitlines():
        if not line.strip() or line.startswith("ok "):
            continue
        match = re.fullmatch(r"(.+?):(\d+)(?::(\d+))?: (.+)", line)
        if match is None and findings and line[:1].isspace():
            # An indented source excerpt continues the diagnostic above it.
            findings[-1] = replace(findings[-1], message=f"{findings[-1].message}\n{line.strip()}")
            continue
        if match is None:
            message = f"{analyzer}: unrecognized diagnostic: {line}"
            raise ValueError(message)
        path, number, column, reason = match.groups()
        findings.append(Finding(_path(path), int(number), int(column or "0"), analyzer, reason))
    return findings


def decode_report(analyzer: str, returncode: int, stdout: str, stderr: str) -> list[Finding]:
    """Read diagnostics, failing closed on crashes, usage errors or malformed output.

    Returns:
        Every diagnostic emitted by the analyzer.

    Raises:
        RuntimeError: A control failed or an analyzer exited abnormally.
    """
    if analyzer in {"no-validation-bypasses", "analysis-environment"}:
        if returncode != 0:
            message = f"{analyzer}: mandatory control failed\n{stdout}\n{stderr}"
            raise RuntimeError(message)
        return []
    valid_status = returncode in {0, 1}
    if analyzer == "pylint":
        valid_status = 0 <= returncode < _PYLINT_USAGE_ERROR and not returncode & 1
    if not valid_status:
        message = f"{analyzer}: analyzer failed with status {returncode}\n{stderr}"
        raise RuntimeError(message)
    parsers = {"ruff": _ruff, "basedpyright": _basedpyright, "pylint": _pylint, "semgrep": _semgrep}
    if analyzer in parsers:
        findings = parsers[analyzer](cast("JsonValue", json.loads(stdout)))
    else:
        findings = _preference(analyzer, stdout + stderr)
    if returncode != 0 and not findings:
        message = f"{analyzer}: nonzero status without attributable diagnostics"
        raise RuntimeError(message)
    return findings
