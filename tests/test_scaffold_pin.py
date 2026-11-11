"""A fresh book pins one press major, in both places the press reads it.

The scaffold template names the press major twice: in ``requirements.txt``
for local installs and in the book's CI workflow for the reusable build. If
the two ever disagree, ``press migrate`` refuses the book as split across
majors before an author has written a word. This pins the template to a
single, current major so a new major's template bump cannot land half-done.
"""

from __future__ import annotations

import re
from pathlib import Path

from press import booklib, migrate

TEMPLATE = booklib.DATA / "template"
PIN = re.compile(r"clintecker/press(?:/\.github/workflows/build\.yml)?@v(\d+)\b")


def _majors(text: str) -> set[int]:
    return {int(m) for m in PIN.findall(text)}


def test_template_pins_exactly_one_press_major():
    requirements = (TEMPLATE / "requirements.txt").read_text(encoding="utf-8")
    workflow = (TEMPLATE / "dot-github" / "workflows" / "book.yml").read_text(encoding="utf-8")
    assert _majors(requirements) == _majors(workflow)
    assert len(_majors(requirements)) == 1


def test_template_pins_the_current_major():
    """The template must point a new book at the newest major, never a
    retired one: CHANGELOG.md's newest versioned section names it."""

    changelog = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
    if not changelog.is_file():  # an installed wheel carries no changelog
        return
    sections = re.findall(r"^## \[(\d+)\.\d+\.\d+\]", changelog.read_text(encoding="utf-8"), re.M)
    unreleased_major = re.search(r"^## \[Unreleased\]", changelog.read_text(encoding="utf-8"), re.M)
    newest = int(sections[0]) if sections else 0
    template_major = next(iter(_majors((TEMPLATE / "requirements.txt").read_text(encoding="utf-8"))))
    # Between rolling the changelog and tagging, the template may already
    # name the major the next section will carry; it may never lag.
    assert template_major >= newest, (template_major, newest, bool(unreleased_major))


def test_scaffolded_book_diagnoses_as_one_major(scaffolded_book):
    diagnosis = migrate.diagnose(scaffolded_book)
    assert not diagnosis.problems
    assert diagnosis.from_major is not None
