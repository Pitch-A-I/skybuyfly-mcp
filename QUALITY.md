# Python Quality Gate

Run the repository's complete fail-closed Python gate with:

```sh
uv run --project quality --python 3.12 --frozen check
```

The aggregate runs the anti-bypass policy, all six PitchAI Python preference
checkers, Ruff with every rule selected, BasedPyright in strict mode with fatal
warnings, full Pylint with a score floor of 10 and a 250-line module ceiling,
and Semgrep `ERROR` rules. It checks every repository Python and stub file,
including tests and tools. Only generated caches, virtual environments, build
outputs, and other non-source directories are omitted from discovery.

Vendored code: the `.system/` tree at the repository root holds the Codex
system skills, third-party code that the skill installer manages (its
`.codex-system-skills.marker` names it), so the gate leaves that one root
tree out (Infrastructure manager, 21 Oct 2026). A `.system` directory
anywhere below the root is first-party source and stays checked; the
contract tests in `quality_kit/test_vendored_roots.py` hold both sides.
The rule lives in `source_files.py`, which an upgrade does not copy, so a
consumer gets it only through its own reviewed PR. In a pull request, a
changed vendored file is handled like a deleted one: it adds no source scope.

GitHub Actions runs PR dependency closures and full staging/main/nightly scans.

The read-only GitHub workflow is the external CI trust root. Before installing
or executing the quality project, it compares the anti-bypass verifier with an
exact SHA-256 digest committed in the workflow and fails loudly on a mismatch.
The verifier hardcodes the exact digest of the required-file manifest. The
manifest, in turn, hashes the runner, all six preference checkers, every
semantic helper, the complete-source resolver, `strict_policy.py`, locked
dependencies, tool configuration, Semgrep policy, and this documentation. The
workflow, verifier, and manifest are intentionally excluded from the manifest
to keep the digest chain acyclic.

The verifier rejects missing or unexpected portable files, altered manifest
membership, and every manifested-file hash mismatch. It also validates the
workflow's PR/staging/main/nightly triggers, read-only permissions, trust-anchor step,
frozen install and aggregate commands, full-SHA action pins, and absence of
`continue-on-error: true`. The unavoidable boundary is a coordinated edit to
the external workflow trust root and the chain it anchors: that change must be
identified and judged in code review. Repository-local files cannot
self-authenticate such a coordinated change, this design makes no claim of
mutually authenticated local files, and it uses no operational signing secret.

Ruff always receives `--config quality/pyproject.toml`, BasedPyright receives
`--project quality/pyproject.toml`, Pylint receives
`--rcfile quality/pyproject.toml`, and Semgrep receives the absolute strict
config path. Installation and execution both select the frozen `quality`
project. Consequently root dependency files cannot change the quality
environment, and root tool configs cannot weaken these invocations. The
anti-bypass gate also rejects alternate root tool configs and any other GitHub
Actions workflow that invokes the quality project or a direct checker.
Across every workflow, non-local `uses:` references must be pinned to a full
40-hex commit SHA and `continue-on-error` is forbidden. Mutable third-party
action tags and ignored workflow failures are reported as anti-bypass debt;
deployment workflows receive no exemption.

A nonzero result is an enforcement result, not permission to narrow coverage.
Repair violations with real dependencies or stubs and explicit boundary
architecture. Do not add inline suppressions, diagnostic downgrades, source
exclusions, ignored failures, or checker wrappers that hide a tool result.

## Process edges

A broad exception handler (`except Exception`, `except BaseException` or a bare
`except`) is allowed only at a declared process edge: a CLI entry, a worker
loop, an HTTP boundary, a job runner or a best-effort step. Declare one with
`@process_edge(kind="cli" | "worker_loop" | "http_boundary" | "job" | "best_effort")`, imported
from a copy of `quality/pitchai_quality/process_edge_marker.py` inside the
application. The `process-edges` gate honours the decorator only when that copy
is byte-identical to the kit's file, and only on a `[project.scripts]` target,
an HTTP route, or a function listed in the manifested
`quality/process-edges.json` (`{"edges": ["path/to/module.py:function"]}`).
Any other decorator spelled `process_edge` is a finding: a home-made one, one
imported from a modified copy, or a module-qualified `@module.process_edge(...)`.
Import it by name from the marker copy. Semgrep exempts `@process_edge(...)` by
its spelling alone, so the gate is what ties the exemption to the marker.

