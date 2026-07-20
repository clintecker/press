"""The fixture provenance auditor.

quality/fixtures.yaml is the source of record for the checked-in
regression fixtures: the deliberately-defective files under
src/press/data/known-bad/ that each trip one checker rule. A fixture is
only trustworthy when it is clear what valid object it came from, which
single mutation it carries, which invariant it must violate, and which
diagnostic proves the right checker noticed it. This module audits that
record. It fails when a fixture file has no manifest entry, when an entry
names a file that has left the tree, when two entries claim the same
file, or when an entry names an invariant the ledger does not define.

Facts once: the expected diagnostic substring lives inline in each
fixture as `<!-- expect: ... -->`, the authority check_the_checkers
already reads to prove the declared rule fires. The manifest restates it
in `expect` and the audit refuses any drift between the two, so a fixture
intended for one invariant must fail for that invariant's diagnostic
rather than an unrelated earlier rejection. The declared checker must
match the enforcer the invariant ledger names, so a fixture cannot claim
the wrong checker caught it.

The manifest and the fixtures ship in different places: the fixtures are
package data, the manifest is repo-only (like scripts/release.sh). When
the manifest is absent the audit returns early, because there is nothing
to hold to account in an installed wheel.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import yamlio

from .check_the_checkers import EXPECT

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT.parent.parent / "quality" / "fixtures.yaml"
KNOWN_BAD = ROOT / "data" / "known-bad"

REQUIRED = {
    "file", "kind", "invariant", "provenance", "mutation",
    "expected_result", "checker", "regenerate",
}
OPTIONAL = {"expect", "source_digest", "generator"}
KINDS = {"source", "damaged-artifact", "recorded-response"}
RESULTS = {"rejected"}


def load(path: Path = MANIFEST) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        data = yamlio.loads(handle.read())
    if not isinstance(data, dict) or not isinstance(data.get("fixtures"), list):
        raise SystemExit(f"{path}: must be a mapping with a 'fixtures' list")
    return data["fixtures"]


def fixture_diagnostic(path: Path) -> str | None:
    """The expected diagnostic substring a fixture declares inline, or
    None when it carries no `<!-- expect: ... -->` comment."""

    match = EXPECT.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def enforcers(invariants: list[dict[str, Any]]) -> dict[str, str]:
    """Map each invariant id to the module its enforcer names, so a
    fixture's declared checker can be reconciled with the ledger."""

    return {
        inv["id"]: str(inv["enforcer"]).partition(".")[0]
        for inv in invariants
        if isinstance(inv, dict) and "id" in inv and "enforcer" in inv
    }


def _entry_problems(
    entry: Any,
    index: int,
    fixture_dir: Path,
    module_for: dict[str, str],
) -> list[str]:
    """Every defect in one manifest entry: schema, then that its file,
    invariant, checker, and inline diagnostic all agree with reality."""

    where = f"entry {index}"
    if not isinstance(entry, dict):
        return [f"{where}: not a mapping"]
    where = f"fixture {entry.get('file', where)!r}"
    problems: list[str] = []
    missing = REQUIRED - set(entry)
    extra = set(entry) - REQUIRED - OPTIONAL
    if missing:
        problems.append(f"{where}: missing fields {sorted(missing)}")
    if extra:
        problems.append(f"{where}: unknown fields {sorted(extra)}")
    if missing:
        return problems

    if entry["kind"] not in KINDS:
        problems.append(f"{where}: kind must be one of {sorted(KINDS)}")
    if entry["expected_result"] not in RESULTS:
        problems.append(f"{where}: expected_result must be one of {sorted(RESULTS)}")

    if entry["invariant"] not in module_for:
        problems.append(f"{where}: names unknown invariant {entry['invariant']!r}")
    elif entry["checker"] != module_for[entry["invariant"]]:
        problems.append(
            f"{where}: checker {entry['checker']!r} is not the enforcer "
            f"{module_for[entry['invariant']]!r} of {entry['invariant']}"
        )

    fixture = fixture_dir / entry["file"]
    if not fixture.is_file():
        problems.append(f"{where}: no such fixture file")
    elif entry["kind"] == "source":
        declared = fixture_diagnostic(fixture)
        if declared is None:
            problems.append(f"{where}: fixture carries no inline expect comment")
        elif "expect" not in entry:
            problems.append(f"{where}: source fixture must declare expect")
        elif entry["expect"] != declared:
            problems.append(
                f"{where}: manifest expect {entry['expect']!r} disagrees with "
                f"the fixture's inline {declared!r}"
            )

    if entry["kind"] in {"damaged-artifact", "recorded-response"} and not (
        entry.get("source_digest") or entry.get("generator")
    ):
        problems.append(
            f"{where}: a {entry['kind']} fixture must record a source_digest or generator"
        )
    return problems


def audit(
    manifest: list[dict[str, Any]],
    fixture_dir: Path,
    invariants: list[dict[str, Any]],
) -> list[str]:
    """Every defect across the manifest: malformed entries, duplicate or
    missing files, unknown invariants, drifted diagnostics, and any
    fixture file on disk that no entry accounts for."""

    module_for = enforcers(invariants)
    problems: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(manifest):
        problems.extend(_entry_problems(entry, index, fixture_dir, module_for))
        if isinstance(entry, dict):
            name = entry.get("file")
            if isinstance(name, str):
                if name in seen:
                    problems.append(f"fixture {name!r}: duplicate manifest entry")
                seen.add(name)

    # Every file, not only markdown: the schema supports damaged-artifact
    # and recorded-response kinds (docx, epub, json), and those must not
    # escape the provenance audit by not ending in .md.
    for fixture in sorted(fixture_dir.rglob("*")):
        if fixture.is_file() and fixture.name not in seen:
            problems.append(
                f"fixture {fixture.name!r}: on disk but absent from quality/fixtures.yaml"
            )
    return problems


def check() -> None:
    """Selftest entry: the shipped manifest accounts for every regression
    fixture and every entry resolves. Absent (installed wheel), there is
    nothing to audit."""

    if not MANIFEST.is_file():
        return
    from . import invariants

    problems = audit(load(), KNOWN_BAD, invariants.load())
    if problems:
        raise SystemExit(
            "fixture provenance manifest does not hold:\n"
            + "\n".join(f"  - {p}" for p in problems)
        )


def main() -> int:
    check()
    print(
        f"Fixture provenance holds: {len(load())} regression fixtures each "
        "carry provenance, invariant, and a reconciled diagnostic"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
