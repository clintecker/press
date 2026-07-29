"""Deterministic mutation of the pure policy modules, for celebrimbor's ratchet.

Coverage proves a line ran; it does not prove a test would notice if the
line were wrong. This module mutates the pure, deterministic policy and
verifier modules one edit at a time -- flip a comparison, swap a boolean
operator, bump a constant -- and runs each module's example-based tests
against the mutant. A mutant the tests still pass is a survivor: a change
to the logic that no test detects, which is a missing proof.

Determinism is the whole point, so the gate cannot flake. The target
modules are pure (no toolchain, no clock, no network); their provers are
example-based, never Hypothesis; each mutant runs its tests exactly once
with no retry, so a red result can never be laundered into green. The
mutant runs against a shadow copy of the source tree (symlinks, with the
one mutated file written real) so the working tree is never touched.

:func:`survivors` is the seam celebrimbor's mutation ratchet consumes
(``[tool.celebrimbor] mutation_survivors``): it returns the current survivor
set as ``frozenset[celebrimbor.Survivor]``, and celebrimbor runs its own
survivor-identity ratchet over that set against
``.celebrimbor/baselines/mutation.yaml``. celebrimbor is a dev/CI dependency,
never a book runtime one, so it is imported lazily inside :func:`survivors`
and this module imports cleanly without it.
"""

from __future__ import annotations

import ast
import copy
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from . import adapters

if TYPE_CHECKING:
    from celebrimbor import Survivor

SRC = Path(__file__).resolve().parent
ROOT = SRC.parent.parent

# module -> the example-based test files that must kill its mutants.
#
# The target set is deliberately the pure-computation modules, where a
# surviving mutant is unambiguously a missing proof: the EAN-13 checksum
# and bar encoding, the artifact-state derivation, the drop-cap grapheme
# and settings split, and the figure-declaration parse and validation.
# Mutation is the wrong instrument for the rest of the package and they are
# gated elsewhere -- data definitions (catalog's command flags) by the
# surface-inventory and catalog-equals-CLI proofs, CLI dispatch
# (receipts.main) by the selftest, orchestration that the tests
# legitimately stub (impact) by its own example tests. verify_formats is
# deliberately NOT a target: it is dominated by verifier functions that
# only run under the toolchain (verify_epub, verify_site), so whole-module
# mutation would enumerate scores of mutants no unit test can reach (7 of 92
# killed) -- the wrong instrument, exactly like receipts and impact; its pure
# witness logic is pinned by test_verify_editions and the normalized
# property tests instead. Adding a module here is a promise its tests pin its
# logic tightly; earn the score before making the promise.
TARGETS: dict[str, list[str]] = {
    "barcode": ["tests/test_barcode.py"],
    "artifact_status": ["tests/test_artifact_status.py"],
    "dropcaps": ["tests/test_dropcaps.py"],
    "figures": ["tests/test_figures.py"],
}

_COMPARE_FLIP = {
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
}
_ARITH_FLIP = {
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.FloorDiv,
    ast.FloorDiv: ast.Mult,
    ast.Mod: ast.Mult,
}
_BOOL_FLIP = {ast.And: ast.Or, ast.Or: ast.And}


@dataclass(frozen=True)
class Site:
    """A single mutation, addressed by node position so it can be found
    again in a freshly parsed tree."""

    lineno: int
    col: int
    kind: str
    detail: str  # operator index or the concrete edit, for a stable id


def _site_id(site: Site) -> str:
    return f"{site.lineno}:{site.col}:{site.kind}:{site.detail}"


def _const_site(node: ast.Constant, line: int, col: int) -> Site | None:
    """The mutation a constant offers: flip a bool, bump an int. bool is a
    subclass of int, so it must be tested first."""

    if isinstance(node.value, bool):
        return Site(line, col, "boolconst", str(node.value))
    if isinstance(node.value, int):
        return Site(line, col, "intconst", str(node.value))
    return None


