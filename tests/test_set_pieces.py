"""The set-piece constructs: a fenced div (``::: cascade`` / ``verse`` / ``tail``)
holding a line block becomes a staircase, a verse measure, or a serpentine
calligram, in every edition, while the words stay live. A book that uses none
renders unchanged. The filter runs pandoc directly (no LaTeX) to prove the
emitted markup.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

FILTER = (
    Path(__file__).resolve().parent.parent / "src" / "press" / "data" / "lua" / "set-pieces.lua"
)

_needs_pandoc = pytest.mark.skipif(
    shutil.which("pandoc") is None, reason="requires capability: pandoc"
)


def _render(markdown: str, to: str = "latex") -> str:
    args = ["pandoc", "-f", "markdown+smart+fenced_divs", "-t", to, f"--lua-filter={FILTER}"]
    result = subprocess.run(args, input=markdown, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


_CASCADE = "::: cascade\n| First,\n| Second,\n| Third.\n:::\n"
_VERSE = "::: verse\n| Line one\n| Line two\n|\n| Line three\n:::\n"
_TAIL = "::: tail\n| a\n| b\n| c\n| d\n:::\n"


@_needs_pandoc
@pytest.mark.layer("integration")
def test_cascade_is_a_staircase_in_latex():
    out = _render(_CASCADE)
    # each line indented one step more than the last
    assert "\\hspace*{0.00em}" in out
    assert "\\hspace*{2.40em}" in out
    assert "\\hspace*{4.80em}" in out


@_needs_pandoc
@pytest.mark.layer("integration")
def test_verse_is_one_paragraph_with_line_breaks():
    out = _render(_VERSE)
    assert "\\begin{PressVerse}" in out and "\\end{PressVerse}" in out
    # joined by \\ (LineBreak), not separate paragraphs; the blank line doubles
    assert out.count("\\\\") >= 3
    # no bare \\ that would be "no line here to end": every \\ ends a real line
    assert "\\begin{PressVerse}\n\n\\\\" not in out


@_needs_pandoc
@pytest.mark.layer("integration")
def test_tail_is_a_centred_serpentine_with_a_size_ramp():
    out = _render(_TAIL)
    assert "\\begin{center}" in out
    assert "\\hspace*" in out  # per-line horizontal offset
    assert "\\normalsize" in out and "\\tiny" in out  # the head-to-tip taper


@_needs_pandoc
@pytest.mark.layer("integration")
def test_constructs_carry_their_class_into_html():
    assert 'class="cascade"' in _render(_CASCADE, to="html")
    assert 'class="verse"' in _render(_VERSE, to="html")
    assert 'class="tail"' in _render(_TAIL, to="html")


@_needs_pandoc
@pytest.mark.layer("integration")
def test_constructs_degrade_to_a_clean_line_block_in_plaintext():
    # markdown/plain/docx carry no styled geometry: each construct becomes a
    # native line block, so the words stay live and the plain-text edition shows
    # them as verse -- none of the html divs or latex machinery leaking in.
    for md in (_CASCADE, _VERSE, _TAIL):
        out = _render(md, to="markdown")
        assert "| " in out  # a pandoc line block
        assert 'class="' not in out and "padding-left" not in out and "margin-left" not in out
        assert "wrapfigure" not in out and "\\hspace" not in out and "PressVerse" not in out


@_needs_pandoc
@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_ordinary_div_is_untouched():
    # A div without a set-piece class is left exactly as pandoc renders it.
    out = _render("::: note\nJust a note.\n:::\n")
    assert "PressVerse" not in out and "\\hspace*" not in out
