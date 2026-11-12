"""Figures the author declares in the manuscript, with their kind and their
art-direction description -- the raw material of a good image-model prompt, so
the caption's own words never leak into the picture (#225)."""

from __future__ import annotations

import json

import pytest

from tests import factories
from press import booklib, figures


@pytest.mark.layer("unit")
def test_a_plate_carries_kind_style_and_art_description():
    md = (
        "Some prose.\n\n"
        "![A compositor at the case](assets/fig/compositor.jpg)"
        "{.plate style=wood-engraving}\n\n"
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
    assert fig.directive_form == figures.DIRECTIVE_BLANK_LINE


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
        "![Yields by season](assets/fig/yields.svg){.chart}\n\n"
        "<!-- data: bar chart from tables/yields.csv -->\n\n"
        "![The press](assets/fig/press.svg){.diagram}\n\n"
        "<!-- source: drawings/press.svg -->\n"
    )
    chart, diagram = figures.parse(md)
    assert chart.kind == "chart" and chart.directive == "data"
    assert diagram.kind == "diagram" and diagram.directive == "source"
    assert chart.generatable is False and diagram.generatable is False


@pytest.mark.layer("unit")
def test_figures_are_returned_in_source_order():
    md = "![One](a.jpg)\n\ntext\n\n![Two](b.jpg){.plate}\n\n<!-- art: a scene -->\n"
    one, two = figures.parse(md)
    assert (one.src, one.kind) == ("a.jpg", "figure")
    assert (two.src, two.kind, two.generatable) == ("b.jpg", "plate", True)


@pytest.mark.layer("unit")
def test_as_dict_carries_the_art_direction_for_a_workflow():
    (fig,) = figures.parse(
        "![A label](assets/fig/x.jpg){.plate style=wood-engraving}\n\n"
        "<!-- art: the described scene -->\n"
    )
    d = figures.as_dict(fig)
    assert d == {
        "src": "assets/fig/x.jpg",
        "caption": "A label",
        "kind": "plate",
        "style": "wood-engraving",
        "directive": "art",
        "directive_form": "blank-line",
        "description": "the described scene",
        "generatable": True,
        "identifier": None,
        "width": None,
        "place": None,
        "outset": None,
        "alt": None,
        "decorative": False,
        "numbered": False,
    }


@pytest.mark.layer("unit")
def test_placement_vocabulary_rides_on_the_image_attributes():
    (fig,) = figures.parse(
        "![The press at work](assets/fig/press.jpg){#fig:press .figure "
        "width=half-measure place=wrap-outer outset=1em "
        'fig-alt="A hand press, the platen raised"}\n'
    )
    assert fig.identifier == "fig:press"
    assert fig.kind == "figure" and fig.kind_declared is True
    assert fig.width == "half-measure"
    assert fig.place == "wrap-outer"
    assert fig.outset == "1em"
    assert fig.alt == "A hand press, the platen raised"
    assert fig.decorative is False
    assert fig.numbered is True  # an explicit informative kind is numbered


@pytest.mark.layer("unit")
def test_a_bare_image_and_a_plate_are_never_numbered():
    # Byte-identity's guarantee: a book that declares no numbered figure gets
    # none. A bare image defaults to kind "figure" but is not DECLARED, and a
    # plate is the unnumbered woodcut idiom.
    bare, plate = figures.parse("![One](a.png)\n\n![Two](b.png){.plate}\n")
    assert bare.kind == "figure" and bare.kind_declared is False
    assert bare.numbered is False
    assert plate.kind == "plate" and plate.numbered is False


@pytest.mark.layer("unit")
def test_a_decorative_image_is_not_numbered():
    (fig,) = figures.parse("![orn](o.png){.figure decorative=true}\n")
    assert fig.decorative is True
    assert fig.numbered is False


@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_a_house_placement_vocabulary_validates_clean():
    figs = figures.parse(
        "![A](a.png){.figure width=full-measure place=inline}\n\n"
        "![B](b.png){.map place=wrap-inner outset=1.5em}\n\n"
        "![C](c.png){.plate place=frontispiece}\n"
    )
    assert figures.validate(figs) == []


@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_validate_refuses_left_right_absolute_and_bad_outset():
    # Every clause of the relative, parity-aware law has a refusal.
    left = figures.validate(figures.parse("![A](a.png){.figure place=left}\n"))
    assert left and "parity-aware" in left[0]

    unknown = figures.validate(figures.parse("![A](a.png){.figure place=floating}\n"))
    assert unknown and "unknown place" in unknown[0]

    absolute = figures.validate(figures.parse("![A](a.png){.figure place=inline width=2.4in}\n"))
    assert absolute and "absolute" in absolute[0]

    measure_on_plate = figures.validate(
        figures.parse("![A](a.png){.plate place=plate width=half-measure}\n")
    )
    assert measure_on_plate and "in-flow" in measure_on_plate[0]

    bad_outset = figures.validate(
        figures.parse("![A](a.png){.figure place=wrap-outer outset=12pt}\n")
    )
    assert bad_outset and "runaround gap" in bad_outset[0]

    contradiction = figures.validate(
        figures.parse('![A](a.png){.plate decorative=true fig-alt="x"}\n')
    )
    assert contradiction and "empty alt" in contradiction[0]