def _site_for(node: ast.AST, line: int, col: int) -> Site | None:
    """The one mutation site a node offers, or None if it offers none."""

    if isinstance(node, ast.Compare) and node.ops and type(node.ops[0]) in _COMPARE_FLIP:
        return Site(line, col, "compare", type(node.ops[0]).__name__)
    if isinstance(node, ast.BinOp) and type(node.op) in _ARITH_FLIP:
        return Site(line, col, "arith", type(node.op).__name__)
    if isinstance(node, ast.BoolOp) and type(node.op) in _BOOL_FLIP:
        return Site(line, col, "bool", type(node.op).__name__)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return Site(line, col, "not", "drop")
    if isinstance(node, ast.Constant):
        return _const_site(node, line, col)
    return None


def _dedupe(sites: list[Site]) -> list[Site]:
    """Left-nested BinOps share a (line, col), producing identical site ids;
    keep one per id so a mutant is enumerated and run exactly once."""

    seen: set[str] = set()
    unique: list[Site] = []
    for site in sites:
        if _site_id(site) not in seen:
            seen.add(_site_id(site))
            unique.append(site)
    return unique


def _enumerate(tree: ast.AST) -> list[Site]:
    sites: list[Site] = []
    for node in ast.walk(tree):
        if not hasattr(node, "lineno") or not hasattr(node, "col_offset"):
            continue
        site = _site_for(node, node.lineno, node.col_offset)
        if site is not None:
            sites.append(site)
    return _dedupe(sites)


def _mut_compare(node: ast.AST, detail: str) -> bool:
    if isinstance(node, ast.Compare) and node.ops and type(node.ops[0]).__name__ == detail:
        node.ops[0] = _COMPARE_FLIP[type(node.ops[0])]()
        return True
    return False


def _mut_arith(node: ast.AST, detail: str) -> bool:
    if isinstance(node, ast.BinOp) and type(node.op).__name__ == detail:
        node.op = _ARITH_FLIP[type(node.op)]()
        return True
    return False


def _mut_bool(node: ast.AST, detail: str) -> bool:
    if isinstance(node, ast.BoolOp) and type(node.op).__name__ == detail:
        node.op = _BOOL_FLIP[type(node.op)]()
        return True
    return False


def _mut_boolconst(node: ast.AST, detail: str) -> bool:
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, bool)
        and str(node.value) == detail
    ):
        node.value = not node.value
        return True
    return False


def _mut_intconst(node: ast.AST, detail: str) -> bool:
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
        and str(node.value) == detail
    ):
        node.value = node.value + 1
        return True
    return False


_MUTATORS: dict[str, Callable[[ast.AST, str], bool]] = {
    "compare": _mut_compare,
    "arith": _mut_arith,
    "bool": _mut_bool,
    "boolconst": _mut_boolconst,
    "intconst": _mut_intconst,
}


def _apply(tree: ast.AST, site: Site) -> ast.AST:
    """Return a fresh tree with exactly the one mutation applied."""

    mutated = copy.deepcopy(tree)
    for node in ast.walk(mutated):
        if getattr(node, "lineno", None) != site.lineno:
            continue
        if getattr(node, "col_offset", None) != site.col:
            continue
        if site.kind == "not":
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
                return _replace_not(mutated, node)
            continue
        mutate = _MUTATORS.get(site.kind)
        if mutate is not None and mutate(node, site.detail):
            break
    return mutated


def _replace_not(tree: ast.AST, target: ast.UnaryOp) -> ast.AST:
    """Replace `not x` with `x` by rewriting the parent reference."""

    class Dropper(ast.NodeTransformer):
        def visit_UnaryOp(self, node: ast.UnaryOp):
            self.generic_visit(node)
            if (
                isinstance(node.op, ast.Not)
                and node.lineno == target.lineno
                and node.col_offset == target.col_offset
            ):
                return node.operand
            return node

    return ast.fix_missing_locations(Dropper().visit(tree))


