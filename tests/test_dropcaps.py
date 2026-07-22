"""The drop-cap semantic split: grapheme-aware, punctuation-aware, and safe
on the awkward openings a real manuscript throws at it. These are the
renderer-independent fixtures the Lua filter's behavior mirrors.
"""

from __future__ import annotations

import unicodedata

import pytest

from press import dropcaps


@pytest.mark.layer("unit")
def test_settings_default_is_off():
    s = dropcaps.settings(None, None)
    assert s.style == "none" and not s.enabled


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
