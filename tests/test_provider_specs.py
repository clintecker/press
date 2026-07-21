"""Provider specs turn a page count and paper into a spine width. These tests
pin the four spine shapes, the per-book override, and -- the compatibility
gate -- that the house spec reproduces the v1 caliper math exactly.
"""

from __future__ import annotations

import pytest

from press import provider_specs


def _spec(spine: dict, bleed: float = 0.125) -> provider_specs.ProviderSpec:
    return provider_specs.ProviderSpec("test", {"spine": spine, "cover": {"bleed": bleed}})


@pytest.mark.layer("unit")
def test_house_spec_reproduces_v1_caliper_math():
    house = provider_specs.load()
    # v1: pages x caliper, no +0.06 allowance. Cream default, white on request.
    assert house.spine(46, "cream") == pytest.approx(46 * 0.0025)
    assert house.spine(100, "white") == pytest.approx(100 * 0.002252)
    # Default paper is cream, matching the v1 default.
    assert house.spine(46) == pytest.approx(46 * 0.0025)
    assert house.bleed == 0.125


@pytest.mark.layer("unit")
def test_page_thickness_override_wins():
    house = provider_specs.load()
    assert house.spine(100, "cream", override=0.003) == pytest.approx(0.3)


@pytest.mark.layer("unit")
def test_constant_shape_applies_the_allowance():
    spec = _spec({
        "shape": "constant", "calipers": {"white": 0.002252},
        "paperback-allowance": 0.06, "default-paper": "white",
    })
    assert spec.spine(100, "white") == pytest.approx(100 * 0.002252 + 0.06)


@pytest.mark.layer("unit")
def test_divisor_shape_is_stock_independent():
    # Lulu's paperback shape: pages / 444 + 0.06, regardless of paper.
    spec = _spec({"shape": "divisor", "divisor": 444, "paperback-allowance": 0.06})
    assert spec.spine(444, "anything") == pytest.approx(1.0 + 0.06)


@pytest.mark.layer("unit")
def test_ppi_table_shape_reads_pages_per_inch():
    # IngramSpark's shape: pages / ppi[stock]; white 50# is thinner (512 PPI).
    spec = _spec({"shape": "ppi-table", "ppi": {"white": 512, "cream": 444}})
    assert spec.spine(512, "white") == pytest.approx(1.0)
    assert spec.spine(444, "cream") == pytest.approx(1.0)


@pytest.mark.layer("unit")
def test_lookup_shape_reads_the_page_band():
    # Lulu hardcover: a stepped table keyed by page-count band.
    spec = _spec({"shape": "lookup", "table": [[24, 84, 0.25], [85, 140, 0.5]]})
    assert spec.spine(46, "cream") == 0.25
    assert spec.spine(140, "cream") == 0.5
    with pytest.raises(SystemExit, match="no spine band"):
        spec.spine(1000, "cream")


@pytest.mark.layer("unit")
def test_unknown_paper_is_refused():
    spec = _spec({"shape": "constant", "calipers": {"white": 0.002252}})
    with pytest.raises(SystemExit, match="unknown paper stock"):
        spec.spine(100, "groundwood")


@pytest.mark.layer("unit")
def test_unknown_provider_is_refused_and_names_available():
    with pytest.raises(SystemExit) as exc:
        provider_specs.load("no-such-provider")
    assert "unknown provider spec" in str(exc.value)
    assert provider_specs.HOUSE in str(exc.value)


def _catalog() -> provider_specs.ProviderSpec:
    return provider_specs.ProviderSpec("vendor", {
        "spine": {"shape": "constant", "calipers": {"white": 0.002252}},
        "cover": {"bleed": 0.125},
        "trims": [
            {"width": 6, "height": 9, "bindings": ["perfect-bound", "casewrap"]},
            {"width": 5.5, "height": 8.5, "bindings": ["perfect-bound"]},
        ],
        "pages": {
            "perfect-bound": {"min": 32, "max": 828},
            "casewrap": {"min": 24, "max": 550},
        },
    })


@pytest.mark.layer("unit")
def test_legality_accepts_an_offered_combination():
    assert _catalog().check_selection(6, 9, "perfect-bound", 200) == []


@pytest.mark.layer("unit")
def test_legality_refuses_an_uncut_trim():
    problems = _catalog().check_selection(7, 10, "perfect-bound", 200)
    assert any("does not offer a 7 x 10 trim" in p for p in problems)


@pytest.mark.layer("unit")
def test_legality_refuses_a_binding_not_offered_for_that_trim():
    problems = _catalog().check_selection(5.5, 8.5, "casewrap", 200)
    assert any("does not offer 5.5 x 8.5 in 'casewrap'" in p for p in problems)


@pytest.mark.layer("unit")
def test_legality_refuses_page_counts_out_of_range():
    assert any("at least 32" in p for p in _catalog().check_selection(6, 9, "perfect-bound", 20))
    assert any("at most 550" in p for p in _catalog().check_selection(6, 9, "casewrap", 600))


@pytest.mark.layer("unit")
def test_house_spec_imposes_no_limits():
    # No trims/pages tables -> the house spec never refuses (v1 compatibility).
    assert provider_specs.load().check_selection(6, 9, "perfect-bound", 46) == []
    assert provider_specs.load().check_selection(11, 17, "coil", 5000) == []
