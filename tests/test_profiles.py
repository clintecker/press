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


@pytest.mark.layer("unit")
def test_geometry_projection_generalizes_to_another_trim():
    # A synthetic profile proves the projection is data-driven: a different
    # trim and cap produce a different page, with no code path special-cased
    # to 6x9.
    digest = profiles.Profile(
        "digest-5x8",
        {
            "trim": {"width": 5.0, "height": 8.0},
            "interior": {
                "margins": {
                    "inner": 0.7, "outer": 0.6, "top": 0.7,
                    "bottom": 0.7, "headsep": 0.2, "footskip": 0.35,
                },
                "figure-cap": 5.5,
            },
        },
    )
    tex = profiles.geometry_tex(digest)
    assert "paperwidth=5in,paperheight=8in" in tex
    assert "\\renewcommand{\\PressFigureCap}{5.5in}" in tex


@pytest.mark.layer("unit")
def test_unknown_profile_is_refused_before_rendering():
    with pytest.raises(SystemExit) as exc:
        profiles.load("no-such-profile")
    assert "unknown print profile" in str(exc.value)
    # The refusal names what is available, so a typo is diagnosable.
    assert profiles.HOUSE in str(exc.value)
