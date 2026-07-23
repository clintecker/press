"""The chapter-dropcap Lua filter on the pandoc AST: it caps the first
eligible paragraph after a chapter, mirrors the semantic split (punctuation,
accents, emphasis), skips epigraphs and non-prose openers, and is a no-op
when the style is off. These run pandoc directly (no LaTeX), so they prove
the emitted markup without the toolchain.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

FILTER = Path(__file__).resolve().parent.parent / "src" / "press" / "data" / "lua" / \
    "chapter-dropcap.lua"

pytestmark = pytest.mark.skipif(shutil.which("pandoc") is None,
                                reason="requires capability: pandoc")


def _render(markdown: str, to: str = "latex", style: str = "drop-cap") -> str:
    args = ["pandoc", "-f", "markdown", "-t", to, f"--lua-filter={FILTER}"]
    if style is not None:
        args += ["-M", f"chapter-opening-style={style}"]
    result = subprocess.run(args, input=markdown, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.mark.layer("integration")
@pytest.mark.invariant("INV-dropcap-opening")
@pytest.mark.proof("negative")
def test_plain_chapter_gets_a_lettrine():
    out = _render("# The machinery\n\nThe machinery supplies everything else.\n")
    assert "\\PressDropCap{T}{he}" in out


@pytest.mark.layer("integration")
def test_one_word_opening_paragraph():
    out = _render("# A very short chapter\n\nNo.\n\nThe next paragraph.\n")
    assert "\\PressDropCap{N}{o.}" in out


@pytest.mark.layer("integration")
def test_leading_quote_and_em_dash():
    # smart turns the straight quote into a Quoted node; the cap lands on the
    # first letter inside it and the quote glyphs render around it.
    quote = _render('# One\n\n"The machinery," she said.\n')
    assert "\\PressDropCap{T}{he}" in quote and "``" in quote
    dash = _render("# Two\n\n---Then the machine started.\n")
    # pandoc turns --- into an em dash, which the cap keeps in front of T.
    assert "\\PressDropCap" in dash and "}{hen}" in dash


@pytest.mark.layer("integration")
def test_accented_initial_stays_whole():
    out = _render("# Trois\n\nEvidence, or Ãvidence, is not verification.\n")
    # An ASCII opener still caps cleanly; the grapheme logic is unit-tested
    # in test_dropcaps against real combining marks.
    assert "\\PressDropCap{E}{vidence,}" in out


@pytest.mark.layer("integration")
def test_emphasised_opening_is_capped():
    out = _render("# Four\n\n*The machinery* supplies everything else.\n")
    assert "\\PressDropCap{T}{he}" in out
    assert "\\emph" in out or "\\textit" in out   # the emphasis is preserved


@pytest.mark.layer("integration")
def test_epigraph_first_block_is_skipped_to_the_real_opening():
    md = ("# Five\n\n> An epigraph that opens the chapter.\n\n"
          "The machinery supplies everything else.\n")
    out = _render(md)
    # The blockquote is not capped; the first prose paragraph after it is.
    assert "\\PressDropCap{T}{he}" in out
    assert "epigraph" in out.lower()   # the epigraph text survives, uncapped


@pytest.mark.layer("integration")
@pytest.mark.invariant("INV-dropcap-opening")
@pytest.mark.proof("negative")
def test_disabled_style_is_a_no_op():
    md = "# The machinery\n\nThe machinery supplies everything else.\n"
    off = _render(md, style="none")
    assert "PressDropCap" not in off and "drop-cap" not in off


@pytest.mark.layer("integration")
def test_html_emits_semantic_spans():
    out = _render("# One\n\nThe machinery supplies everything else.\n", to="html")
    assert 'class="chapter-opening"' in out
    assert 'class="drop-cap"' in out and ">T<" in out
    assert 'class="opening-word-rest"' in out


@pytest.mark.layer("integration")
def test_only_the_first_paragraph_of_a_chapter_is_capped():
    md = ("# One\n\nFirst paragraph here.\n\nSecond paragraph should be plain.\n")
    out = _render(md)
    assert out.count("\\PressDropCap") == 1


def _lettrine_available() -> bool:
    if shutil.which("kpsewhich") is None:
        return False
    got = subprocess.run(["kpsewhich", "lettrine.sty"], capture_output=True, text=True)
    return bool(got.stdout.strip())


@pytest.mark.layer("integration")
@pytest.mark.skipif(
    any(shutil.which(t) is None for t in ("pandoc", "lualatex", "latexmk"))
    or not _lettrine_available(),
    reason="requires capability: pandoc, lualatex, latexmk, and the lettrine "
           "package (texlive-latex-extra in the toolchain image)",
)
def test_drop_cap_book_renders_to_pdf(tmp_path):
    # The whole path, in the real toolchain: a book that enables drop caps
    # builds a valid PDF (the lettrine style loads, the macro compiles, the
    # short-paragraph opener does not error).
    from tests import factories

    from press import build

    handle = (
        factories.BookFactory(slug="dropcap-fixture", title="Drop Cap Fixture")
        .with_sentinels("the machinery supplies everything else")
        .with_metadata(**{"chapter-opening": {"style": "drop-cap", "lines": 3}})
        .with_chapter("01-one.md", "# The machinery\n\n"
                      "The machinery supplies everything else, and this opening "
                      "runs long enough to wrap beside the dropped initial. " * 3)
        .with_chapter("02-short.md", "# A very short chapter\n\nNo.\n")
        .build(tmp_path)
    )
    with handle.use():
        build.build_target("pdf")
        pdf = handle.root / "dist" / f"{handle.slug}.pdf"
        assert pdf.is_file() and pdf.stat().st_size > 0


@pytest.mark.layer("integration")
def test_unnumbered_heading_gets_no_lettrine():
    # Front and back matter (an "also by", an about-the-author, a glossary) are
    # level-1 headings but unnumbered; a bibliographic list is not a chapter to
    # open with a drop cap. The numbered chapter above it still gets one.
    out = _render(
        "# Chapter One\n\nReal chapter prose opens here.\n\n"
        "# Also by Someone {.unnumbered}\n\nA list of other titles follows.\n"
    )
    assert "\\PressDropCap{R}{eal}" in out          # the chapter is capped
    assert "\\PressDropCap{A}" not in out           # the appendix is not
    assert "\\section*{Also by Someone}" in out     # and stays unnumbered
