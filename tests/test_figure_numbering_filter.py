"""The figure-numbering Lua filter on the pandoc AST: it numbers only the
explicitly-declared informative kinds (chapter.N), leaves plates and bare
images untouched (the byte-identity guarantee), splits the illustration lists,
resolves @fig:id cross-references, and carries the placement vocabulary. These
run pandoc directly (no LaTeX), so they prove the emitted markup without the
toolchain.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests import lua_coverage

FILTER = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "press"
    / "data"
    / "lua"
    / "figure-numbering.lua"
)

pytestmark = lua_coverage.needs_pandoc


def _render(
    markdown: str, to: str = "latex", filtered: bool = True, standalone: bool = False
) -> str:
    args = [
        "pandoc",
        "-f",
        "markdown+smart",
        "-t",
        to,
        "--top-level-division=chapter",
        "--number-sections",
    ]
    if standalone:
        args += ["-s", "-V", "documentclass=scrbook"]
    if filtered:
        args.append(lua_coverage.filter_arg(FILTER))
    result = subprocess.run(args, input=markdown, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


_MIXED = (
    "# First chapter\n\nText with a reference to @fig:press here.\n\n"
    "![A bare plate](assets/w/x.png)\n\n"
    "![The press](assets/f/press.jpg){#fig:press .figure width=half-measure}\n\n"
    "# Second chapter\n\n"
    "![Yields](assets/f/y.svg){#fig:yields .chart}\n\n"
    "![A named plate](assets/w/z.png){.plate}\n"
)


@pytest.mark.layer("integration")
@pytest.mark.proof("positive")
def test_declared_informative_kinds_are_numbered_by_chapter():
    out = _render(_MIXED)
    assert "\\textbf{Figure~1.1.}" in out  # figure, chapter 1
    assert "\\textbf{Figure~2.1.}" in out  # chart, chapter 2, resets
    assert "\\addcontentsline{lof2}{figure}{\\protect\\numberline{1.1}" in out
    assert "\\addcontentsline{lof2}{figure}{\\protect\\numberline{2.1}" in out


@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_plates_and_bare_images_are_never_numbered():
    out = _render(_MIXED)
    # The bare and .plate images keep pandoc's ordinary \caption (List of
    # Plates), never a "Figure N" label and never a lof2 line.
    assert "\\caption{A bare plate}" in out
    assert "\\caption{A named plate}" in out
    assert "Figure~1.2" not in out and "Figure~2.2" not in out


@pytest.mark.layer("integration")
def test_list_of_figures_is_emitted_only_when_numbered_figures_exist():
    assert "\\PressListOfFigurestrue" in _render(_MIXED, standalone=True)
    plates_only = _render(
        "# One\n\n![A plate](assets/w/x.png)\n\n![Another](assets/w/y.png){.plate}\n",
        standalone=True,
    )
    assert "\\PressListOfFigures" not in plates_only


@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_list_of_figures_is_front_matter_not_a_body_block():
    """#289: the list printed as the first body block landed after \\mainmatter
    and took arabic folios 1 and 2 ahead of the Preface. The filter now only
    raises the flag, ahead of the contents; the header prints the list before
    \\mainmatter, so the body never carries it."""
    out = _render(_MIXED, standalone=True)
    flag = out.index("\\PressListOfFigurestrue")
    assert flag < out.index("\\mainmatter")
    body = out[out.index("\\mainmatter") :]
    assert "\\PressListOfFigures" not in body
    # an author's own include-before survives beside the flag
    kept = _render("---\ninclude-before: \\AuthorLine\n---\n\n" + _MIXED, standalone=True)
    assert "\\AuthorLine" in kept and "\\PressListOfFigurestrue" in kept


@pytest.mark.layer("integration")
def test_cross_reference_resolves_to_the_number():
    latex = _render(_MIXED)
    assert "\\hyperref[fig:press]{Figure~1.1}" in latex
    html = _render(_MIXED, to="html")
    assert '<a href="#fig:press">Figure 1.1</a>' in html
    assert 'id="fig:press"' in html


@pytest.mark.layer("integration")
def test_width_measure_becomes_a_relative_graphics_width():
    latex = _render(_MIXED)
    assert "width=0.5\\linewidth" in latex
    html = _render(_MIXED, to="html")
    assert "width:50" in html or 'width="50%"' in html


@pytest.mark.layer("integration")
@pytest.mark.parametrize(
    ("width", "option"),
    [
        # a percentage becomes the same fraction of the measure
        ("50%", "width=0.5\\linewidth"),
        # a raw length outside the vocabulary passes through unchanged
        ("3in", "width=3in"),
    ],
)
def test_a_numbered_figure_honours_a_percent_or_raw_width(width, option):
    out = _render(f"# One\n\n![Cap.](x.png){{.figure width={width}}}\n")
    assert f"\\includegraphics[keepaspectratio,{option}]{{x.png}}" in out


@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_a_book_with_no_numbered_figures_is_byte_identical():
    # The load-bearing guarantee: adding the filter changes nothing for a book
    # that declares no numbered figure (bare images and plates only).
    doc = (
        "# One\n\nProse here, long enough to be real.\n\n"
        "![A caption](assets/w/x.png)\n\n"
        "![A sized plate](assets/w/y.png){width=2.4in}\n\n"
        "![A named plate](assets/w/z.png){.plate}\n"
    )
    for fmt in ("latex", "html"):
        assert _render(doc, to=fmt, filtered=False) == _render(doc, to=fmt)


@pytest.mark.layer("integration")
def test_a_decorative_image_carries_no_descriptive_alt():
    # A decorative ornament must not announce its words to a screen reader:
    # the alt is emptied (pandoc renders an empty alt as no alt attribute at
    # all, which is the same "skip me" signal) and never the caption text.
    html = _render("# One\n\n![An ornament](assets/deco.png){.figure decorative=true}\n", to="html")
    assert 'alt="An ornament"' not in html and "data-decorative" not in html
    # Decorative wins over numbering: it earns no "Figure N".
    assert "Figure 1.1" not in html and "Figure~1.1" not in html


@pytest.mark.layer("integration")
def test_figures_inside_divs_and_quotes_are_numbered_in_sequence():
    # The walk descends into fenced divs and block quotes, so a figure there
    # counts in the chapter's sequence like any other.
    out = _render("# One\n\n::: aside\n![Cap.](x.png){.figure}\n:::\n\n> ![Q.](q.png){.chart}\n")
    assert "\\textbf{Figure~1.1.}}\\enspace Cap." in out
    assert "\\begin{quote}\n\\begin{figure}[H]" in out
    assert "\\textbf{Figure~1.2.}}\\enspace Q." in out


@pytest.mark.layer("integration")
def test_an_unnumbered_chapter_does_not_advance_the_chapter_count():
    # A {.unnumbered} preface is not chapter 1: a figure before the first
    # numbered chapter takes a bare sequence number, and the first real
    # chapter's figure is still 1.1.
    out = _render(
        "# Preface {.unnumbered}\n\n![Cap.](x.png){.figure}\n\n# One\n\n![Next.](y.png){.figure}\n"
    )
    assert "\\textbf{Figure~1.}}\\enspace Cap." in out
    assert "\\textbf{Figure~1.1.}}\\enspace Next." in out


@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
@pytest.mark.parametrize("fmt", ["latex", "html"])
def test_a_citation_that_is_not_a_figure_is_left_alone(fmt):
    # Only a known figure id resolves; an ordinary citation and an unknown
    # @fig: id pass through untouched, never as a dangling "Figure".
    out = _render(_MIXED + "\nSee @smith and @fig:none.\n", to=fmt)
    assert "@smith" in out and "@fig:none" in out
    assert "#fig:none" not in out


@pytest.mark.layer("integration")
def test_unnumbered_chapter_sets_its_own_running_head_mark():
    """#282: \\chapter* sets no mark, so an unnumbered chapter's pages carried
    the last numbered chapter's head. The filter follows each unnumbered
    chapter heading (and only those) with the header's mark macro, the title
    set without its footnote."""
    out = _render(
        "# One\n\nx\n\n# Appendix A: *Extra*[^n] {.unnumbered}\n\ny\n\n"
        "## A section {.unnumbered}\n\nz\n\n[^n]: A note.\n"
    )
    assert "\\PressUnnumberedChapter{Appendix A: \\emph{Extra}}" in out
    assert out.count("\\PressUnnumberedChapter") == 1  # not after One, not a section
    assert out.index("\\chapter*") < out.index("\\PressUnnumberedChapter")
    html = _render("# Preface {.unnumbered}\n\nx\n", to="html")
    assert "PressUnnumberedChapter" not in html


@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_unnumbered_chapter_contributes_no_chapter_number():
    """#288: a colophon after Chapter 2 numbered its figure 2.2, counting on
    from the last numbered chapter. An unnumbered chapter takes no chapter
    number: its figures number plainly, on one book-wide sequence shared with
    any front part (so they never collide), and its plates list with no
    number (the header's \\PressUnnumberedChapter empties the list format;
    \\PressNumberedChapter restores it at the next numbered chapter)."""
    out = _render(
        "# Preface {.unnumbered}\n\n![Early](a.png){.figure}\n\n"
        "# One\n\n![First](b.png){.figure}\n\n"
        "# Two\n\n![Second](c.png){.figure}\n\n"
        "# Colophon {.unnumbered}\n\n![Late](d.png){.figure}\n\n![A plate](e.png)\n\n"
        "# Three\n\n![Third](f.png){.figure}\n"
    )
    assert "\\textbf{Figure~1.}}\\enspace Early" in out
    assert "\\textbf{Figure~1.1.}}\\enspace First" in out
    assert "\\textbf{Figure~2.1.}}\\enspace Second" in out
    assert "\\textbf{Figure~2.}}\\enspace Late" in out
    assert "Figure~2.2" not in out
    assert "\\textbf{Figure~3.1.}}\\enspace Third" in out
    # the list format is restored once, at the first numbered chapter after
    # each unnumbered one (One and Three), never after Two
    assert out.count("\\PressNumberedChapter") == 2
    one = out.index("\\chapter{One}")
    assert out.index("\\PressNumberedChapter", one) < out.index("\\chapter{Two}")
    plain = _render("# One\n\n![First](b.png){.figure}\n\n# Two\n\nx\n")
    assert "\\PressNumberedChapter" not in plain


_WIDE_CELL = "a cell long enough to wrap onto a second line in its column " * 2


@pytest.mark.layer("integration")
def test_table_is_kept_with_its_head_and_first_two_rows():
    """#286: a longtable head stranded at a page foot with one row. Every
    table is preceded by a \\Needspace sized to its caption, head, and first
    two body rows, estimated from the cells: a narrow table asks for little,
    a table of wrapping rows for more. An ordinary paragraph gets nothing."""
    narrow = _render("Prose.\n\n| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n| 5 | 6 |\n")
    # \LTpre 1 + head 1 + rules 1 + two one-line rows
    assert "\\Needspace{5\\baselineskip}" in narrow
    assert narrow.index("\\Needspace") < narrow.index("\\begin{longtable}")
    assert narrow.count("\\Needspace") == 1
    rows = "\n".join(f"| r{k} | {_WIDE_CELL}|" for k in range(4))
    wide = _render(
        f"| key | Meaning |\n|------------------|{'-' * 50}|\n{rows}\n\n"
        "Table: A caption over the table\n"
    )
    # \LTpre 1 + caption 1.5 + head 1 + rules 1 + two rows of 3 lines each
    assert "\\Needspace{11\\baselineskip}" in wide
    one_row = _render("| a | b |\n|---|---|\n| 1 | 2 |\n")
    assert "\\Needspace{4\\baselineskip}" in one_row
    assert "Needspace" not in _render("| a |\n|---|\n| 1 |\n", to="html")


@pytest.mark.layer("integration")
def test_last_two_contents_entries_carry_over_together():
    """#291: a one-line Contents overflow set the last entry alone on a page.
    The second-to-last listed chapter (an unlisted heading makes no entry and
    is not counted) writes a \\Needspace into the .toc ahead of its entry."""
    keep = "\\addtocontents{toc}{\\protect\\Needspace{3\\baselineskip}}"
    out = _render(
        "# One\n\nx\n\n# Two\n\nx\n\n::: part\n# Three {.unnumbered}\n\nx\n:::\n\n"
        "# Hidden {.unnumbered .unlisted}\n\nx\n"
    )
    assert out.count(keep) == 1
    assert out.index("{One}") < out.index(keep) < out.index("{Two}")
    assert keep not in _render("# Only\n\nx\n")
    assert "Needspace" not in _render("# One\n\nx\n\n# Two\n\nx\n", to="html")
