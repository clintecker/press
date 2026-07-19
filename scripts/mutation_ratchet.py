#!/usr/bin/env python3
"""Deterministic mutation-score ratchet over the pure policy modules.

Coverage proves a line ran; it does not prove a test would notice if the
line were wrong. This ratchet mutates the pure, deterministic policy and
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

quality/mutation-baseline.json records, per module, how many mutants the
tests kill and which survive. The gate fails if a module kills fewer than
its baseline (a proof weakened) or if the mutant total changed (the
source moved and the baseline must be re-taken deliberately, never
automatically). Raise a baseline with --update after adding tests.

Usage:
  python3 scripts/mutation_ratchet.py            # check against baseline
  python3 scripts/mutation_ratchet.py --update   # re-take the baseline
  python3 scripts/mutation_ratchet.py --module receipts   # one module
"""

from __future__ import annotations

import ast
import copy
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "press"
BASELINE = ROOT / "quality" / "mutation-baseline.json"

# module -> the example-based test files that must kill its mutants.
#
# The target set is deliberately the pure-computation modules, where a
# surviving mutant is unambiguously a missing proof: the EAN-13 checksum
# and bar encoding, and the artifact-state derivation. Mutation is the
# wrong instrument for the rest of the package and they are gated
# elsewhere -- data definitions (catalog's command flags) by the
# surface-inventory and catalog-equals-CLI proofs, CLI dispatch
# (receipts.main) by the selftest, orchestration that the tests
# legitimately stub (impact) by its own example tests. Adding a module
# here is a promise its tests pin its logic tightly; earn the score
# before making the promise.
TARGETS: dict[str, list[str]] = {
    "barcode": ["tests/test_barcode.py"],
    "artifact_status": ["tests/test_artifact_status.py"],
}

_COMPARE_FLIP = {
    ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Is: ast.IsNot,
    ast.IsNot: ast.Is, ast.In: ast.NotIn, ast.NotIn: ast.In,
}
_ARITH_FLIP = {
    ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.FloorDiv,
    ast.FloorDiv: ast.Mult, ast.Mod: ast.Mult,
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

    @property
    def id(self) -> str:
        return f"{self.lineno}:{self.col}:{self.kind}:{self.detail}"


def _enumerate(tree: ast.AST) -> list[Site]:
    sites: list[Site] = []
    for node in ast.walk(tree):
        if not hasattr(node, "lineno") or not hasattr(node, "col_offset"):
            continue
        line: int = node.lineno
        col: int = node.col_offset
        if isinstance(node, ast.Compare) and node.ops:
            op = node.ops[0]
            if type(op) in _COMPARE_FLIP:
                sites.append(Site(line, col, "compare", type(op).__name__))
        elif isinstance(node, ast.BinOp) and type(node.op) in _ARITH_FLIP:
            sites.append(Site(line, col, "arith", type(node.op).__name__))
        elif isinstance(node, ast.BoolOp) and type(node.op) in _BOOL_FLIP:
            sites.append(Site(line, col, "bool", type(node.op).__name__))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            sites.append(Site(line, col, "not", "drop"))
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                sites.append(Site(line, col, "boolconst", str(node.value)))
            elif isinstance(node.value, int):
                sites.append(Site(line, col, "intconst", str(node.value)))
    # Left-nested BinOps share a (line, col), producing identical site
    # ids; keep one per id so a mutant is enumerated and run exactly once.
    seen: set[str] = set()
    unique: list[Site] = []
    for site in sites:
        if site.id not in seen:
            seen.add(site.id)
            unique.append(site)
    return unique


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
    if isinstance(node, ast.Constant) and isinstance(node.value, bool) and str(node.value) == detail:
        node.value = not node.value
        return True
    return False


def _mut_intconst(node: ast.AST, detail: str) -> bool:
    if (isinstance(node, ast.Constant) and isinstance(node.value, int)
            and not isinstance(node.value, bool) and str(node.value) == detail):
        node.value = node.value + 1
        return True
    return False


_MUTATORS = {
    "compare": _mut_compare, "arith": _mut_arith, "bool": _mut_bool,
    "boolconst": _mut_boolconst, "intconst": _mut_intconst,
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
            if (isinstance(node.op, ast.Not)
                    and node.lineno == target.lineno
                    and node.col_offset == target.col_offset):
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


def _run_tests(test_files: list[str], pkg_parent: Path) -> bool:
    """True if the tests all pass on the current shadow (mutant survived);
    False if any test fails or errors (mutant killed)."""

    env = dict(os.environ)
    env["PYTHONPATH"] = str(pkg_parent) + os.pathsep + env.get("PYTHONPATH", "")
    # No bytecode cache: a .pyc written for one mutant would, within a
    # single mtime tick, be reused for the next and run the wrong mutant.
    # Forbidding the cache makes every import compile the current source.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
         "--no-header", "-x", *test_files],
        cwd=ROOT, env=env, capture_output=True,
    )
    return result.returncode == 0


def score_module(module: str) -> dict:
    source = (SRC / f"{module}.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    sites = _enumerate(tree)
    survivors: list[str] = []
    with tempfile.TemporaryDirectory(prefix=f"mut-{module}-") as tmp:
        tmp_path = Path(tmp)
        pkg = _shadow(module, tmp_path)
        target = pkg / f"{module}.py"
        for site in sites:
            mutant = _apply(tree, site)
            target.write_text(ast.unparse(mutant), encoding="utf-8")
            if _run_tests(TARGETS[module], tmp_path):
                survivors.append(site.id)
    total = len(sites)
    return {"total": total, "killed": total - len(survivors),
            "survivors": sorted(survivors)}


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    update = "--update" in args
    only = None
    if "--module" in args:
        only = args[args.index("--module") + 1]

    modules = [only] if only else list(TARGETS)
    current = {m: score_module(m) for m in modules}
    for m in modules:
        r = current[m]
        print(f"{m}: killed {r['killed']}/{r['total']}"
              + (f"  survivors: {', '.join(r['survivors'])}" if r["survivors"] else ""))

    if update:
        existing = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {"modules": {}}
        existing.setdefault("modules", {}).update(current)
        existing["modules"] = dict(sorted(existing["modules"].items()))
        BASELINE.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
        print(f"re-baselined {len(current)} module(s)")
        return 0

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))["modules"]
    problems = []
    for m in modules:
        r = current[m]
        base = baseline.get(m)
        if base is None:
            problems.append(f"{m}: no baseline (run --update)")
        elif r["total"] != base["total"]:
            problems.append(
                f"{m}: mutant total changed {base['total']} -> {r['total']}; "
                f"the source moved, re-take the baseline deliberately")
        elif r["killed"] < base["killed"]:
            new = sorted(set(r["survivors"]) - set(base["survivors"]))
            problems.append(
                f"{m}: kills dropped {base['killed']} -> {r['killed']}; "
                f"new survivors: {', '.join(new)}")
    if problems:
        print("\nmutation ratchet failed:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"\nmutation ratchet holds: {len(modules)} module(s) at or above baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
