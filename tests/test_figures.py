"""Figures the author declares in the manuscript, with their kind and their
art-direction description -- the raw material of a good image-model prompt, so
the caption's own words never leak into the picture (#225)."""

from __future__ import annotations

import pytest

from press import figures


@pytest.mark.layer("unit")
def test_a_plate_carries_kind_style_and_art_description():
    md = (
        "Some prose.\n\n"
        "![A compositor at the case](assets/fig/compositor.jpg)"
        "{.plate style=wood-engraving}\n"
        "<!-- art: a compositor's left hand holding a brass composing stick;\n"
        "     type in the case behind; high contrast line, no lettering -->\n\n"
        "More prose.\n"
    )
    (fig,) = figures.parse(md)
    assert fig.src == "assets/fig/compositor.jpg"
    assert fig.caption == "A compositor at the case"
    assert fig.kind == "plate"
    assert fig.style == "wood-engraving"
    assert fig.directive == "art"
    assert "composing stick" in fig.description
    assert "\n" not in fig.description  # whitespace-normalized
    assert fig.generatable is True


@pytest.mark.layer("unit")
def test_a_bare_image_is_a_figure_with_no_directive():
    (fig,) = figures.parse("![Just a caption](img.png)\n")
    assert fig.kind == "figures".rstrip("s")  # "figure"
    assert fig.style is None
    assert fig.directive == ""
    assert fig.description is None
    assert fig.generatable is False


@pytest.mark.layer("unit")
def test_a_generatable_kind_without_art_is_not_generatable():
    # The load-bearing rule: a plate with no art: description must NOT be drawn
    # from the caption's words. It is simply not generatable until described.
    (fig,) = figures.parse("![The stick](s.jpg){.plate}\n")
    assert fig.kind == "plate"
    assert fig.directive == ""
    assert fig.generatable is False


@pytest.mark.layer("unit")
def test_charts_and_diagrams_route_away_from_the_image_model():
    md = (
        "![Yields by season](assets/fig/yields.svg){.chart}\n"
        "<!-- data: bar chart from tables/yields.csv -->\n\n"
        "![The press](assets/fig/press.svg){.diagram}\n"
        "<!-- source: drawings/press.svg -->\n"
    )
    chart, diagram = figures.parse(md)
    assert chart.kind == "chart" and chart.directive == "data"
    assert diagram.kind == "diagram" and diagram.directive == "source"
    assert chart.generatable is False and diagram.generatable is False


@pytest.mark.layer("unit")
def test_figures_are_returned_in_source_order():
    md = "![One](a.jpg)\n\ntext\n\n![Two](b.jpg){.plate}\n<!-- art: a scene -->\n"
    one, two = figures.parse(md)
    assert (one.src, one.kind) == ("a.jpg", "figure")
    assert (two.src, two.kind, two.generatable) == ("b.jpg", "plate", True)
