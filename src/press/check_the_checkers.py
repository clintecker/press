"""Prove the checkers can fail.

Each fixture violates one rule a checker claims to enforce. A checker that
returns success against its fixture is an untested claim, and this script
fails the build. Universal fixtures ship with the press; a book adds its own
under tests/known-bad/ (for house rules like banned project names), and every
fixture must be rejected by the style audit or the jargon lint.
"""

from __future__ import annotations

import contextlib
import io
import subprocess
import sys
from pathlib import Path

from . import booklib, style_audit


def rejected(fixture: Path) -> bool:
    """True if at least one prose checker fails the fixture."""

    with contextlib.redirect_stdout(io.StringIO()):
        if style_audit.main([str(fixture)]) != 0:
            return True
    allow = booklib.house_rules().get("jargon-allow") or []
    command = [
        sys.executable, "-m", "press.jargon_lint",
        "--fail-on", "rewrite",
        *[arg for term in allow for arg in ("--allow", term)],
        str(fixture),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    return result.returncode != 0


def main() -> int:
    fixtures = sorted((booklib.DATA / "known-bad").glob("*.md"))
    book_fixtures = booklib.root() / "tests" / "known-bad"
    if book_fixtures.is_dir():
        fixtures.extend(sorted(book_fixtures.glob("*.md")))

    failures: list[str] = []
    for fixture in fixtures:
        if rejected(fixture):
            continue
        failures.append(f"{fixture.name}: no checker rejected a known-bad fixture")

    if failures:
        print("Checker self-test failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"Checker self-test passed: {len(fixtures)} known-bad fixtures rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
