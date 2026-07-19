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

import yaml

REQUIRED = {
    "id", "statement", "risk", "criticality", "owner", "enforcer",
    "layers", "negative", "ci_tier", "limitations",
}
OPTIONAL = {"producer", "positive"}
CRITICALITIES = {"critical", "standard"}
ROOT = Path(__file__).resolve().parent
LEDGER = ROOT.parent.parent / "quality" / "invariants.yaml"
KNOWN_BAD = ROOT / "data" / "known-bad"


def load(path: Path = LEDGER) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
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
        "Generated from quality/invariants.yaml; do not edit by hand.",
        "Run `python3 -m press selftest --write-docs` after changing the",
        "ledger. Each row traces an invariant to where it is enforced, the",
        "proof it can fail, and the honest limit of that proof.",
        "",
        "See also the narrative matrix in "
        "[docs/ARCHITECTURE.md](https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md) "
        "and the artifact table in "
        "[docs/REFERENCE.md](https://github.com/clintecker/press/blob/main/docs/REFERENCE.md).",
        "",
        "| id | invariant | enforced at | proof it can fail | limitation |",
        "|---|---|---|---|---|",
    ]
    for inv in sorted(invariants, key=lambda i: i["id"]):
        proofs = ", ".join(inv["negative"])
        crit = " (critical)" if inv["criticality"] == "critical" else ""
        lines.append(
            f"| {inv['id']}{crit} | {inv['statement']} | "
            f"`{inv['enforcer']}` | {proofs} | {inv['limitations']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    validate(load())
    print(f"Invariant ledger holds: {len(load())} invariants, all references resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
