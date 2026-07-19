"""Collection-time enforcement of test-to-invariant metadata.

A test can exist yet prove no named project claim, exercise only a
passive signal, use an undeclared skip, or sit in the wrong tier. This
plugin rejects those before the expensive tests run. It reads the
executable invariant ledger (quality/invariants.yaml, via
``press.invariants``) and, during collection, holds these lines *where
the metadata is present* -- it does not force markers onto every test:

  - an ``invariant`` marker must name a ledger id, and a test that
    carries one must also carry ``layer`` and ``proof`` (an invariant
    claim with no proof polarity is the missing-proof failure);
  - a ``layer`` marker must be one of the known tiers, a ``proof``
    marker one of the polarities;
  - every ``xfail`` must cite a declared invariant limitation (an INV
    id whose ledger entry carries a ``limitations`` field), in the
    marker reason or the test's own ``invariant`` marker;
  - every environment-dependent skip must name a declared toolchain
    capability, and the capability set is emitted in the report;
  - a marked test with no assertion, ``pytest.raises``/``warns``, or a
    recognized assertion helper is an assertionless test and fails.

It also emits the test -> invariant and invariant -> collected-test
indexes to ``tests/_collection-index.json`` before execution, so later
gates (fixture provenance, surface coverage) can consume the mapping
mechanically rather than re-deriving it from marker scraping.

This module deliberately exposes no public module-level callable: the
hooks live on a class and every helper is underscore-prefixed, so the
public-surface inventory (``press.surfaces``) has nothing here to
classify. ``tests/conftest.py`` (and each malformed-suite sub-session)
installs it by calling ``_install`` from its ``pytest_configure``.
"""

from __future__ import annotations

import ast
import inspect
import json
import re
import textwrap
from pathlib import Path
from typing import Any

import pytest

# The known tiers and polarities. Kept in step with the marker help in
# pyproject.toml's [tool.pytest.ini_options].markers.
_LAYERS = frozenset({"unit", "property", "selftest", "integration"})
_POLARITIES = frozenset({"positive", "negative"})

# The toolchain capabilities a skip is allowed to gate on. These are the
# external tools the press shells out to (see press.doctor); an
# environment-dependent skip must name one of them, so a skip can never
# hide an untested tier behind an unexplained condition.
_CAPABILITIES = frozenset({
    "pandoc", "lualatex", "latexmk", "pdftoppm", "pdffonts",
    "pdfinfo", "pdftotext", "git", "epubcheck", "claude",
    # The packaging tool, a real capability the distribution tests need.
    "build",
    # The optional operator-desk interface.
    "textual",
})

_INV_ID = re.compile(r"INV-[A-Za-z0-9-]+")
# Call names that count as an assertion when a test carries no bare
# `assert`: pytest's expected-exception/warning contexts and helpers, and
# unittest-style assert* helpers. A bare expect() (a common assertion
# spelling) counts; expect*-prefixed value helpers do not.
_ASSERT_CALLS = frozenset({
    "raises", "warns", "deprecated_call", "fail", "xfail", "approx",
})

_PLUGIN_NAME = "press-invariants"


def _load_ledger() -> dict[str, dict[str, Any]]:
    """Ledger id -> entry, from the executable invariant ledger."""

    from press import invariants

    return {
        inv["id"]: inv
        for inv in invariants.load()
        if isinstance(inv, dict) and "id" in inv
    }


def _marker(item: pytest.Item, name: str) -> tuple[bool, Any]:
    """(present, first-positional-arg-or-None) for one marker."""

    mark = item.get_closest_marker(name)
    if mark is None:
        return False, None
    return True, (mark.args[0] if mark.args else None)


def _source_tree(item: pytest.Item) -> ast.AST | None:
    """The AST of the test's own body, unwrapping hypothesis and
    functools wrappers. None when the source cannot be read (never a
    reason to fail; absence of evidence is not evidence of assertionless
    code)."""

    func = getattr(item, "obj", None)
    if func is None:
        return None
    inner = getattr(getattr(func, "hypothesis", None), "inner_test", None)
    if inner is None:
        inner = getattr(func, "__wrapped__", func)
    try:
        source = textwrap.dedent(inspect.getsource(inner))
    except (OSError, TypeError):
        return None
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _has_assertion(tree: ast.AST) -> bool:
    """True if the test body carries a bare assert, an expected-exception
    or -warning context, or a call to a recognized assertion helper."""

    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            return True
        if isinstance(node, ast.Call):
            name = _call_name(node)
            # `assert*` covers unittest-style helpers (assertEqual); a bare
            # `expect`-prefix is too loose (expected_payload() is a value,
            # not an assertion), so only an exact `expect` call counts.
            if name in _ASSERT_CALLS or name.startswith("assert") or name == "expect":
                return True
    return False


def _cited_limitation(reason: str, invariant: str | None, ledger: dict[str, dict[str, Any]]) -> bool:
    """True if the reason or invariant marker names an INV id whose
    ledger entry declares a limitation."""

    text = f"{reason or ''} {invariant or ''}"
    for found in _INV_ID.findall(text):
        entry = ledger.get(found)
        if entry and entry.get("limitations"):
            return True
    return False


def _named_capabilities(reason: str) -> list[str]:
    """Declared capabilities the reason names, as `capability:<name>` or
    by bare word."""

    reason = reason or ""
    return sorted(
        cap for cap in _CAPABILITIES
        if re.search(rf"\b{re.escape(cap)}\b", reason)
    )