@pytest.mark.layer("unit")
def test_figure_is_a_frozen_value_object_with_off_by_default_flags():
    # A parsed figure is immutable, and its two boolean flags default to off:
    # a bare image is not decorative and not kind-declared until the manuscript
    # says so. These pin the dataclass defaults the parser leans on.
    fig = figures.Figure(
        src="a.png",
        caption="A",
        kind="figure",
        style=None,
        directive="",
        description=None,
    )
    assert fig.decorative is False
    assert fig.kind_declared is False
    assert fig.directive_form == ""
    with pytest.raises(Exception):
        fig.decorative = True  # type: ignore[misc]


@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_a_directive_after_one_blank_line_is_the_lawful_form():
    # The form pandoc keeps as a Figure: image, one blank line, the comment.
    # Trailing spaces on the image line and Windows line ends do not change it.
    for gap in ("\n\n", "  \n\n", "\r\n\r\n"):
        (fig,) = figures.parse(f"![C](a.png){{.plate}}{gap}<!-- art: a scene -->\n")
        assert fig.directive == "art" and fig.description == "a scene"
        assert fig.directive_form == figures.DIRECTIVE_BLANK_LINE
        assert figures.validate([fig]) == []


@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_directive_on_the_next_line_is_refused_with_the_fix_named():
    # pandoc folds a comment on the very next line into the image's paragraph
    # and sets the image as inline text (#280). The parser still attaches the
    # directive -- nothing is silently dropped -- but records the form, and
    # validation refuses it naming the one-line fix. Every directive key is
    # covered, not only art:.
    for key in ("art", "data", "source"):
        (fig,) = figures.parse(f"![C](a.png){{.figure}}\n<!-- {key}: a thing -->\n")
        assert fig.directive == key and fig.description == "a thing"
        assert fig.directive_form == figures.DIRECTIVE_NEXT_LINE
        (problem,) = figures.validate([fig])
        assert problem.startswith("a.png: ")
        assert f"<!-- {key}:" in problem
        assert "inline text" in problem
        assert "insert one blank line" in problem
    # The dict hand-off carries the form, so a workflow sees it too.
    (fig,) = figures.parse("![C](a.png){.plate}\n<!-- art: a scene -->\n")
    assert figures.as_dict(fig)["directive_form"] == "next-line"


@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_the_packaged_next_line_fixture_is_rejected_by_the_figures_checker():
    # The known-bad fixture the celebrimbor gate and press's fixture auditor
    # both run: it must draw exactly the diagnostic it declares, from this
    # checker, naming the fixture file.
    fixture = booklib.DATA / "known-bad" / "figure-comment-next-line.md"
    found = figures.diagnostics_for(fixture)
    assert found and all(line.startswith("figure-comment-next-line.md: ") for line in found)
    assert any("insert one blank line" in line for line in found)
    # and the known-good fixture draws nothing from it
    assert figures.diagnostics_for(booklib.DATA / "known-good" / "clean.md") == []


@pytest.mark.layer("unit")
def test_a_decorative_image_without_alt_validates_clean():
    # The contradiction check fires only when a decorative image ALSO carries
    # fig-alt; a decorative image with no alt (the correct spelling) is clean,
    # and a captioned image with alt and no decorative flag is clean too. This
    # pins the `decorative and alt` conjunction: neither half alone is a fault.
    decorative_only = figures.validate(figures.parse("![orn](o.png){.figure decorative=true}\n"))
    assert decorative_only == []
    alt_only = figures.validate(figures.parse('![A](a.png){.figure fig-alt="a hand on a stick"}\n'))
    assert alt_only == []


@pytest.mark.layer("integration")
def test_press_figures_prints_declared_figures_as_json(tmp_path, capsys):
    handle = (
        factories.minimal()
        .with_chapter(
            "01-fig.md",
            "# Fig\n\n![A compositor](assets/fig/compositor.jpg){.plate}\n\n"
            "<!-- art: a compositor's hand on a composing stick -->\n\n"
            "![Yields](assets/fig/yields.svg){.chart}\n\n<!-- data: from t.csv -->\n",
        )
        .build(tmp_path)
    )
    with handle.use():
        assert figures.main([]) == 0
    raw = capsys.readouterr().out
    # The record dump is pretty-printed at two-space indent (list items open
    # with exactly two leading spaces), not a single dense line.
    assert "\n  {" in raw
    records = json.loads(raw)
    plate = next(r for r in records if r["src"] == "assets/fig/compositor.jpg")
    assert plate["file"] == "book/chapters/01-fig.md"
    assert plate["description"] == "a compositor's hand on a composing stick"
    assert plate["generatable"] is True
    assert plate["directive_form"] == "blank-line"
    chart = next(r for r in records if r["kind"] == "chart")
    assert chart["directive"] == "data" and chart["generatable"] is False
