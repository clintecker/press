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
def test_profile_ink_defaults_to_single_and_stays_byte_identical():
    # A profile that does not declare ink is single-ink, and declaring it
    # single explicitly changes neither the value nor the digest -- so every
    # existing book, whose profile omits ink, is unchanged and its visual
    # baseline still holds.
    house = profiles.load("house-6x9")
    assert house.ink == "single"
    explicit = profiles.Profile("house-6x9", {**house.data, "ink": "single"})
    assert explicit.ink == "single"
    assert profiles.digest(explicit) == profiles.digest(house)


@pytest.mark.layer("unit")
def test_a_color_profile_declares_color_and_keys_a_distinct_baseline():
    base = _synthetic()
    color = profiles.Profile(base.id, {**base.data, "ink": "color"})
    assert color.ink == "color"
    # A colour interior is a different physical object, so it must not share a
    # single-ink profile's visual baseline.
    assert profiles.digest(color) != profiles.digest(base)


@pytest.mark.layer("unit")
def test_an_unknown_ink_is_refused():
    bad = profiles.Profile("bad", {**_synthetic().data, "ink": "duotone"})
    with pytest.raises(SystemExit, match="ink must be 'single' or 'color'"):
        _ = bad.ink


@pytest.mark.layer("unit")
def test_unknown_profile_is_refused_before_rendering():
    with pytest.raises(SystemExit) as exc:
        profiles.load("no-such-profile")
    assert "unknown print profile" in str(exc.value)
    # The refusal names what is available, so a typo is diagnosable.
    assert profiles.HOUSE in str(exc.value)


# --- Trim profiles: large-print (#216), digest and mass-market (#217) -------

# The exact digest of every sealed profile. Pinning the literals is the
# byte-identity contract: a design profile is sealed by its major, so its
# digest -- which keys the visual baseline -- must not move without a design
# change. If an edit to a shipped profile changes one of these, that is the
# test catching a design drift, not a value to bump. The existing three
# (house, its colour twin, novella) must stay byte-identical as new profiles
# are added; the trim profiles seal at these values.
PROFILE_DIGESTS = {
    "house-6x9": "c524978840a0af4e",
    "house-6x9-color": "a280760e423612e8",
    "novella-5x8": "ae1fb2ce3e139411",
    "large-print-7x10": "2165d6840d062455",
    "digest-5.5x8.5": "cdaa82a294fa2862",
    "mass-market-4.25x6.87": "c37446c8ab4dbfcc",
}


@pytest.mark.layer("unit")
@pytest.mark.parametrize("profile_id, digest", sorted(PROFILE_DIGESTS.items()))
def test_every_profile_seals_at_its_pinned_digest(profile_id, digest):
    # Byte-identity: each shipped profile loads and hashes to its sealed
    # value, so adding a trim profile cannot silently shift an existing one.
    assert profiles.digest(profiles.load(profile_id)) == digest


@pytest.mark.layer("unit")
def test_all_profile_digests_are_pairwise_distinct():
    # No two shipped designs may collide -- a shared digest would let one
    # profile's visual baseline stand in for another's.
    digs = [profiles.digest(profiles.load(pid)) for pid in PROFILE_DIGESTS]
    assert len(set(digs)) == len(digs)


@pytest.mark.layer("unit")
@pytest.mark.parametrize("profile_id, trim, cap", [
    ("large-print-7x10", (7.0, 10.0), 7.2),
    ("digest-5.5x8.5", (5.5, 8.5), 6.0),
    ("mass-market-4.25x6.87", (4.25, 6.87), 4.8),
])
def test_trim_profile_loads_with_its_declared_geometry(profile_id, trim, cap):
    p = profiles.load(profile_id)
    assert p.trim == trim
    assert p.figure_cap == cap
    assert p.ink == "single"
    # The figure cap stays clear of the text block -- the LuaLaTeX empty-page
    # scar. The text block is the page height less the vertical margins.
    m = p.margins
    text_height = trim[1] - m["top"] - m["bottom"]
    assert p.figure_cap < text_height - 0.5


@pytest.mark.layer("unit")
def test_large_print_is_a_genuinely_larger_design():
    # The accessibility point of #216: a bigger base face and markedly more
    # open leading than the house, not merely a resized page.
    house, lp = profiles.load("house-6x9"), profiles.load("large-print-7x10")
    assert lp.trim[0] > house.trim[0] and lp.trim[1] > house.trim[1]
    assert float(lp.typography["leading"]) > float(house.typography["leading"])
    assert lp.web["base-size"] == "1.4rem"      # larger than the house 1.25rem
    assert float(lp.web["line-height"]) > float(house.web["line-height"])


@pytest.mark.layer("unit")
def test_mass_market_is_the_densest_design():
    # The mass-market discipline (#217): the tightest leading and the
    # narrowest web measure of the shipped profiles, so a long novel fits the
    # rack spine.
    leadings = {pid: float(profiles.load(pid).typography["leading"])
                for pid in PROFILE_DIGESTS}
    assert leadings["mass-market-4.25x6.87"] == min(leadings.values())


@pytest.mark.layer("unit")
@pytest.mark.parametrize("profile_id, measure", [
    ("large-print-7x10", "54rem"),
    ("digest-5.5x8.5", "44rem"),
    ("mass-market-4.25x6.87", "34rem"),
])
def test_trim_profile_web_css_overrides_only_the_measure(profile_id, measure):
    css = profiles.web_css(profiles.load(profile_id))
    assert f"max-width: {measure}" in css
    # It touches the reading measure only -- never the palette or font the
    # aesthetic controls.
    assert "color" not in css and "font-family" not in css


@pytest.mark.layer("unit")
@pytest.mark.parametrize("profile_id, expect", [
    ("large-print-7x10", "paperwidth=7in,paperheight=10in"),
    ("digest-5.5x8.5", "paperwidth=5.5in,paperheight=8.5in"),
    ("mass-market-4.25x6.87", "paperwidth=4.25in,paperheight=6.87in"),
])
def test_trim_profile_geometry_tex_projects_its_trim(profile_id, expect):
    assert expect in profiles.geometry_tex(profiles.load(profile_id))


@pytest.mark.layer("unit")
def test_trim_profiles_are_offered_by_the_providers_that_cut_them():
    # Provider support is the honest matrix: every vendor cuts 7x10 and
    # 5.5x8.5, but only Lulu cuts the 4.25x6.87 pocketbook, so KDP and
    # IngramSpark must REFUSE the mass-market trim (a known-bad the producer
    # rejects) rather than guess a wrap for a size they do not make.
    from press import provider_specs

    def offered(provider: str, profile_id: str) -> bool:
        w, h = profiles.load(profile_id).trim
        return not provider_specs.load(provider).check_selection(w, h, "perfect-bound")

    for provider in ("lulu", "kdp", "ingramspark"):
        assert offered(provider, "large-print-7x10")
        assert offered(provider, "digest-5.5x8.5")
    assert offered("lulu", "mass-market-4.25x6.87")
    assert not offered("kdp", "mass-market-4.25x6.87")
    assert not offered("ingramspark", "mass-market-4.25x6.87")
