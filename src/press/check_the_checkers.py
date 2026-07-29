"""Prove the checkers can fail, and fail for the stated reason.

Each fixture violates one rule a checker claims to enforce and names
that rule in its first line (`<!-- expect: em dash -->`). Any-rejection
was not proof: an accidentally over-broad checker could reject every
fixture while the intended rule quietly disappeared. The harness now
requires the declared diagnostic to fire, reports any additional
diagnostics for review, and holds a known-good fixture that no checker
may reject. Book fixtures under tests/known-bad/ use the same
expectation comment; one without it falls back to any-rejection with a
note.
"""

from __future__ import annotations

import contextlib
import io
import re
import sys
from pathlib import Path

from . import adapters, booklib, style_audit

EXPECT = re.compile(r"<!--\s*expect:\s*(.+?)\s*-->")
"""The declared-diagnostic convention: a fixture's first line names the
rule it must trip. fixture_provenance imports this so the manifest and
the checker agree on how a fixture states its expected diagnostic."""


def diagnostics(fixture: Path) -> list[str]:
    """Every diagnostic any prose checker emits for the fixture."""

    found: list[str] = []
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        style_audit.main([str(fixture)])
    found.extend(line.strip() for line in buffer.getvalue().splitlines() if fixture.name in line)
    allow = booklib.house_rules().get("jargon-allow") or []
    command = [
        sys.executable,
        "-m",
        "press.jargon_lint",
        "--fail-on",
        "rewrite",
        *[arg for term in allow for arg in ("--allow", term)],
        str(fixture),
    ]
    result = adapters.process_runner.run(command, capture=True, check=False)
    if result.returncode != 0:
        output = result.stdout.decode("utf-8", errors="replace") + result.stderr.decode(
            "utf-8", errors="replace"
        )
        found.extend(
            f"jargon: {line.strip()}" for line in output.splitlines() if "rewrite:" in line
        )
    return found


def _collect_known_bad_fixtures() -> list[Path]:
    """Every known-bad fixture: the packaged universals plus the book's own."""

    fixtures = sorted((booklib.DATA / "known-bad").glob("*.md"))
    book_fixtures = booklib.root() / "tests" / "known-bad"
    if book_fixtures.is_dir():
        fixtures.extend(sorted(book_fixtures.glob("*.md")))
    return fixtures


def _check_known_bad(fixture: Path) -> tuple[list[str], int]:
    """Verify one known-bad fixture trips its declared rule.

    Returns the fixture's failures (empty when it passed) and the count of
    extra, undeclared diagnostics it drew (which are also printed as notes).
    """

    expected = EXPECT.search(fixture.read_text(encoding="utf-8"))
    found = diagnostics(fixture)
    if expected is None:
        if not found:
            return [
                f"{fixture.name}: no checker rejected a known-bad fixture "
                "(and it declares no expected rule)"
            ], 0
        return [], 0
    rule = expected.group(1)
    matching = [d for d in found if rule.lower() in d.lower()]
    if not matching:
        others = "; ".join(found[:3]) or "no diagnostics at all"
        return [f"{fixture.name}: expected rule {rule!r} did not fire ({others})"], 0
    if len(found) > len(matching):
        for extra in (d for d in found if rule.lower() not in d.lower()):
            print(f"  note: {fixture.name} also drew: {extra}")
        return [], len(found) - len(matching)
    return [], 0


def _check_known_good() -> list[str]:
    """No checker may reject any known-good fixture."""

    failures: list[str] = []
    for clean in sorted((booklib.DATA / "known-good").glob("*.md")):
        found = diagnostics(clean)
        if found:
            failures.append(
                f"{clean.name}: a checker rejected the known-good fixture: " + "; ".join(found[:3])
            )
    return failures


def main() -> int:
    fixtures = _collect_known_bad_fixtures()

    failures: list[str] = []
    extras = 0
    for fixture in fixtures:
        fixture_failures, fixture_extras = _check_known_bad(fixture)
        failures.extend(fixture_failures)
        extras += fixture_extras

    failures.extend(_check_known_good())

    if failures:
        print("Checker self-test failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(
        f"Checker self-test passed: {len(fixtures)} known-bad fixtures each "
        "tripped their declared rule, known-good fixture accepted"
        + (f", {extras} extra diagnostics noted" if extras else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
