# Copyright (c) 2026 PitchAI. All rights reserved.
"""Run every strict analyzer and enforce the reviewed Git debt ratchet."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, cast

import anyio

from .gates import PYTHON_PATHS, gates
from .ratchet_bootstrap import ceiling
from .ratchet_git import BASELINE_PATH, event_base
from .ratchet_model import baseline_text, json_array, json_object, ratchet_errors, read_baseline
from .ratchet_reports import decode_report
from .ratchet_scope import selected_paths, source_changes
from .source_files import REPOSITORY_ROOT
from .strict_policy import EXPECTED_GATES

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .gates import Gate
    from .ratchet_model import Baseline, JsonValue

USAGE_GATES = frozenset({"no-single-use-one-line-functions", "no-pure-wrapper-functions"})


def report_command(gate: Gate) -> tuple[str, ...]:
    """Add serialization options to the canonical analyzer command.

    Returns:
        The same gate with machine-readable diagnostics; Pylint uses two workers.
    """
    formats = {
        "ruff": ("--output-format=json",),
        "basedpyright": ("--outputjson",),
        "pylint": ("--output-format=json2", "--jobs=2"),
        "semgrep": ("--json",),
    }
    return (*gate.command, *formats.get(gate.name, ()))


# Import resolution depends on which modules a parallel Pylint worker linted first when two top-level modules share
# a name, so these rules run in one serial pass; the parallel pass runs every other rule.
SERIAL_PYLINT_RULES = "import-error,no-name-in-module,cyclic-import"


def pylint_commands(gate: Gate) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split Pylint into a parallel pass and a serial pass for the order-dependent import rules.

    Returns:
        The parallel command and the serial command, both with JSON output.
    """
    base = report_command(gate)
    serial = (*base, "--jobs=1", "--disable=all", f"--enable={SERIAL_PYLINT_RULES}")
    return (*base, f"--disable={SERIAL_PYLINT_RULES}"), serial


async def _run_pylint(gate: Gate, env: dict[str, str]) -> tuple[tuple[str, ...], int, str, str]:
    parallel, serial = pylint_commands(gate)
    first = await anyio.run_process(parallel, cwd=REPOSITORY_ROOT, env=env, check=False)
    second = await anyio.run_process(serial, cwd=REPOSITORY_ROOT, env=env, check=False)
    messages: list[JsonValue] = []
    for process in (first, second):
        report = json_object(cast("JsonValue", json.loads(process.stdout.decode() or "{}")))
        messages.extend(json_array(report.get("messages", [])))
    stdout = json.dumps({"messages": messages})
    stderr = first.stderr.decode() + second.stderr.decode()
    return (*parallel, "&&", *serial), first.returncode | second.returncode, stdout, stderr


