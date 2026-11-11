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


def _render(markdown: str, to: str = "latex", filtered: bool = True) -> str:
    args = [
        "pandoc",
        "-f",
        "markdown+smart",
        "-t",
        to,
        "--top-level-division=chapter",
        "--number-sections",
    ]
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
    assert "\\PressListOfFigures" in _render(_MIXED)
    plates_only = _render(
        "# One\n\n![A plate](assets/w/x.png)\n\n![Another](assets/w/y.png){.plate}\n"
    )
    assert "\\PressListOfFigures" not in plates_only


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