Every broad handler outside a marked function is a finding, repository-wide, with
one exception: cleanup that cannot swallow. Such a handler is accepted anywhere only
when every path through it ends in a bare `raise` or `raise X from <the caught
error>` (no conditional raise that another path falls past), it contains no return,
break, continue, yield or nested try that swallows, and its raise is not inside a
loop or a with block. `contextlib.suppress(Exception)` or `suppress(BaseException)`
is a broad swallow and always a finding; suppress a concrete error instead.
Inside one, the handler ends in a bare `raise` or `raise ... from <error>`; a
cli edge may also end in `return <non-zero literal>`; any edge may end in
`sys.exit(<non-zero literal>)` or `raise SystemExit(<non-zero literal>)`; any
edge may end in `fail_job(logger, <error>, record_failure)` or
`return fail_job(...)` from the marker, which logs the error with its traceback and
returns the recorded result (a health route's `{ok: false}` or a monitor's red stage). A handler that exits or returns logs the exception first
(`logger.exception` or `exc_info=`) and never returns, breaks or continues
before its ending.

`fail_job` logs at ERROR. Only a `best_effort` edge may pass
`level=logging.WARNING`, for a step whose failure must be visible but must not
fail its caller (a photo's unreadable EXIF time, a telemetry write); any other
level, or `level=` at another edge kind, is a finding. A best-effort edge is
listed in `quality/process-edges.json` and ends in `fail_job` like any other.

While the process-edges gate is enforced, Ruff `BLE001` and Pylint
`broad-exception-caught` (W0718) are left out of the analyzer commands
(`check.py` adds `--ignore BLE001` and `--disable=broad-exception-caught` only
when `process-edges` is in `EXPECTED_GATES`). The gate is stricter than both:
BLE001 accepts a broad handler anywhere that logs with `exc_info` and then
swallows, and W0718 accepts any handler that raises, while process-edges accepts
a broad handler only at a listed edge with a loud ending, or as cleanup that
re-raises on every path, and also flags `suppress(Exception)`. Without the gate,
both rules stay on. Bare `except` (E722) and every other rule are unchanged.

The Semgrep try/except rule exempts `@process_edge` functions, and the
nested-event-loop gate accepts exactly one `asyncio.run` owned by a
`@process_edge(kind="cli")` function or a `[project.scripts]` target.

The try/except rule also recognizes two framework I/O edges that came with an
earlier installed kit lineage (Infrastructure manager, 23 Oct 2026). One is typed Starlette
middleware that forwards the request: an ASGI `__call__(self, scope: Scope,
receive: Receive, send: Send)` awaiting `self.app(scope, receive, send)`, or a
`BaseHTTPMiddleware.dispatch(self, request: Request, call_next:
RequestResponseEndpoint)` awaiting `call_next(request)`. The other is a try that
opens an `httpx.Client`, `httpx.AsyncClient`, `aiohttp.ClientSession` or
`requests.Session` context. The same method names without the Starlette types or
the forwarding call, a client made outside a `with` block, and plain logic stay
findings. That lineage's narrower `forbid-requests-outside-infra` rule was not
carried over: the central rule still reports every client, wherever it is opened.
That rule reports a call on `requests`, `httpx`, `aiohttp`, `urllib.request`,
`urllib3` or `socket` (an aliased import too) unless the name was assigned a
plain value in its scope: a literal, comprehension, `list`/`dict`/`set`/
`tuple`/`frozenset`, `str`, f-string or `Path` expression. A `socket` path or a
`requests` list is not the module. A dynamic import, a module default
argument, a rebinding to another module, a parameter and a loop variable stay
reported.

## Recognized structural types

Pylint's `too-few-public-methods` (R0903) does not count methods on a class
derived from `typing.Protocol` (`exclude-too-few-public-methods` in
`quality/pyproject.toml`). A Protocol declares an interface; a Protocol with
only `__call__` is the typed shape of a keyword-only callback, which `Callable`
cannot express. Every other class with one public method still fails R0903.

## Incremental pull requests

The portable ratchet runs all analyzers on changed Python files plus their
static dependency closure for pull_request events. It follows affected importers
and their dependencies in both revisions, retaining deleted import edges,
ambiguous source roots, package initializers, pytest fixtures and stub pairs.
Consumers of unresolved dynamic imports are included whenever Python changes.
This is static analysis; it does not execute application plugin loaders.
Dependency and analyzer configuration changes invalidate the whole source set.
Before trusting a closure, every incremental run replays a deep import chain
and a generated import graph through the selector and fails if any transitive
importer of a changed module is missing. The single-use and pure-wrapper
analyzers count callers across the repository, so they always read all source.

The committed quality-baseline.json contains exact diagnostic fingerprints.
Candidate additions are forbidden globally, even when no Python changed.
Touched files must be clean; new findings in unchanged dependents also fail.
Unexamined baseline debt is preserved. Track this file even in repositories
whose ignore rules otherwise exclude JSON.

A target branch without a baseline accepts its first one only from a change
that edits kit files or removes inline suppressions and nothing else, checked
line by line against the merge base. That run is forced to a full scan, which
must reproduce the baseline exactly; files that only lost suppressions keep
their now-visible debt. Any other change to an unseeded target has an empty
ceiling. Remove suppressions in the accepted form with:
uv run --project quality --python 3.12 --frozen python -m pitchai_quality.ratchet_bootstrap PATH...

The target is under 15 minutes for a typical PR. The workflow runs full scans
nightly and on staging/main pushes; workflow_dispatch is also a full scan.
Each commit runs once per mode: a job-level concurrency group keyed by mode and
commit lets a pull_request run cancel a duplicate, never a full push scan.
Integrity checks remain repository-wide. Raw reports record each command,
status and elapsed time. Large dependency closures can still take longer.

Fingerprints must be the same for every run of the same tree. Pylint's
duplicate-code check runs through `pitchai_quality/pylint_similarity_index.py`,
which sorts files by module name and content before comparing (and compares
only file pairs that share a hashed chunk), so the reported groups do not depend
on the order parallel workers finish. Extra copies byte-identical to the kit's process-edge marker are left out of the comparison, because the kit requires them and checks them by hash; one copy stays, so a modified copy is still compared with it. An R0801 fingerprint uses the pseudo-path
`duplicate-code:<first module>` and the sorted `==module:[start:end]` lines,
because Pylint attaches the group to an arbitrary module and prints either
copy's code. `import-error`, `no-name-in-module` and `cyclic-import` depend on
which modules a worker linted first when two top-level modules share a name, so
they run in one serial Pylint pass; the parallel pass runs every other rule.
Every analyzer runs with `PYTHONHASHSEED=0`: Pylint's cycle search walks
hash-ordered sets, so with a random seed the same tree reports a different
set of `cyclic-import` findings from run to run.
An indented source excerpt printed under a preference-checker diagnostic is
part of that diagnostic.

For a local PR proof, run:
uv run --project quality --python 3.12 --frozen python -m pitchai_quality.ratchet --base origin/staging --incremental
Omit --incremental for a full scan. --shrink removes resolved fingerprints only;
an incremental shrink leaves fingerprints outside its examined set intact.

## Application analysis environment

BasedPyright and Pylint resolve imports against `quality/analysis/.venv`, built
from this repository's own locked dependencies; the analyzers stay in the frozen
quality project. Before a local `uv run --project quality --python 3.12 --frozen check`,
run the same commands as the strict workflow, from the repository root:

    UV_PROJECT_ENVIRONMENT=quality/analysis/.venv uv sync --python 3.12 --frozen --all-groups

Without it, imports are unresolved and the gates fail with import errors.
