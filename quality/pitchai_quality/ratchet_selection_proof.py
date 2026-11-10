# Copyright (c) 2026 PitchAI. All rights reserved.
"""Prove that PR selection keeps every transitive importer before trusting it.

The incremental ratchet may only skip a module when no change can reach it
through imports. Every incremental run first replays two fixtures through the
real closure function and fails closed if a transitive importer is missing:

* a hand-written chain in which each link imports its predecessor with a
  different form: package re-exports, dotted, aliased, relative and nested
  source-root imports, stub pairs, literal dynamic loaders, deferred, guarded
  and function-local imports, a long linear tail and pytest conftest scoping;
* a generated graph whose expected importers come from its explicit edge
  list, independently of the AST-based resolver under test.
"""

from __future__ import annotations

from .ratchet_dependencies import dependency_closure

_TAIL_LENGTH = 24
_GRAPH_SIZE = 160
_GRAPH_SEEDS = (0, 1, 17, 59, 101, 158)
_IMPORT_FORMS = (
    "import graph.n{0:03d}\n",
    "from graph import n{0:03d}\n",
    "from . import n{0:03d}\n",
    "from .n{0:03d} import VALUE\n",
)
_HAND_CHAIN = (
    ("a00/base.py", "VALUE = 1\n"),
    ("a01/pkg/__init__.py", "from a00.base import VALUE\n"),
    ("a02/user.py", "import a01.pkg\n"),
    ("a03/sub/helper.py", "from a02.user import a01\n"),
    ("a03/sub/deep/mod.py", "from ..helper import a01\n"),
    ("a05/alias.py", "import a03.sub.deep.mod as deep_module\n"),
    ("src/a06/srcroot.py", "from a05 import alias\n"),
    ("a07/consumer.py", "from a06.srcroot import alias\n"),
    ("a08/typed.pyi", "from a07.consumer import alias as alias\n"),
    ("a08/typed.py", "VALUE = 2\n"),
    ("a09/runtime_user.py", "import a08.typed\n"),
    ("a10/loader.py", "from importlib import import_module as load\nMODULE = load('a09.runtime_user')\n"),
    ("a11/legacy.py", "LOADED = __import__('a10.loader')\n"),
    ("a12/deferred.py", "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from a11 import legacy\n"),
    ("a13/lazy.py", "def load():\n    from a12.deferred import TYPE_CHECKING\n    return TYPE_CHECKING\n"),
    ("a14/guarded.py", "try:\n    import a13.lazy as lazy\nexcept ImportError:\n    lazy = None\n"),
)
_FIXTURE_TEST = ("tests/unit/test_uses_fixture.py", "def test_fixture():\n    assert True\n")
_UNRELATED = ("other/isolated.py", "VALUE = 3\n")


def _hand_chain() -> dict[str, str]:
    sources = dict(_HAND_CHAIN)
    previous = "a14.guarded"
    for index in range(_TAIL_LENGTH):
        sources[f"chain/link_{index:02d}.py"] = f"import {previous}\n"
        previous = f"chain.link_{index:02d}"
    sources["tests/conftest.py"] = f"from {previous} import *\n"
    sources[_FIXTURE_TEST[0]] = _FIXTURE_TEST[1]
    sources[_UNRELATED[0]] = _UNRELATED[1]
    return sources


def _graph_edges() -> dict[int, frozenset[int]]:
    edges: dict[int, frozenset[int]] = {0: frozenset()}
    for index in range(1, _GRAPH_SIZE):
        candidates = {(index * 37 + 11) % 151 % index, (index * index + 3) % 149 % index}
        if index % 5:
            candidates.add(index - 1)
        edges[index] = frozenset(candidates)
    return edges


def _graph_sources(edges: dict[int, frozenset[int]]) -> dict[str, str]:
    sources: dict[str, str] = {}
    for importer, dependencies in edges.items():
        lines = ["VALUE = 0\n"]
        for dependency in sorted(dependencies):
            form = _IMPORT_FORMS[(importer + dependency) % len(_IMPORT_FORMS)]
            lines.append(form.format(dependency))
        sources[f"graph/n{importer:03d}.py"] = "".join(lines)
    return sources


def _graph_importers(edges: dict[int, frozenset[int]], seed: int) -> frozenset[str]:
    found = {seed}
    pending = [seed]
    while pending:
        dependency = pending.pop()
        for importer, dependencies in edges.items():
            if dependency in dependencies and importer not in found:
                found.add(importer)
                pending.append(importer)
    return frozenset(f"graph/n{index:03d}.py" for index in found)


def _missing(sources: dict[str, str], changed: str, expected: frozenset[str]) -> list[str]:
    selected = dependency_closure(sources, {}, frozenset({changed}))
    return [f"{changed} -> {path}" for path in sorted(expected - selected)]


def prove_selection() -> None:
    """Fail closed unless every transitive importer of a change is selected.

    Raises:
        RuntimeError: The closure omitted a module that imports a changed module.
    """
    chain = _hand_chain()
    chain_importers = frozenset(chain) - {_UNRELATED[0]}
    missing = _missing(chain, _HAND_CHAIN[0][0], chain_importers)
    edges = _graph_edges()
    graph = _graph_sources(edges)
    for seed in _GRAPH_SEEDS:
        missing.extend(_missing(graph, f"graph/n{seed:03d}.py", _graph_importers(edges, seed)))
    if missing:
        message = "incremental selection skipped transitive importers:\n" + "\n".join(missing)
        raise RuntimeError(message)
