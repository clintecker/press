"""The cover-wrap layout engine composes a wrap from trim, spine, margin,
inner offset, and board/jacket deltas per binding. These tests pin the
topologies: perfect-bound reproduces the v1 geometry exactly, a no-spine
binding drops the spine, and casewrap and dust jacket match IngramSpark's
published total-size formulas. The binding-resolution logic is pinned too.
"""

from __future__ import annotations

import pytest

from press import gen_coverwrap as cw
from press.provider_specs import ProviderSpec

BLEED = 0.125


@pytest.mark.layer("unit")
def test_perfect_bound_reproduces_v1_geometry():
    # trim 6x9, spine 0.115 (make-ready): the exact v1 wrap numbers.
    lay = cw.wrap_geometry(6.0, 9.0, 0.115, True, BLEED, 0.0, 0.0, 0.0, "paperback")
    assert lay.wrap_w == pytest.approx(2 * BLEED + 2 * 6.0 + 0.115)   # 12.365
    assert lay.wrap_h == pytest.approx(2 * BLEED + 9.0)               # 9.250
    assert lay.back_x == pytest.approx(BLEED)
    assert lay.front_x == pytest.approx(BLEED + 6.0 + 0.115)
    assert lay.front_art_w == pytest.approx(6.0 + BLEED)
    assert lay.cloth_field is True


@pytest.mark.layer("unit")
def test_no_spine_binding_drops_the_spine():
    lay = cw.wrap_geometry(6.0, 9.0, 0.0, False, BLEED, 0.0, 0.0, 0.0, "paperback")
    assert lay.wrap_w == pytest.approx(2 * BLEED + 2 * 6.0)   # no spine
    assert lay.front_x == pytest.approx(BLEED + 6.0)          # front butts back
    assert lay.has_spine is False


@pytest.mark.layer("unit")
def test_casewrap_matches_ingram_formula():
    # IngramSpark casewrap: wrap 0.625, hinge 0.5, board = trim-0.185 x trim+0.25.
    # BleedW = 0.625 + board + 0.5 + spine + 0.5 + board + 0.625.
    lay = cw.wrap_geometry(6.0, 9.0, 0.25, True, 0.625, 0.5, -0.185, 0.25, "casewrap")
    board_w = 6.0 - 0.185
    assert lay.wrap_w == pytest.approx(0.625 + board_w + 0.5 + 0.25 + 0.5 + board_w + 0.625)
    assert lay.wrap_h == pytest.approx(0.625 + (9.0 + 0.25) + 0.625)


@pytest.mark.layer("unit")
def test_jacket_matches_ingram_formula():
    # IngramSpark jacket: bleed 0.125, flap 3.25 + strip 0.25 (inner), cover = trim+0.4375.
    lay = cw.wrap_geometry(6.0, 9.0, 0.25, True, BLEED, 3.5, 0.4375, 0.25, "linen")
    cover_w = 6.0 + 0.4375
    assert lay.wrap_w == pytest.approx(
        0.125 + 3.25 + 0.25 + cover_w + 0.25 + cover_w + 0.25 + 3.25 + 0.125
    )
    assert lay.back_x == pytest.approx(BLEED + 3.5)          # bleed + flap + strip
    assert lay.front_art_w == pytest.approx(cover_w)         # art stays on panel
    assert lay.cloth_field is False                          # linen: no field


def _spec(bindings: dict) -> ProviderSpec:
    return ProviderSpec("v", {"spine": {"shape": "constant", "calipers": {}},
                              "cover": {"bleed": BLEED, "bindings": bindings}})


@pytest.mark.layer("unit")
def test_soft_binding_defaults_need_no_spec():
    spec = _spec({})
    assert cw._binding_geometry(spec, "perfect-bound") == (True, BLEED, 0.0, 0.0, 0.0)
    assert cw._binding_geometry(spec, "saddle-stitch") == (False, BLEED, 0.0, 0.0, 0.0)


@pytest.mark.layer("unit")
def test_hardcover_bindings_read_the_spec():
    spec = _spec({
        "casewrap": {"spine": True, "margin": 0.625, "hinge": 0.5,
                     "panel-width-delta": -0.185, "panel-height-delta": 0.25},
        "dust-jacket": {"spine": True, "margin": 0.125, "flap": 3.25, "strip": 0.25,
                        "panel-width-delta": 0.4375, "panel-height-delta": 0.25},
    })
    assert cw._binding_geometry(spec, "casewrap") == (True, 0.625, 0.5, -0.185, 0.25)
    # inner = flap + strip = 3.5
    assert cw._binding_geometry(spec, "dust-jacket") == (True, 0.125, 3.5, 0.4375, 0.25)


@pytest.mark.layer("unit")
def test_unsupported_binding_is_refused():
    # KDP has no dust jacket: a spec that does not define it must refuse.
    with pytest.raises(SystemExit, match="does not define the 'dust-jacket'"):
        cw._binding_geometry(_spec({}), "dust-jacket")
