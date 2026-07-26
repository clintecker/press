"""The drop-cap semantic split: grapheme-aware, punctuation-aware, and safe
on the awkward openings a real manuscript throws at it. These are the
renderer-independent fixtures the Lua filter's behavior mirrors.
"""

from __future__ import annotations

import unicodedata

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from press import dropcaps

_DETERMINISTIC = settings(derandomize=True, deadline=None, max_examples=400)


@pytest.mark.layer("unit")
def test_settings_default_is_off():
    s = dropcaps.settings(None, None)
    assert s.style == "none" and not s.enabled


@pytest.mark.layer("unit")
def test_settings_defaults_are_three_lines_no_depth_small_caps_on():
    # The resolved defaults when nothing is stated: three lines, no extra
    # descender depth, small-caps remainder on. These pin the exact default
    # constants the resolver and the Settings dataclass carry.
    s = dropcaps.settings(None, None)
    assert s.lines == 3
    assert s.depth == 0
    assert s.small_caps_remainder is True
    # The dataclass field defaults are used when a style is set with no counts.
    d = dropcaps.Settings(style="drop-cap")
    assert d.lines == 3 and d.depth == 0 and d.small_caps_remainder is True
    assert "lines=3,depth=0" in dropcaps.tex_setup(d)


@pytest.mark.layer("unit")
def test_settings_and_opening_are_frozen_value_objects():
    # Both are frozen dataclasses: a resolved treatment and a split opening are
    # immutable, so a caller cannot mutate one after the pipeline hands it over.
    s = dropcaps.Settings(style="drop-cap")
    with pytest.raises(Exception):
        s.lines = 5  # type: ignore[misc]
    o = dropcaps.split_initial("The shop opened at dawn.")
    with pytest.raises(Exception):
        o.initial = "X"  # type: ignore[misc]


@pytest.mark.layer("unit")
def test_book_override_wins_over_profile_default():
    s = dropcaps.settings({"style": "none"}, {"style": "drop-cap", "lines": 4})
    assert s.style == "drop-cap" and s.lines == 4 and s.enabled


@pytest.mark.layer("unit")
def test_unknown_style_is_refused():
    with pytest.raises(SystemExit):
        dropcaps.settings({"style": "flourish"}, None)


@pytest.mark.layer("unit")
def test_tex_setup_off_is_empty():
    assert dropcaps.tex_setup(dropcaps.Settings(style="none")) == ""


@pytest.mark.layer("unit")
def test_tex_setup_defines_the_macro_with_the_settings():
    tex = dropcaps.tex_setup(dropcaps.Settings(style="drop-cap", lines=3, depth=1))
    assert "\\usepackage{lettrine}" in tex
    assert "\\newcommand{\\PressDropCap}" in tex
    assert "lines=3,depth=1" in tex
    assert "\\scshape" in tex               # small-caps remainder on by default
    assert "\\Needspace*{5\\baselineskip}" in tex   # lines + depth + 1 reserved


@pytest.mark.layer("unit")
def test_tex_setup_without_small_caps():
    tex = dropcaps.tex_setup(
        dropcaps.Settings(style="drop-cap", small_caps_remainder=False))
    assert "\\scshape" not in tex


@pytest.mark.layer("unit")
def test_tex_setup_routes_the_lead_through_ante_only_when_present():
    # The macro takes the lead as its own first argument and passes it to
    # lettrine's `ante`; an empty lead takes the branch with no `ante` at all,
    # so an ordinary opener compiles to the exact lettrine call it did before.
    tex = dropcaps.tex_setup(dropcaps.Settings(style="drop-cap", lines=3))
    assert "\\newcommand{\\PressDropCap}[3]" in tex
    assert "\\ifx\\PressDropLead\\empty" in tex
    assert "ante={#1}" in tex
    # The empty-lead branch is byte-identical to the pre-fix lettrine call.
    assert ("\\lettrine[lines=3,depth=0,findent=2pt,nindent=0pt]{#2}"
            "{\\scshape #3}") in tex


@pytest.mark.layer("unit")
def test_ornate_is_accepted_and_loads_the_decorated_initial_font():
    s = dropcaps.settings({"style": "ornate"}, None)
    assert s.style == "ornate" and s.enabled
    tex = dropcaps.tex_setup(s)
    # yfonts supplies the yinit decorated capitals; the initial is set in it.
    assert "\\usepackage{yfonts}" in tex
    assert "\\usefont{U}{yinit}{m}{n}" in tex
    assert "\\PressOrnateInitial #2" in tex


@pytest.mark.layer("unit")
def test_non_ornate_styles_carry_no_decorated_font():
    for style in ("drop-cap", "raised-cap"):
        tex = dropcaps.tex_setup(dropcaps.Settings(style=style))
        assert "yfonts" not in tex and "yinit" not in tex


