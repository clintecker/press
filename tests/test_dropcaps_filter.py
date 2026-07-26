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
    # An ordinary opener carries an empty lead argument, so the \PressDropCap
    # macro's empty-lead branch compiles to exactly the lettrine call it did
    # before the lead became a separate argument: this is a fix, not a change.
    out = _render("# The machinery\n\nThe machinery supplies everything else.\n")
    assert "\\PressDropCap{}{T}{he}" in out


@pytest.mark.layer("integration")
def test_one_word_opening_paragraph():
    out = _render("# A very short chapter\n\nNo.\n\nThe next paragraph.\n")
    assert "\\PressDropCap{}{N}{o.}" in out


@pytest.mark.layer("integration")
@pytest.mark.invariant("INV-dropcap-opening")
@pytest.mark.proof("positive")
def test_leading_quote_lifts_into_the_lead_not_the_initial():
    # smart wraps a chapter opening on dialogue in a Quoted node; the opening
    # quote is lifted into the drop cap's lead (its own first macro argument,
    # which the TeX layer routes through lettrine's `ante`), never fused into
    # the initial where it would scale up and strand above the letter.
    out = _render('# One\n\n"The machinery," she said.\n')
    assert "\\PressDropCap{\u201c}{T}{he}" in out    # lead = opening curly quote
    assert "\\PressDropCap{\u201cT}" not in out       # never fused into the initial


@pytest.mark.layer("integration")
@pytest.mark.invariant("INV-dropcap-opening")
@pytest.mark.proof("positive")
def test_leading_em_dash_lifts_into_the_lead():
    dash = _render("# Two\n\n---Then the machine started.\n")
    # pandoc turns --- into an em dash, kept as the lead before the initial T.
    assert "\\PressDropCap{\u2014}{T}{hen}" in dash


@pytest.mark.layer("integration")
def test_accented_initial_stays_whole():
    out = _render("# Trois\n\nEvidence, or Ãvidence, is not verification.\n")
    # An ASCII opener still caps cleanly; the grapheme logic is unit-tested
    # in test_dropcaps against real combining marks.
    assert "\\PressDropCap{}{E}{vidence,}" in out


@pytest.mark.layer("integration")
def test_emphasised_opening_is_capped():
    out = _render("# Four\n\n*The machinery* supplies everything else.\n")
    assert "\\PressDropCap{}{T}{he}" in out
    assert "\\emph" in out or "\\textit" in out   # the emphasis is preserved


@pytest.mark.layer("integration")
def test_epigraph_first_block_is_skipped_to_the_real_opening():
    md = ("# Five\n\n> An epigraph that opens the chapter.\n\n"
          "The machinery supplies everything else.\n")
    out = _render(md)
    # The blockquote is not capped; the first prose paragraph after it is.
    assert "\\PressDropCap{}{T}{he}" in out
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
    # An ordinary opener emits no lead span at all, so its HTML is byte-for-byte
    # what it was before the lead became its own span.
    assert "drop-cap-lead" not in out


@pytest.mark.layer("integration")
def test_html_quote_opener_hangs_the_lead_in_its_own_span():
    # The opening quote hangs in its own .drop-cap-lead span beside the big
    # initial, not inside the .drop-cap span where it would strand above it.
    out = _render('# One\n\n"The machinery," she said.\n', to="html")
    assert 'class="drop-cap-lead">“<' in out
    assert 'class="drop-cap">T<' in out


@pytest.mark.layer("integration")
def test_ornate_marks_the_html_opening_for_its_web_fallback():
    # An ornate opening carries a second class so the reader stylesheet can give
    # the initial its degraded decorative treatment (the print foliate font
    # cannot cross to the browser). LaTeX carries no such class -- the ornate
    # font is applied in the centralized \PressDropCap macro instead.
    html = _render("# One\n\nThe machinery here.\n", to="html", style="ornate")
    assert 'class="chapter-opening ornate"' in html
    latex = _render("# One\n\nThe machinery here.\n", style="ornate")
    assert "\\PressDropCap{}{T}{he}" in latex


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
        # A chapter opening on dialogue: the opening quote must ride lettrine's
        # `ante` (not scale up into the initial), which only the real toolchain
        # can prove renders.
        .with_chapter("03-dialogue.md", "# The dialogue\n\n"
                      '"The machinery supplies everything else," she said, and '
                      "the sentence runs on far enough to wrap. " * 3)
        .build(tmp_path)
    )
    with handle.use():
        build.build_target("pdf")
        pdf = handle.root / "dist" / f"{handle.slug}.pdf"
        assert pdf.is_file() and pdf.stat().st_size > 0


def _yinit_available() -> bool:
    if shutil.which("kpsewhich") is None:
        return False
    got = subprocess.run(["kpsewhich", "yfonts.sty"], capture_output=True, text=True)
    return bool(got.stdout.strip())


@pytest.mark.layer("integration")
@pytest.mark.skipif(
    any(shutil.which(t) is None for t in ("pandoc", "lualatex", "latexmk"))
    or not _lettrine_available() or not _yinit_available(),
    reason="requires capability: pandoc, lualatex, latexmk, lettrine, and yfonts "
           "(texlive-fonts-extra in the toolchain image) for the ornate initial",
)
def test_ornate_book_renders_to_pdf(tmp_path):
    # The ornate path in the real toolchain: yfonts loads and the yinit initial
    # font resolves, so an ornate chapter opening compiles to a valid PDF.
    from tests import factories

    from press import build

    handle = (
        factories.BookFactory(slug="ornate-fixture", title="Ornate Fixture")
        .with_sentinels("the machinery supplies everything else")
        .with_metadata(**{"chapter-opening": {"style": "ornate", "lines": 3}})
        .with_chapter("01-one.md", "# The machinery\n\n"
                      "The machinery supplies everything else, and this opening "
                      "runs long enough to wrap beside the decorated initial. " * 3)
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
    assert "\\PressDropCap{}{R}{eal}" in out        # the chapter is capped
    assert "\\PressDropCap{}{A}" not in out         # the appendix is not
    assert "\\section*{Also by Someone}" in out     # and stays unnumbered
