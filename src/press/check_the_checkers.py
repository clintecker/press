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
import subprocess
import sys
from pathlib import Path

from . import booklib, style_audit

EXPECT = re.compile(r"<!--\s*expect:\s*(.+?)\s*-->")


def diagnostics(fixture: Path) -> list[str]:
    """Every diagnostic any prose checker emits for the fixture."""

    found: list[str] = []
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        style_audit.main([str(fixture)])
    found.extend(
        line.strip() for line in buffer.getvalue().splitlines()
        if fixture.name in line
    )
    allow = booklib.house_rules().get("jargon-allow") or []
    command = [
        sys.executable, "-m", "press.jargon_lint",
        "--fail-on", "rewrite",
        *[arg for term in allow for arg in ("--allow", term)],
        str(fixture),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        found.extend(
            f"jargon: {line.strip()}"
            for line in (result.stdout + result.stderr).splitlines()
            if "rewrite:" in line
        )
    return found


def main() -> int:
    fixtures = sorted((booklib.DATA / "known-bad").glob("*.md"))
    book_fixtures = booklib.root() / "tests" / "known-bad"
    if book_fixtures.is_dir():
        fixtures.extend(sorted(book_fixtures.glob("*.md")))

    failures: list[str] = []
    extras = 0
    for fixture in fixtures:
        expected = EXPECT.search(fixture.read_text(encoding="utf-8"))
        found = diagnostics(fixture)
        if expected is None:
            if not found:
                failures.append(
                    f"{fixture.name}: no checker rejected a known-bad fixture "
                    "(and it declares no expected rule)"
                )
            continue
        rule = expected.group(1)
        matching = [d for d in found if rule.lower() in d.lower()]
        if not matching:
            others = "; ".join(found[:3]) or "no diagnostics at all"
            failures.append(
                f"{fixture.name}: expected rule {rule!r} did not fire ({others})"
            )
        elif len(found) > len(matching):
            extras += len(found) - len(matching)
            for extra in (d for d in found if rule.lower() not in d.lower()):
                print(f"  note: {fixture.name} also drew: {extra}")

    for clean in sorted((booklib.DATA / "known-good").glob("*.md")):
        found = diagnostics(clean)
        if found:
            failures.append(
                f"{clean.name}: a checker rejected the known-good fixture: "
                + "; ".join(found[:3])
            )

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
