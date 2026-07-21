"""Print profiles model a book's physical form as versioned data. These
tests pin the house profile (the v1 baseline) and prove the geometry
projection generalizes to another trim -- the byte-identical reproduction of
v1 itself is proven by the build backtest, not here.
"""

from __future__ import annotations

import pytest

from press import profiles


@pytest.mark.layer("unit")
def test_house_profile_loads_with_v1_geometry():
    house = profiles.load()
    assert house.id == profiles.HOUSE
    assert house.trim == (6.0, 9.0)
    assert house.figure_cap == 6.3


@pytest.mark.layer("unit")
def test_house_geometry_tex_carries_the_v1_numbers():
    tex = profiles.geometry_tex(profiles.load())
    # %g formatting: an integer trim is "6in", never "6.0in" -- byte-for-byte
    # what the v1 header carried.
    assert "paperwidth=6in,paperheight=9in" in tex
    assert "inner=0.78in,outer=0.68in" in tex
    assert "headsep=0.2in" in tex
    assert "\\renewcommand{\\PressFigureCap}{6.3in}" in tex


def _synthetic() -> profiles.Profile:
    return profiles.Profile(
        "synthetic-5x8",
        {
            "design-major": 1,
            "trim": {"width": 5.0, "height": 8.0},
            "interior": {
                "margins": {
                    "inner": 0.7, "outer": 0.6, "top": 0.7,
                    "bottom": 0.7, "headsep": 0.2, "footskip": 0.35,
                },
                "figure-cap": 5.5,
                "typography": {"indent": "1.0em", "leading": 1.1},
            },
            "web": {"measure": "42rem", "base-size": "1.2rem", "line-height": 1.6},
        },
    )


@pytest.mark.layer("unit")
def test_geometry_projection_generalizes_to_another_trim():
    # A synthetic profile proves the projection is data-driven: a different
    # trim, cap, and type treatment produce a different page, with no code
    # path special-cased to 6x9.
    tex = profiles.geometry_tex(_synthetic())
    assert "paperwidth=5in,paperheight=8in" in tex
    assert "\\renewcommand{\\PressFigureCap}{5.5in}" in tex
    assert "\\setlength{\\parindent}{1.0em}" in tex
    assert "\\linespread{1.1}" in tex


@pytest.mark.layer("unit")
def test_house_typography_matches_the_v1_header():
    # The house profile projects exactly the v1 header's parindent and
    # linespread, so a house book renders byte-for-byte unchanged.
    tex = profiles.geometry_tex(profiles.load())
    assert "\\setlength{\\parindent}{1.1em}" in tex
    assert "\\linespread{1.045}" in tex


@pytest.mark.layer("unit")
def test_house_web_css_is_a_no_op():
    # The house web measure matches the reader stylesheet, so it appends
    # nothing and the CSS is byte-for-byte what it was before profiles.
    assert profiles.web_css(profiles.load()) == ""


@pytest.mark.layer("unit")
def test_non_house_web_css_overrides_only_the_measure():
    css = profiles.web_css(profiles.load("novella-5x8"))
    assert "max-width: 40rem" in css
    assert "font-size: 1.2rem" in css and "line-height: 1.66" in css
    # It touches the measure only -- never the palette or font the aesthetic
    # controls.
    assert "color" not in css and "font-family" not in css


@pytest.mark.layer("unit")
def test_novella_is_a_meaningfully_different_design():
    house, novella = profiles.load("house-6x9"), profiles.load("novella-5x8")
    assert house.trim != novella.trim
    assert house.typography != novella.typography
    assert house.web != novella.web
    # A different design has a different digest.
    assert profiles.digest(house) != profiles.digest(novella)


@pytest.mark.layer("unit")
def test_digest_is_stable_and_sensitive():
    # Same profile, same digest across loads (keys a visual baseline).
    assert profiles.digest(profiles.load("house-6x9")) == \
        profiles.digest(profiles.load("house-6x9"))
    # Changing any sealed value moves the digest.
    base = _synthetic()
    changed_data = {**base.data, "interior": {**base.data["interior"], "figure-cap": 5.6}}
    changed = profiles.Profile(base.id, changed_data)
    assert profiles.digest(base) != profiles.digest(changed)


@pytest.mark.layer("unit")
def test_unknown_profile_is_refused_before_rendering():
    with pytest.raises(SystemExit) as exc:
        profiles.load("no-such-profile")
    assert "unknown print profile" in str(exc.value)
    # The refusal names what is available, so a typo is diagnosable.
    assert profiles.HOUSE in str(exc.value)
