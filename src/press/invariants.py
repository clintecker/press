"""The executable invariant ledger.

quality/invariants.yaml is the source of record for what the press
promises and where each promise is kept. This module validates the
ledger and renders docs/INVARIANTS.md from it. Validation has teeth
beyond schema shape: every enforcer names a real module (and function,
when given), and every proof names a real selftest check or a fixture
file that exists, so the ledger cannot cite a function or fixture that
has been deleted or renamed. A critical invariant with no owner,
enforcer, or proof fails the ledger rather than sitting undefended.

Fields per invariant:
  id          stable identifier, INV-<area>-<n>
  statement   what is guaranteed, one sentence
  risk        what breaks if it fails
  criticality critical | standard
  owner       the module responsible
  enforcer    module or module.function that holds the line
  producer    optional: what generates the artifact this guards
  layers      required test layers (e.g. [selftest, integration])
  positive    optional list: proofs the invariant holds
  negative    list: proofs it can fail (selftest check names or
              fixture paths under src/press/data/known-bad/)
  ci_tier     which CI boundary runs the proof
  limitations one honest sentence on what it does not cover
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from . import yamlio

REQUIRED = {
    "id", "statement", "risk", "criticality", "owner", "enforcer",
    "layers", "negative", "ci_tier", "limitations",
}
OPTIONAL = {"producer", "positive"}
CRITICALITIES = {"critical", "standard"}
ROOT = Path(__file__).resolve().parent
LEDGER = ROOT.parent.parent / "quality" / "invariants.yaml"
KNOWN_BAD = ROOT / "data" / "known-bad"

# A short human name for each invariant, shown alongside its id so the
# generated reference reads as a scannable list of guarantees rather than
# a wall of INV- slugs. Every invariant must have one (validate enforces
# it), so a new invariant cannot ship nameless.
TITLES = {
    "INV-config-slug": "Safe slugs",
    "INV-config-trim": "Fixed v1 trim",
    "INV-config-locatable": "Locatable config errors",
    "INV-config-release-witness": "No vacuous releases",
    "INV-config-registrations": "Computed check digits",
    "INV-editorial-battery": "The prose battery",
    "INV-editorial-jargon": "Jargon watchlist",
    "INV-editorial-checkers": "Checkers proven by fixtures",
    "INV-editorial-banned-regex": "Guarded banned patterns",
    "INV-authorities-claims": "Authorities claims exist",
    "INV-authorities-printsafe": "Print-safe sources",
    "INV-pdf-detector": "Proven blank-page detector",
    "INV-pdf-ink": "Every page carries ink",
    "INV-format-witness": "A witness in every format",
    "INV-format-site-identity": "One witness per chapter",
    "INV-pages-refs": "Every reference resolves",
    "INV-archive-site-bytes": "Reader archive matches the site",
    "INV-archive-source-policy": "Policy-clean source archive",
    "INV-coverwrap-geometry": "Cover-wrap geometry",
    "INV-coverwrap-barcode": "Scannable barcode panel",
    "INV-graph-acyclic": "Acyclic artifact graph",
    "INV-graph-no-stale": "No stale artifact is blessed",
    "INV-graph-escaping": "Escaped interpolation",
    "INV-cli-exit-code": "Honest exit codes",
    "INV-release-tag-grammar": "Strict release tags",
    "INV-release-contract": "Immutable release contract",
    "INV-scaffold-neutral": "Neutral scaffold",
    "INV-docs-no-drift": "Docs never drift",
    "INV-contract-mirror": "AGENTS mirrors CLAUDE",
    "INV-release-receipt-chain": "Complete release chain",
    "INV-edition-manifest": "Immutable edition identity",
    "INV-provider-qualification": "Honest provider record",
    "INV-commerce-config": "Safe ordering config",
    "INV-commerce-release-gate": "Qualified before sale",
    "INV-provider-contract": "Provider-neutral contract",
}


def load(path: Path = LEDGER) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        data = yamlio.loads(handle.read())
    if not isinstance(data, dict) or not isinstance(data.get("invariants"), list):
        raise SystemExit(f"{path}: must be a mapping with an 'invariants' list")
    return data["invariants"]


def _module_exists(dotted: str) -> bool:
    """A `press.x` module or `press.x.func` reference resolves."""

    module, _, attr = dotted.partition(".")
    try:
        mod = importlib.import_module(f"press.{module}")
    except ModuleNotFoundError:
        return False
    return not attr or hasattr(mod, attr)


def _selftest_has(check: str) -> bool:
    from . import selftest

    return hasattr(selftest, check)


def _proof_resolves(proof: str) -> str | None:
    """None if the proof reference is real, else the reason it is not.

    A proof is either a selftest check function name, a known-bad
    fixture path, or the literal 'integration'/'none' with a reason
    the ledger records honestly.
    """

    if proof in {"integration", "none"}:
        return None
    if proof.startswith("check_"):
        return None if _selftest_has(proof) else f"no selftest {proof}"
    if proof.startswith("fixture:"):
        name = proof.split(":", 1)[1]
        return None if (KNOWN_BAD / name).is_file() else f"no fixture {name}"
    return f"unrecognized proof reference {proof!r}"


def _entry_problems(where: str, inv: dict[str, Any]) -> list[str]:
    """Every defect in one invariant: schema, then referential
    integrity of its enforcer, producer, and proofs, then the rule that
    a critical invariant must carry a real negative proof."""

    problems = []
    if inv["criticality"] not in CRITICALITIES:
        problems.append(f"{where}: criticality must be one of {sorted(CRITICALITIES)}")
    if not _module_exists(inv["enforcer"]):
        problems.append(f"{where}: enforcer {inv['enforcer']!r} resolves to nothing")
    if inv.get("producer") and not _module_exists(inv["producer"]):
        problems.append(f"{where}: producer {inv['producer']!r} resolves to nothing")
    negatives = inv["negative"]
    if not isinstance(negatives, list) or not negatives:
        problems.append(f"{where}: negative must be a non-empty list")
        return problems
    for proof in negatives + (inv.get("positive") or []):
        reason = _proof_resolves(proof)
        if reason:
            problems.append(f"{where}: proof {reason}")
    if inv["criticality"] == "critical" and set(negatives) <= {"none"}:
        problems.append(f"{where}: critical invariant has no real negative proof")
    return problems


def validate(invariants: list[dict[str, Any]]) -> None:
    problems: list[str] = []
    seen: set[str] = set()
    for index, inv in enumerate(invariants):
        where = inv.get("id", f"entry {index}") if isinstance(inv, dict) else f"entry {index}"
        if not isinstance(inv, dict):
            problems.append(f"{where}: not a mapping")
            continue
        missing = REQUIRED - set(inv)
        extra = set(inv) - REQUIRED - OPTIONAL
        if missing:
            problems.append(f"{where}: missing fields {sorted(missing)}")
        if extra:
            problems.append(f"{where}: unknown fields {sorted(extra)}")
        if missing:
            continue
        if inv["id"] in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(inv["id"])
        if inv["id"] not in TITLES:
            problems.append(f"{where}: no human title in invariants.TITLES")
        problems.extend(_entry_problems(where, inv))
    if problems:
        raise SystemExit(
            "invariant ledger does not hold:\n"
            + "\n".join(f"  - {p}" for p in problems)
        )


def render() -> str:
    invariants = load()
    validate(invariants)
    lines = [
        "# Invariants",
        "",
        "An **invariant** is a promise the press keeps about what it produces "
        "-- something that must be true of a finished book no matter which "
        "book it is. *Every page carries ink. A release ships the exact bytes "
        "the tests approved. A slug can't escape its directory.* This page is "
        "the whole list of those promises.",
        "",
        "Each promise is kept by real code (**enforced by**). Because a guard "
        "you never test is a guard you can't trust, each promise also has a "
        "test that deliberately breaks it and confirms the guard catches the "
        "violation (**tested by**). And each states, honestly, what its guard "
        "does *not* cover (**known limit**), so a narrow check is never "
        "mistaken for a broad one.",
        "",
        "The promises are declared in one file, `quality/invariants.yaml`, and "
        "validated on every build: a promise with no real test -- or a "
        "critical one with no way to prove it can fail -- fails the build. So "
        "this page cannot drift from what the code actually does; it is "
        "generated from that ledger. A few are marked **critical**: breaking "
        "one would let a corrupt or unsafe book through, so they must carry a "
        "test that proves the guard can fail.",
        "",
        "See also the narrative matrix in "
        "[docs/ARCHITECTURE.md](https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md) "
        "and the artifact table in "
        "[docs/REFERENCE.md](https://github.com/clintecker/press/blob/main/docs/REFERENCE.md).",
        "",
    ]
    for inv in sorted(invariants, key=lambda i: i["id"]):
        proofs = ", ".join(f"`{p}`" for p in inv["negative"])
        badge = "critical" if inv["criticality"] == "critical" else "standard"
        lines += [
            f"## {TITLES[inv['id']]}",
            "",
            f"`{inv['id']}` · {badge}",
            "",
            inv["statement"],
            "",
        ]
        lines += _field_table([
            ("If it breaks", inv["risk"]),
            ("Enforced by", f"`{inv['enforcer']}`"),
            ("Tested by", proofs),
            ("Known limit", inv["limitations"]),
        ])
        lines.append("")
    return "\n".join(lines)


def _field_table(rows: list[tuple[str, str]]) -> list[str]:
    """A small two-column label/value table, headerless (its empty header
    row is hidden on the site). A real table aligns and wraps its own
    values -- one small table per record, not one table for everything."""

    lines = ["| | |", "|---|---|"]
    for label, value in rows:
        cell = " ".join(str(value).split()).replace("|", "\\|")
        lines.append(f"| **{label}** | {cell} |")
    return lines


def main() -> int:
    validate(load())
    print(f"Invariant ledger holds: {len(load())} invariants, all references resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
