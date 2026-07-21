"""The cover-wrap layout engine composes a wrap from trim, spine, margin, and
flap per binding. These tests pin the topologies: perfect-bound reproduces the
v1 geometry exactly, a no-spine binding drops the spine, a board turn-in and a
jacket flap grow the wrap, and linen suppresses the printed field. The
binding-resolution logic (which margin/flap a binding gets) is pinned too.
"""

from __future__ import annotations

import pytest

from press import gen_coverwrap as cw
from press.provider_specs import ProviderSpec

BLEED = 0.125


@pytest.mark.layer("unit")
def test_perfect_bound_reproduces_v1_geometry():
    # trim 6x9, spine 0.115 (make-ready): the exact v1 wrap numbers.
    lay = cw.wrap_geometry(6.0, 9.0, 0.115, True, BLEED, 0.0, "paperback")
    assert lay.wrap_w == pytest.approx(2 * BLEED + 2 * 6.0 + 0.115)   # 12.365
    assert lay.wrap_h == pytest.approx(2 * BLEED + 9.0)               # 9.250
    assert lay.back_x == pytest.approx(BLEED)
    assert lay.front_x == pytest.approx(BLEED + 6.0 + 0.115)
    assert lay.front_art_w == pytest.approx(6.0 + BLEED)
    assert lay.cloth_field is True


@pytest.mark.layer("unit")
def test_no_spine_binding_drops_the_spine():
    lay = cw.wrap_geometry(6.0, 9.0, 0.0, False, BLEED, 0.0, "paperback")
    assert lay.wrap_w == pytest.approx(2 * BLEED + 2 * 6.0)   # no spine
    assert lay.front_x == pytest.approx(BLEED + 6.0)          # front butts back
    assert lay.has_spine is False


@pytest.mark.layer("unit")
def test_casewrap_turn_in_grows_the_wrap():
    # A 0.75in board turn-in replaces the 0.125in bleed on every edge.
    lay = cw.wrap_geometry(6.0, 9.0, 0.25, True, 0.75, 0.0, "casewrap")
    assert lay.wrap_w == pytest.approx(2 * 0.75 + 2 * 6.0 + 0.25)
    assert lay.wrap_h == pytest.approx(2 * 0.75 + 9.0)


@pytest.mark.layer("unit")
def test_jacket_flaps_grow_the_wrap_and_keep_art_to_the_panel():
    lay = cw.wrap_geometry(6.0, 9.0, 0.25, True, BLEED, 3.25, "linen")
    assert lay.wrap_w == pytest.approx(2 * BLEED + 2 * 3.25 + 2 * 6.0 + 0.25)
    assert lay.back_x == pytest.approx(BLEED + 3.25)          # flap before back
    assert lay.front_art_w == pytest.approx(6.0)             # art stays on panel
    assert lay.cloth_field is False                          # linen: no field


def _spec(bindings: dict) -> ProviderSpec:
    return ProviderSpec("v", {"spine": {"shape": "constant", "calipers": {}},
                              "cover": {"bleed": BLEED, "bindings": bindings}})


@pytest.mark.layer("unit")
def test_soft_binding_defaults_need_no_spec():
    spec = _spec({})
    assert cw._binding_geometry(spec, "perfect-bound", "paperback") == (True, BLEED, 0.0)
    assert cw._binding_geometry(spec, "saddle-stitch", "paperback") == (False, BLEED, 0.0)


@pytest.mark.layer("unit")
def test_hardcover_bindings_read_the_spec():
    spec = _spec({
        "casewrap": {"spine": True, "turn-in": 0.75},
        "dust-jacket": {"spine": True, "flap": 3.25},
    })
    assert cw._binding_geometry(spec, "casewrap", "casewrap") == (True, 0.75, 0.0)
    assert cw._binding_geometry(spec, "dust-jacket", "linen") == (True, BLEED, 3.25)


@pytest.mark.layer("unit")
def test_unsupported_binding_is_refused():
    # KDP has no dust jacket: a spec that does not define it must refuse.
    with pytest.raises(SystemExit, match="does not define the 'dust-jacket'"):
        cw._binding_geometry(_spec({}), "dust-jacket", "linen")
