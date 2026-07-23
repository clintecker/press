"""The illustration engine: the media library loads, a prompt fills with the
book's ink and the wordless single-ink guardrail, style resolution defaults to
the house wood engraving and refuses an unknown id, and a book can add its own
styles. No image model is called."""

from __future__ import annotations

import pytest

from press import illustrate

AES = {"book-colors": {"ink": "#12333a"}, "web-palette": {"paper": "#eef4f2"},
       "plates": {"style": "line-diagram"}}


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
