"""The typographic-spacing filter binds a curated set of abbreviations to what
follows them with a non-breaking space (a title before a name, a reference
before a number, initials to each other), and leaves ordinary prose -- every
sentence-ending period included -- exactly as typed. The filter runs pandoc
directly (no LaTeX) to prove the emitted markup.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

FILTER = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "press"
    / "data"
    / "lua"
    / "typographic-spacing.lua"
)

_needs_pandoc = pytest.mark.skipif(
    shutil.which("pandoc") is None, reason="requires capability: pandoc"
)


def _render(markdown: str, to: str = "latex") -> str:
    args = ["pandoc", "-f", "markdown", "-t", to, f"--lua-filter={FILTER}"]
    result = subprocess.run(args, input=markdown, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


@_needs_pandoc
@pytest.mark.layer("integration")
def test_titles_refs_and_initials_tie_in_latex():
    out = _render("Mr. Smith read p. 42 and Fig. 3, per C. L. Dodgson.")
    assert "Mr.~Smith" in out  # title + name
    assert "p.~42" in out  # reference + number
    assert "Fig.~3" in out
    assert "C.~L.~Dodgson" in out  # initials chain, then tie to the name


@_needs_pandoc
@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_ordinary_prose_and_sentence_periods_are_untied():
    # No title, reference, or initial: nothing binds. A period that is a full
    # stop is never swept up, even before a capital or a digit.
    out = _render("The dog ran. I said no. It cost 5. Then She left.")
    assert "~" not in out


@_needs_pandoc
@pytest.mark.layer("integration")
def test_ties_carry_into_html_as_nbsp():
    # pandoc writes the tie as a literal U+00A0 in HTML (and EPUB).
    out = _render("See Fig. 3 by C. L. Dodgson.", to="html")
    assert chr(0xA0) in out