def _shadow(module: str, tmp: Path) -> Path:
    """A shadow `press` package: symlinks to every real module, with the
    target module left out so the caller writes a mutant in its place."""

    pkg = tmp / "press"
    pkg.mkdir(parents=True, exist_ok=True)
    for entry in SRC.iterdir():
        if entry.name in (f"{module}.py", "__pycache__"):
            continue
        link = pkg / entry.name
        if not link.exists():
            link.symlink_to(entry)
    return pkg


def _mutant_env(pkg_parent: Path) -> dict[str, str]:
    """The child environment for a mutant run: the shadow package ahead on
    PYTHONPATH, and no bytecode cache. A .pyc written for one mutant would,
    within a single mtime tick, be reused for the next and run the wrong
    mutant; forbidding the cache makes every import compile the current
    source. Read through the environment adapter, never ``os.environ``."""

    env = adapters.environment.copy()
    env["PYTHONPATH"] = str(pkg_parent) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _run_tests(test_files: list[str], pkg_parent: Path) -> bool:
    """True if the tests all pass on the current shadow (mutant survived);
    False if any test fails or errors (mutant killed)."""

    result = adapters.process_runner.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-q",
            "--no-header",
            "-x",
            *test_files,
        ],
        cwd=ROOT,
        env=_mutant_env(pkg_parent),
        capture=True,
    )
    return result.returncode == 0


def _assert_shadow_wins(module: str, pkg_parent: Path) -> None:
    """Confirm the shadow module out-ranks the installed one before any
    scoring. If it did not (a strict-editable MetaPathFinder resolving
    press before PYTHONPATH), every mutant would import the real module
    and 'survive' -- and scoring in that state would silently gut the
    gate. Better to abort loudly than to bless a shadow that lost."""

    result = adapters.process_runner.run(
        [sys.executable, "-c", f"import press.{module} as m; print(m.__file__)"],
        cwd=ROOT,
        env=_mutant_env(pkg_parent),
        capture=True,
    )
    resolved = result.stdout.decode("utf-8", "replace").strip()
    if not resolved.startswith(str(pkg_parent)):
        raise SystemExit(
            f"mutation shadow did not win: press.{module} resolved to "
            f"{resolved!r}, not under {pkg_parent}. Mutants would be measured "
            "against the real module; refusing to score."
        )


def _survivor_sites(module: str) -> list[Site]:
    """The sites whose mutant every target test still passed -- the survivors
    of one module, each a change to its logic no test detects."""

    source = (SRC / f"{module}.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    sites = _enumerate(tree)
    survivors: list[Site] = []
    with tempfile.TemporaryDirectory(prefix=f"mut-{module}-") as tmp:
        tmp_path = Path(tmp)
        pkg = _shadow(module, tmp_path)
        target = pkg / f"{module}.py"
        target.write_text(source, encoding="utf-8")
        _assert_shadow_wins(module, tmp_path)
        for site in sites:
            mutant = _apply(tree, site)
            target.write_text(ast.unparse(mutant), encoding="utf-8")
            if _run_tests(TARGETS[module], tmp_path):
                survivors.append(site)
    return survivors


def survivors() -> "frozenset[Survivor]":
    """The current mutation survivors across every target module, as
    ``frozenset[celebrimbor.Survivor]`` for celebrimbor's mutation ratchet.

    One press survivor maps to one ``Survivor(file, line, operator)``: the
    repo-relative source path, the mutation's line, and an operator string
    that carries the column, kind, and detail. celebrimbor's survivor
    identity is ``file:line:operator`` and its baseline round-trips that
    string by splitting on the last two colons, so the operator itself must
    hold no colon; press joins ``col``, ``kind``, and ``detail`` (all
    alphanumeric) with ``-`` instead. Column is part of the operator so two
    mutants on one line never collide. celebrimbor is imported here (never at
    module top) so this module loads without it on a bare install."""

    from celebrimbor import Survivor

    found: set[Survivor] = set()
    for module in TARGETS:
        rel = f"src/press/{module}.py"
        for site in _survivor_sites(module):
            found.add(
                Survivor(
                    file=rel,
                    line=site.lineno,
                    operator=f"{site.col}-{site.kind}-{site.detail}",
                )
            )
    return frozenset(found)