async def execute_gate(gate: Gate, output: Path, env: dict[str, str]) -> tuple[str, int, str, str]:
    """Run an analyzer and retain its raw output and elapsed time.

    Returns:
        Gate name, exit status, standard output and standard error.
    """
    started = time.monotonic()
    if gate.name == "pylint":
        command, returncode, stdout, stderr = await _run_pylint(gate, env)
    else:
        command = report_command(gate)
        process = await anyio.run_process(command, cwd=REPOSITORY_ROOT, env=env, check=False)
        returncode, stdout, stderr = process.returncode, process.stdout.decode(), process.stderr.decode()
    _ = (output / f"{gate.name}.stdout").write_text(stdout, encoding="utf-8")
    _ = (output / f"{gate.name}.stderr").write_text(stderr, encoding="utf-8")
    receipt = {"command": command, "returncode": returncode, "seconds": time.monotonic() - started}
    _ = (output / f"{gate.name}.receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    return gate.name, returncode, stdout, stderr


def analyzer_environment() -> dict[str, str]:
    """Return the environment every analyzer runs in.

    Pylint's cyclic-import search walks hash-ordered sets, so the cycles it reports change with Python's hash
    seed. A fixed seed keeps the fingerprints the same for every run of the same tree.

    Returns:
        The process environment with the kit's import path, Semgrep metrics off and hash seed 0.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(str(REPOSITORY_ROOT / relative) for relative in PYTHON_PATHS)
    env["SEMGREP_SEND_METRICS"] = "off"
    env["PYTHONHASHSEED"] = "0"
    return env


async def collect_reports(output: Path, paths: tuple[Path, ...] | None = None) -> Baseline:
    """Execute all gates and retain raw reports, including analyzer failures.

    Returns:
        Complete diagnostic fingerprints; malformed reports raise after all tools run.
    """
    await anyio.Path(output).mkdir(parents=True, exist_ok=True)
    env = analyzer_environment()
    current: Baseline = {name: frozenset() for name in EXPECTED_GATES}
    completed: list[tuple[str, int, str, str]] = []
    commands = gates(paths or ())
    if paths:
        # Usage-counting analyzers judge a definition by its callers anywhere in
        # the repository. A closure would hide callers and invent findings, so
        # they read all source whenever any Python source is affected.
        full = gates(())
        commands |= {name: full[name] for name in USAGE_GATES.intersection(EXPECTED_GATES)}
    for name in EXPECTED_GATES:
        no_source = paths == () and name not in {"no-validation-bypasses", "analysis-environment"}
        if no_source or commands[name].skip_reason:
            receipt = {"command": (), "returncode": 0, "reason": "dependency closure contains no Python source"}
            _ = (output / f"{name}.receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
            continue
        _ = sys.stdout.write(
            f"==> {name}: {'full-source' if paths is None or name in USAGE_GATES else 'dependency-closure'} analysis\n",
        )
        sys.stdout.flush()
        completed.append(await execute_gate(commands[name], output, env))
    # Run every tool before decoding. Invalid output propagates with its original
    # traceback, while all other analyzer reports remain available for diagnosis.
    for name, returncode, stdout, stderr in completed:
        findings = decode_report(name, returncode, stdout, stderr)
        normalized = [
            replace(finding, message=finding.message.replace(str(REPOSITORY_ROOT) + "/", "")) for finding in findings
        ]
        current[name] = frozenset(finding.fingerprint for finding in normalized)
        _ = sys.stdout.write(f"<== {name}: {len(findings)} findings, {len(current[name])} exact identities\n")
    _ = (output / "current.json").write_text(baseline_text(current), encoding="utf-8")
    return current


def shrunk(proposed: Baseline, current: Baseline, examined: frozenset[str] | None) -> Baseline:
    """Drop resolved entries while keeping debt outside an incremental examination.

    Returns:
        A subset of the proposed baseline.
    """
    result: Baseline = {}
    for name in EXPECTED_GATES:
        retained = proposed[name] & current[name]
        if examined is not None:
            retained |= frozenset(key for key in proposed[name] if key.split("\t", maxsplit=1)[0] not in examined)
        result[name] = retained
    return result


async def run(base: str, output: Path, *, shrink: bool, incremental: bool = False) -> int:
    """Validate baseline history, run all analyzers, and check touched-file debt.

    Returns:
        Zero only for a complete, passing ratchet.
    """
    proposed = read_baseline((REPOSITORY_ROOT / BASELINE_PATH).read_text(encoding="utf-8"))
    trusted, touched, seeded = await ceiling(base, proposed)
    if seeded is not None:
        # A first adoption is only trusted when a full scan reproduces it exactly.
        incremental = False
        _ = sys.stdout.write(f"Bootstrap: full scan of an unseeded target; {len(seeded)} suppression-only files.\n")
    if any(proposed[name] - trusted[name] for name in EXPECTED_GATES):
        _ = sys.stderr.write("Baseline growth is forbidden; entries may only be removed.\n")
        return 1
    paths = await selected_paths(base, touched) if incremental else None
    examined = None
    if paths is not None:
        examined = frozenset(str(path.relative_to(REPOSITORY_ROOT)) for path in paths)
    # Deleted source is also examined: its historical debt must be removed.
    if examined is not None:
        examined |= source_changes(touched)
    started = time.monotonic()
    current = await collect_reports(output, paths)
    if shrink:
        proposed = shrunk(proposed, current, examined)
        _ = (REPOSITORY_ROOT / BASELINE_PATH).write_text(baseline_text(proposed), encoding="utf-8")
    # Suppression-only files keep their now-visible debt in the first baseline.
    errors = ratchet_errors(trusted, proposed, current, touched - (seeded or frozenset()), examined)
    report = json.dumps(
        {
            "base": base,
            "mode": "incremental" if incremental else "full",
            "bootstrap": None if seeded is None else sorted(seeded),
            "examined": None if examined is None else sorted(examined),
            "analyzer_seconds": time.monotonic() - started,
            "touched": sorted(touched),
            "errors": errors,
            "counts": {name: len(current[name]) for name in EXPECTED_GATES},
        },
        indent=2,
    )
    _ = (output / "summary.json").write_text(report + "\n", encoding="utf-8")
    if errors:
        _ = sys.stderr.write("\n".join(errors) + "\nQuality ratchet FAILED.\n")
        return 1
    _ = sys.stdout.write("Quality ratchet PASSED: no new findings; every touched file is clean.\n")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Parse local/CI inputs and run the event-appropriate mandatory ratchet.

    Returns:
        Ratchet exit status.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--base", help="Local comparison commit; CI defaults to its event target.")
    _ = parser.add_argument("--output", type=Path, default=Path(".quality-reports"))
    _ = parser.add_argument("--shrink", action="store_true", help="Remove resolved entries; never add debt.")
    _ = parser.add_argument("--incremental", action="store_true", help="Use PR dependency closure for a local proof.")
    args = parser.parse_args(list(argv) if argv is not None else None)
    base = cast("str | None", args.base) or event_base()
    output = cast("Path", args.output)
    shrink = cast("bool", args.shrink)
    incremental = os.environ.get("GITHUB_EVENT_NAME") == "pull_request" or cast("bool", args.incremental)
    return anyio.run(partial(run, shrink=shrink, incremental=incremental), base, output)


if __name__ == "__main__":
    raise SystemExit(main())
