"""The encoded vendor specs must match the researched, sourced numbers. These
tests are the auditable check on docs/PRINT-PROFILES-PLAN.md and the inline
[SOURCE] citations: if a spec drifts from its cited source, a test turns red.
Every asserted number traces to a source code in the spec's `sources` ledger.
"""

from __future__ import annotations

import pytest

from press import provider_specs


@pytest.mark.layer("unit")
def test_all_vendor_specs_load_with_a_sources_ledger():
    for vendor in ("house", "lulu", "kdp", "ingramspark"):
        spec = provider_specs.load(vendor)
        assert spec.id == vendor
        if vendor != "house":
            # A real spec is auditable: it carries a sources ledger.
            assert spec.data.get("sources"), f"{vendor} has no sources ledger"


@pytest.mark.layer("unit")
def test_lulu_paperback_spine_is_pages_over_444_plus_006():
    lulu = provider_specs.load("lulu")
    # [SPINE][GUIDE] pages/444 + 0.06
    assert lulu.spine(444, binding="perfect-bound") == pytest.approx(1.0 + 0.06)
    assert lulu.spine(46, binding="perfect-bound") == pytest.approx(46 / 444 + 0.06)


@pytest.mark.layer("unit")
def test_lulu_hardcover_spine_reads_the_lookup_table():
    lulu = provider_specs.load("lulu")
    # [SPINE] 46 pages -> the 24-84 band -> 0.25in; 200 -> 195-222 band -> 0.75in.
    assert lulu.spine(46, binding="casewrap") == 0.25
    assert lulu.spine(200, binding="dust-jacket") == 0.75


@pytest.mark.layer("unit")
def test_kdp_calipers_match_the_official_page():
    kdp = provider_specs.load("kdp")
    # [PBCOVER] standard color 0.002252, premium color 0.002347, +0.06.
    assert kdp.spine(100, "standard-color", "perfect-bound") == pytest.approx(100 * 0.002252 + 0.06)
    assert kdp.spine(100, "premium-color", "perfect-bound") == pytest.approx(100 * 0.002347 + 0.06)


@pytest.mark.layer("unit")
def test_ingram_white_50_is_thinner_than_everyone_else():
    ingram = provider_specs.load("ingramspark")
    # [PAPER] white 50# = 512 PPI (0.001953/pg), thinner than crème 444.
    assert ingram.spine(512, "white", "perfect-bound") == pytest.approx(1.0)
    assert ingram.spine(444, "cream", "perfect-bound") == pytest.approx(1.0)
    # No +0.06 allowance for Ingram.
    assert ingram.spine(100, "white", "perfect-bound") == pytest.approx(100 / 512)


@pytest.mark.layer("unit")
def test_kdp_has_no_dust_jacket_but_lulu_does():
    # [HCCOVER] KDP offers no dust jacket at 6x9; [SPEC] Lulu does.
    assert any("dust-jacket" in p or "does not offer" in p
               for p in provider_specs.load("kdp").check_selection(6, 9, "dust-jacket", 100))
    assert provider_specs.load("lulu").check_selection(6, 9, "dust-jacket", 100) == []


@pytest.mark.layer("unit")
def test_ingram_casewrap_geometry_matches_the_published_formula():
    from press import gen_coverwrap as cw

    ingram = provider_specs.load("ingramspark")
    spine = ingram.spine(200, "white", "casewrap")  # pages/PPI, no lookup
    has_spine, margin, inner, wd, hd = cw._binding_geometry(ingram, "casewrap")
    lay = cw.wrap_geometry(6.0, 9.0, spine, has_spine, margin, inner, wd, hd, "casewrap")
    board_w = 6.0 - 0.185
    assert lay.wrap_w == pytest.approx(0.625 + board_w + 0.5 + spine + 0.5 + board_w + 0.625)
    assert lay.wrap_h == pytest.approx(0.625 + (9.0 + 0.25) + 0.625)
