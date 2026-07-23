"""The cover engine: the style library loads, a prompt fills from a book's
context with the exact-text guardrail on baked styles, and style resolution
falls back to the house default and refuses an unknown id. No image model is
called -- these prove the deterministic half."""

from __future__ import annotations

import pytest

from press import cover

META = {"title": "Between the Tides", "author": ["Marisol Vance"],
        "publisher": "Saltmeadow Press"}
AES = {"web-palette": {"accent": "#2f8f7f", "paper": "#eef4f2"},
       "cover": {"style": "swiss-international", "subject": "a rocky shore"}}


@pytest.mark.layer("unit")
def test_house_style_library_loads():
    styles = cover.load_styles()
    assert "penguin-tri-band" in styles
    assert len(styles) >= 10
    assert all("prompt" in s for s in styles.values())


@pytest.mark.layer("unit")
def test_context_reads_title_author_and_palette():
    ctx = cover.context(META, AES)
    assert ctx["title"] == "Between the Tides"
    assert ctx["author"] == "Marisol Vance"
    assert ctx["imprint"] == "Saltmeadow Press"
    assert ctx["initials"] == "SP"          # skips nothing here; two words
    assert ctx["accent"] == "#2f8f7f"
    assert ctx["subject"] == "a rocky shore"


@pytest.mark.layer("unit")
def test_build_prompt_fills_and_guards_baked_style():
    styles = cover.load_styles()
    ctx = cover.context(META, AES)
    prompt = cover.build_prompt(styles["penguin-tri-band"], ctx)
    assert "Between the Tides" in prompt and "#2f8f7f" in prompt
    assert "{" not in prompt                # every placeholder was filled
    assert "EXACT TEXT" in prompt           # baked styles carry the guardrail


@pytest.mark.layer("unit")
def test_style_resolution_defaults_and_refuses_unknown():
    styles = cover.load_styles()
    assert cover._resolve_style(styles, None, {}) == "penguin-tri-band"
    assert cover._resolve_style(styles, None, AES) == "swiss-international"
    with pytest.raises(SystemExit):
        cover._resolve_style(styles, "no-such-style", {})


@pytest.mark.layer("unit")
def test_a_book_can_define_and_use_its_own_style(tmp_path):
    # A book's config/cover-styles.yaml merges over the house set, so an author
    # writes their own art direction and selects it like any built-in.
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "cover-styles.yaml").write_text(
        'styles:\n'
        '  my-house:\n'
        '    name: "My house"\n'
        '    note: "mine"\n'
        '    prompt: |\n'
        '      A cover for "{title}" by {author} in {accent} on {paper}.\n',
        encoding="utf-8")
    styles = cover.load_styles(tmp_path)
    assert "my-house" in styles          # the custom style is available
    assert "penguin-tri-band" in styles  # alongside the house set
    prompt = cover.build_prompt(styles["my-house"], cover.context(META, AES))
    assert 'Between the Tides' in prompt and "#2f8f7f" in prompt
    assert "EXACT TEXT" in prompt         # baked by default, so text is guarded
