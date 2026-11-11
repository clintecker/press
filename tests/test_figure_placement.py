"""Figure placement rendering (figure-numbering.lua). A figure or plate that
declares ``place=`` is laid by the house: wrap-inner/outer fuse a wrapfigure to
the START of the following paragraph so the running text wraps around it (a
standalone wrapfigure wraps nothing); full-bleed/frontispiece take their own
*cleared* leaf, not a deferred float. Placement is a print concern, so on the
reflowable web a placed figure is a clean in-flow figure with no house-only
attributes leaked. A plate that asks for no placement is byte-identical. The
filter runs pandoc directly.
"""

from __future__ import annotations

import re
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

_needs_pandoc = lua_coverage.needs_pandoc


def _render(markdown: str, to: str = "latex") -> str:
    args = ["pandoc", "-f", "markdown+fenced_divs", "-t", to, lua_coverage.filter_arg(FILTER)]
    result = subprocess.run(args, input=markdown, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


_WRAP = (
    "# C\n\nBefore.\n\n"
    "![A cap.](x.png){.figure width=half-measure place=wrap-inner "
    'fig-alt="a"}\n\nThe wrapping paragraph runs on at length.\n'
)


@_needs_pandoc
@pytest.mark.layer("integration")
def test_wrap_fuses_to_the_following_paragraph_in_latex():
    out = _render(_WRAP)
    assert "\\begin{wrapfigure}{i}" in out
    # the wrapfigure ends immediately before the wrapping text -- no \par -- so
    # wrapfig runs the paragraph around it
    assert "\\end{wrapfigure}%\nThe wrapping paragraph" in out
    # the caption is a \caption* (the caption package makes it clean under float)
    assert "\\caption*" in out


@_needs_pandoc
@pytest.mark.layer("integration")
def test_full_page_placements_take_their_own_leaf():
    # A full page is a deterministic cleared leaf, NOT a floating figure[p] (a
    # float defers and lands a page late, leaving a blank); the caption sits on
    # the same leaf via \captionof, not a float-only \caption.
    bleed = _render('# C\n\n![Cap.](x.png){.figure place=full-bleed fig-alt="a"}\n')
    assert "\\clearpage" in bleed
    assert "\\begin{figure}[p]" not in bleed
    assert "\\captionof{figure}" in bleed
    # a frontispiece clears to the verso, facing the next chapter's recto
    front = _render('# C\n\n![Cap.](x.png){.figure place=frontispiece fig-alt="a"}\n')
    assert "\\cleardoubleevenpage" in front


@_needs_pandoc
@pytest.mark.layer("integration")
def test_web_keeps_a_clean_in_flow_figure():
    # Placement is a print concern; on the reflowable web a placed figure is a
    # clean in-flow <figure> -- no wrapfigure/float machinery, and no house-only
    # place=/outset attributes leaking onto the <img> as data-* junk.
    html = _render(_WRAP, to="html")
    assert "<figure" in html and "<img" in html
    assert "wrapfigure" not in html
    assert "wrap-inner" not in html and "data-place" not in html and "outset" not in html


@_needs_pandoc
@pytest.mark.layer("integration")
def test_wrap_outer_and_margin_take_the_outer_side():
    # wrap-outer and margin both wrap on the OUTER edge (the {o} anchor); only
    # wrap-inner takes the inner {i} edge. half-measure is a 0.5\linewidth column.
    outer = _render(_WRAP.replace("place=wrap-inner", "place=wrap-outer"))
    assert "\\begin{wrapfigure}{o}{0.5\\linewidth}" in outer
    margin = _render(_WRAP.replace("place=wrap-inner", "place=margin"))
    assert "\\begin{wrapfigure}{o}" in margin


@_needs_pandoc
@pytest.mark.layer("integration")
def test_wrap_column_and_needspace_guard_scale_with_the_measure():
    # Each measure fixes the wrap column AND the \Needspace guard (how many lines
    # must remain, else the wrap moves to the next page): half -> 0.5\linewidth /
    # 13, third -> 0.3333 / 9. A width outside the vocabulary falls back to
    # 0.4\linewidth and an 11-line guard.
    third = _render(_WRAP.replace("width=half-measure", "width=third-measure"))
    assert "\\begin{wrapfigure}{i}{0.3333\\linewidth}" in third
    assert "\\Needspace*{9\\baselineskip}" in third
    assert "\\Needspace*{13\\baselineskip}" in _render(_WRAP)
    raw = _render(_WRAP.replace("width=half-measure", "width=3in"))
    assert "\\begin{wrapfigure}{i}{0.4\\linewidth}" in raw
    assert "\\Needspace*{11\\baselineskip}" in raw


@_needs_pandoc
@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_bare_plate_is_untouched():
    # No kind, no place, no width, no alt: the byte-identity guarantee.
    out = _render("# C\n\n![A plate.](x.png)\n")
    assert "wrapfigure" not in out and "figwrap" not in out and "figure[p]" not in out


@_needs_pandoc
@pytest.mark.layer("integration")
@pytest.mark.parametrize(
    ("place", "container", "caption"),
    [
        # A plate (no declared kind) honours a runaround like a numbered
        # figure, its own caption as the \caption*, no List-of-Figures line.
        ("wrap-inner", "\\begin{wrapfigure}{i}{0.4\\linewidth}", "\\caption*{A plate.}"),
        ("wrap-outer", "\\begin{wrapfigure}{o}{0.4\\linewidth}", "\\caption*{A plate.}"),
        # A full-page plate takes its cleared leaf, the caption on that leaf.
        ("full-bleed", "\\clearpage\n\\thispagestyle{empty}", "\\captionof{figure}{A plate.}"),
        (
            "frontispiece",
            "\\cleardoubleevenpage\n\\thispagestyle{empty}",
            "\\captionof{figure}{A plate.}",
        ),
        # A placement outside the print vocabulary stays the ordinary in-flow
        # figure, its caption the List-of-Plates \caption.
        ("inline", "\\begin{figure}\n\\centering", "\\caption{A plate.}"),
    ],
)
def test_a_placed_plate_takes_the_house_container(place, container, caption):
    out = _render(f"# C\n\n![A plate.](x.png){{place={place}}}\n\nText after.\n")
    assert container in out
    assert caption in out
    assert "lof2" not in out and "Figure~" not in out


@_needs_pandoc
@pytest.mark.layer("integration")
def test_a_numbered_full_page_figure_carries_its_cross_reference_label():
    # The label rides inside the centred leaf, before the graphic, so a
    # \hyperref to the figure lands on the plate's own page.
    out = _render("# C\n\n![Cap.](x.png){#fig:big .figure place=full-bleed}\n")
    assert "\\begin{center}\n\\phantomsection\\label{fig:big}\n\\pandocbounded" in out


@_needs_pandoc
@pytest.mark.layer("integration")
def test_a_wrap_with_no_following_paragraph_is_flushed_standalone():
    # A heading next means there is no paragraph to fuse to: the wrapfigure is
    # emitted on its own rather than dropped, and the heading follows intact.
    out = _render("# C\n\n![Cap.](x.png){.figure place=wrap-inner}\n\n# D\n\nText.\n")
    # pandoc 3.1 wraps a heading in \hypertarget{d}{%...}; newer pandoc does
    # not. Either way nothing may sit between the wrap and the heading.
    assert re.search(r"\\end\{wrapfigure\}\n\n(?:\\hypertarget\{d\}\{%\n)?\\section\{D\}", out)
    assert "\\end{wrapfigure}%" not in out