def _item_problems(
    item: pytest.Item, ledger: dict[str, dict[str, Any]]
) -> tuple[list[str], list[str]]:
    """(problems, capabilities-named) for one collected test. Every
    problem is prefixed with the node id so the failure is locatable."""

    problems: list[str] = []
    caps: list[str] = []
    nid = item.nodeid

    has_inv, invariant = _marker(item, "invariant")
    has_layer, layer = _marker(item, "layer")
    has_proof, proof = _marker(item, "proof")
    marked = has_inv or has_layer or has_proof

    if has_inv:
        if invariant is None:
            problems.append(f"{nid}: invariant marker carries no id")
        elif invariant not in ledger:
            problems.append(
                f"{nid}: unknown invariant {invariant!r}; "
                "not in quality/invariants.yaml"
            )
        if not has_layer:
            problems.append(
                f"{nid}: invariant marker requires a layer marker "
                "(missing proof metadata)"
            )
        if not has_proof:
            problems.append(
                f"{nid}: invariant marker requires a proof marker "
                "(an invariant claim with no proof polarity)"
            )

    if has_layer and layer not in _LAYERS:
        problems.append(
            f"{nid}: unknown layer {layer!r}; expected one of {sorted(_LAYERS)}"
        )
    if has_proof and proof not in _POLARITIES:
        problems.append(
            f"{nid}: unknown proof {proof!r}; expected positive or negative"
        )

    xfail = item.get_closest_marker("xfail")
    if xfail is not None:
        reason = xfail.kwargs.get("reason", "") or ""
        if not _cited_limitation(reason, invariant if has_inv else None, ledger):
            problems.append(
                f"{nid}: xfail must cite a declared invariant limitation "
                "(an INV id whose ledger entry has a limitations field) "
                "in its reason or invariant marker"
            )

    for skip_name in ("skip", "skipif"):
        mark = item.get_closest_marker(skip_name)
        if mark is None:
            continue
        reason = mark.kwargs.get("reason", "") or ""
        named = _named_capabilities(reason)
        if not named:
            problems.append(
                f"{nid}: {skip_name} must name a declared capability "
                f"(one of {sorted(_CAPABILITIES)}) in its reason"
            )
        caps.extend(named)

    if marked:
        tree = _source_tree(item)
        if tree is not None and not _has_assertion(tree):
            problems.append(
                f"{nid}: marked test has no assertion (no assert, "
                "pytest.raises, or recognized assertion helper)"
            )

    return problems, caps


def _write_index(
    config: pytest.Config,
    test_to_inv: dict[str, str],
    inv_to_tests: dict[str, list[str]],
) -> None:
    """Write the test -> invariant and invariant -> test indexes before
    execution. Only into a real tests/ directory; sub-sessions under a
    temporary root get nothing, which is correct."""

    target = Path(config.rootpath) / "tests" / "_collection-index.json"
    if not target.parent.is_dir():
        return
    payload = {
        "test_to_invariant": test_to_inv,
        "invariant_to_tests": {k: sorted(v) for k, v in inv_to_tests.items()},
    }
    try:
        target.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


class _InvariantCollectionPlugin:
    """Holds the metadata line at collection time and reports the
    capability set and the invariant indexes."""

    def __init__(self) -> None:
        self._capabilities: set[str] = set()
        self._test_to_inv: dict[str, str] = {}
        self._inv_to_tests: dict[str, list[str]] = {}

    def pytest_collection_modifyitems(
        self,
        session: pytest.Session,
        config: pytest.Config,
        items: list[pytest.Item],
    ) -> None:
        ledger = _load_ledger()
        problems: list[str] = []
        for item in items:
            item_problems, caps = _item_problems(item, ledger)
            problems.extend(item_problems)
            self._capabilities.update(caps)
            has_inv, invariant = _marker(item, "invariant")
            if has_inv and invariant is not None:
                self._test_to_inv[item.nodeid] = invariant
                self._inv_to_tests.setdefault(invariant, []).append(item.nodeid)
        if problems:
            raise pytest.UsageError(
                "invariant/layer/proof collection failed:\n"
                + "\n".join(f"  - {p}" for p in problems)
            )
        _write_index(config, self._test_to_inv, self._inv_to_tests)

    def pytest_terminal_summary(
        self,
        terminalreporter: Any,
        exitstatus: int,
        config: pytest.Config,
    ) -> None:
        tr = terminalreporter
        tr.write_sep("-", "invariant collection")
        tr.write_line(
            "declared capabilities: " + ", ".join(sorted(_CAPABILITIES))
        )
        if self._capabilities:
            tr.write_line(
                "capabilities named by skips: "
                + ", ".join(sorted(self._capabilities))
            )
        tr.write_line(
            f"tests carrying an invariant: {len(self._test_to_inv)}; "
            f"invariants with a collected proof: {len(self._inv_to_tests)}"
        )


def _install(config: pytest.Config) -> None:
    """Register the plugin once on a config. Called from a
    ``pytest_configure`` hook in conftest (and in each malformed-suite
    sub-session)."""

    if config.pluginmanager.get_plugin(_PLUGIN_NAME) is None:
        config.pluginmanager.register(_InvariantCollectionPlugin(), _PLUGIN_NAME)
