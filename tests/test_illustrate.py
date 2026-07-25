"""The illustration engine: the media library loads, a prompt fills with the
book's ink and the wordless single-ink guardrail, style resolution defaults to
the house wood engraving and refuses an unknown id, and a book can add its own
styles. No image model is called."""

from __future__ import annotations

import pytest

from tests import factories
from press import figures, illustrate

AES = {"book-colors": {"ink": "#12333a"}, "web-palette": {"paper": "#eef4f2"},
       "plates": {"style": "line-diagram"}}


def _fig(**kw):
    base = dict(src="assets/fig/x.jpg", caption="A label", kind="plate",
                style=None, directive="art", description="a described scene")
    base.update(kw)
    return figures.Figure(**base)


@pytest.mark.layer("unit")
def test_house_media_library_loads():
    styles = illustrate.load_styles()
    assert "wood-engraving" in styles and "engraved-map" in styles
    assert styles["figure-from-photo"]["source"] == "required"
    assert all("prompt" in s for s in styles.values())


@pytest.mark.layer("unit")
def test_context_reads_ink_and_paper():
    ctx = illustrate.context(AES)
    assert ctx["ink"] == "#12333a"      # the print ink, from book-colors
    assert ctx["paper"] == "#eef4f2"


@pytest.mark.layer("unit")
def test_build_prompt_fills_subject_and_guards_single_ink():
    styles = illustrate.load_styles()
    prompt = illustrate.build_prompt(styles["wood-engraving"],
                                     illustrate.context(AES), "a tide pool")
    assert "a tide pool" in prompt and "#12333a" in prompt
    assert "{" not in prompt                        # every placeholder filled
    assert "Single ink only" in prompt and "no text" in prompt.lower()


@pytest.mark.layer("unit")
def test_style_resolution_defaults_and_refuses_unknown():
    styles = illustrate.load_styles()
    assert illustrate._resolve_style(styles, None, {}) == "wood-engraving"
    assert illustrate._resolve_style(styles, None, AES) == "line-diagram"
    with pytest.raises(SystemExit):
        illustrate._resolve_style(styles, "no-such-style", {})


@pytest.mark.layer("unit")
def test_a_book_can_define_its_own_illustration_style(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "illustration-styles.yaml").write_text(
        'styles:\n'
        '  my-plate:\n'
        '    name: "My plate"\n'
        '    note: "mine"\n'
        '    prompt: |\n'
        '      A plate of {subject} in {ink} on {paper}.\n',
        encoding="utf-8")
    styles = illustrate.load_styles(tmp_path)
    assert "my-plate" in styles and "wood-engraving" in styles
    prompt = illustrate.build_prompt(styles["my-plate"], illustrate.context(AES), "a shell")
    assert "a shell" in prompt and "Single ink only" in prompt


@pytest.mark.layer("unit")
def test_arg_parsing_positional_name_and_flags():
    args = illustrate._parse(["harbour", "--style", "engraved-map", "--from", "a.jpg"])
    assert args.name == "harbour" and args.style == "engraved-map"
    assert args.source == "a.jpg" and not args.list


# ---- the manuscript's art: description is the subject, never the caption (#225) ----

@pytest.mark.layer("unit")
def test_subject_is_the_figures_art_description_not_its_caption():
    subject = illustrate.subject_from_figure(
        _fig(caption="A compositor at the case",
             description="a compositor's left hand on a brass composing stick"), "x")
    assert subject == "a compositor's left hand on a brass composing stick"
    assert "compositor at the case" not in subject  # the caption never leaks in


@pytest.mark.layer("unit")
def test_an_undeclared_figure_is_refused_never_drawn():
    with pytest.raises(SystemExit, match="no figure named 'ghost'"):
        illustrate.subject_from_figure(None, "ghost")


@pytest.mark.layer("unit")
def test_a_generatable_kind_without_art_is_refused_not_drawn_from_caption():
    # The load-bearing rule: a plate with no art: description must NOT be drawn
    # from the caption's words. The press refuses and points the author at art:.
    with pytest.raises(SystemExit, match="no <!-- art"):
        illustrate.subject_from_figure(_fig(directive="", description=None), "x")


@pytest.mark.layer("unit")
def test_an_empty_art_description_is_refused():
    with pytest.raises(SystemExit, match="no <!-- art"):
        illustrate.subject_from_figure(_fig(directive="art", description=""), "x")


@pytest.mark.layer("unit")
@pytest.mark.parametrize("kind", ["chart", "diagram"])
def test_charts_and_diagrams_are_routed_away_from_the_image_model(kind):
    with pytest.raises(SystemExit, match="renders from"):
        illustrate.subject_from_figure(
            _fig(kind=kind, directive="data", description="from t.csv"), "x")


@pytest.mark.layer("integration")
def test_illustrate_reads_the_art_description_and_the_figures_style(tmp_path, capsys):
    handle = factories.minimal().with_chapter(
        "01-fig.md",
        "# Fig\n\n"
        "![A compositor at the case](assets/fig/compositor.jpg)"
        "{.plate style=engraved-map}\n"
        "<!-- art: a compositor's hand on a brass composing stick, "
        "high contrast line, no lettering -->\n",
    ).build(tmp_path)
    with handle.use():
        assert illustrate.main(["compositor", "--print"]) == 0
    out = capsys.readouterr().out
    assert "brass composing stick" in out            # the art: description is the prompt
    assert "compositor at the case" not in out       # the caption did not leak in
    assert "illustration style: engraved-map" in out  # the figure's own style was adopted


@pytest.mark.layer("integration")
def test_illustrate_refuses_a_figure_with_no_art_description(tmp_path):
    handle = factories.minimal().with_chapter(
        "01-fig.md", "# Fig\n\n![The stick](assets/fig/stick.jpg){.plate}\n",
    ).build(tmp_path)
    with handle.use(), pytest.raises(SystemExit, match="no <!-- art"):
        illustrate.main(["stick", "--print"])


@pytest.mark.layer("integration")
def test_illustrate_still_honours_an_explicit_subject_from_the_cli(tmp_path, capsys):
    # --subject is the author's own art direction, not a caption: it bypasses the
    # manuscript entirely, and needs no declared figure.
    handle = factories.minimal().build(tmp_path)
    with handle.use():
        assert illustrate.main(["anything", "--subject", "a lighthouse", "--print"]) == 0
    assert "a lighthouse" in capsys.readouterr().out


@pytest.mark.layer("integration")
def test_find_figure_matches_on_the_image_file_stem(tmp_path):
    handle = factories.minimal().with_chapter(
        "01-fig.md",
        "# Fig\n\n![A scene](assets/fig/harbour.jpg){.plate}\n<!-- art: a harbour -->\n",
    ).build(tmp_path)
    with handle.use():
        assert illustrate.find_figure("harbour").src == "assets/fig/harbour.jpg"
        assert illustrate.find_figure("absent") is None