@pytest.mark.layer("unit")
def test_plain_opening():
    o = dropcaps.split_initial("The machinery supplies everything else.")
    assert (o.lead, o.initial, o.word_remainder) == ("", "T", "he")
    assert o.rest == " machinery supplies everything else."


@pytest.mark.layer("unit")
def test_one_word_opening():
    o = dropcaps.split_initial("No.")
    assert o.initial == "N" and o.word_remainder == "o." and o.rest == ""


@pytest.mark.layer("unit")
def test_leading_quote_is_kept_with_the_initial():
    o = dropcaps.split_initial('"The machinery supplies everything else."')
    assert o.lead == '"' and o.initial == "T" and o.word_remainder == "he"


@pytest.mark.layer("unit")
def test_leading_em_dash_is_kept():
    o = dropcaps.split_initial("—Then the machine started.")
    assert o.lead == "—" and o.initial == "T" and o.word_remainder == "hen"


@pytest.mark.layer("unit")
def test_precomposed_accented_initial_is_whole():
    o = dropcaps.split_initial("Évidence is not verification.")   # É
    assert o.initial == "É" and o.word_remainder == "vidence"


@pytest.mark.layer("unit")
def test_decomposed_accented_initial_stays_a_grapheme():
    # E + combining acute accent -> one grapheme, not split after the E.
    text = "Évidence is not verification."
    o = dropcaps.split_initial(text)
    assert o.initial == "É"
    assert unicodedata.combining(o.initial[-1])   # the accent rode along
    assert o.word_remainder == "vidence"


@pytest.mark.layer("unit")
def test_q_with_descender_word_remainder():
    o = dropcaps.split_initial("Quietly, the engine cooled.")
    assert o.initial == "Q" and o.word_remainder == "uietly,"


@pytest.mark.layer("unit")
def test_leading_whitespace_is_dropped():
    o = dropcaps.split_initial("   The machinery.")
    assert o.lead == "" and o.initial == "T" and o.word_remainder == "he"


@pytest.mark.layer("unit")
def test_punctuation_only_has_no_initial():
    o = dropcaps.split_initial('"..."')
    assert o.is_empty
    # The caller renders the original text unchanged.
    assert o.rest == '"..."'


@pytest.mark.layer("unit")
def test_single_letter_word():
    o = dropcaps.split_initial("A quiet start.")
    assert o.initial == "A" and o.word_remainder == "" and o.rest == " quiet start."


@pytest.mark.layer("unit")
def test_reassembly_is_lossless_after_the_stripped_prefix():
    # lead + initial + word_remainder + rest reconstructs the text (minus only
    # the leading whitespace the split intentionally drops).
    text = '"Quietly," she said.'
    o = dropcaps.split_initial(text)
    assert o.lead + o.initial + o.word_remainder + o.rest == text.lstrip()


@pytest.mark.invariant("INV-dropcap-opening")
@pytest.mark.layer("property")
@pytest.mark.proof("positive")
@_DETERMINISTIC
@given(text=st.text())
def test_split_initial_is_lossless_over_arbitrary_unicode(text):
    """The reassembly contract holds for every string -- arbitrary Unicode,
    combining marks, leading punctuation, whitespace, or nothing at all --
    so the drop cap never adds, drops, or reorders a character of the
    opening. The contract is exact and has two branches, which the code
    draws deliberately:

      * when there is no letter to cap, the split is a no-op that returns
        the *original* text as `rest` (leading whitespace and all), so a
        caller rendering an epigraph or an ellipsis opener changes nothing;
      * otherwise the four pieces concatenate to `text.lstrip()`, the only
        loss being the leading whitespace the split intentionally drops.

    And the initial is always one grapheme: a base character followed only
    by combining marks, never a bare code point that would strand an accent.
    """

    o = dropcaps.split_initial(text)
    if o.is_empty:
        assert o.lead == "" and o.initial == "" and o.word_remainder == ""
        assert o.rest == text
    else:
        assert o.lead + o.initial + o.word_remainder + o.rest == text.lstrip()
        assert o.initial != ""
        # Every character after the base is a combining mark: one grapheme.
        assert all(unicodedata.combining(ch) for ch in o.initial[1:])
        # Leading punctuation kept with the cap is drawn only from the
        # documented lead set, never swept-in arbitrary symbols.
        assert all(ch in dropcaps._LEAD for ch in o.lead)
        # The word remainder carries no whitespace: it is the rest of the
        # first word, and the flow of the paragraph lives in `rest`.
        assert not any(ch.isspace() for ch in o.word_remainder)
