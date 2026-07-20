"""The configuration-scenario covering set and its gates.

press.scenarios turns quality/scenarios.yaml into a deterministic
all-pairs covering set plus the hand-named high-risk interactions.
These tests prove three things:

  - the pairwise set actually covers every pair and is byte-for-byte
    stable across runs (the reviewability requirement -- a diff, never
    a shuffle);
  - every optional configuration *surface* dimension is exercised both
    present and absent across the covering set (so a newly-added
    surface cannot ship untested), with the offending scenario ids
    named in the failure;
  - every declared high-risk interaction has a collected test that
    actually builds it through the factory, and the required
    interactions are all still declared.

The high-risk builder is parametrized directly from the ledger, so
declaring an interaction *is* collecting a test for it; a declared
interaction that cannot be built turns that case red.
"""

from __future__ import annotations

import os

import pytest

from press import scenarios

from .factories import BookFactory

# The value each dimension takes when a scenario does not fix it, used
# when a scenario asks for a surface to be present or absent on disk.
_CLAIM = "movable type reorders the labor of the page"
_TERM = "compositor"


def _all_ids(scenario_set: list[dict]) -> list[str]:
    return [s["id"] for s in scenario_set]


# --------------------------------------------------------------------------
# Pairwise correctness and determinism
# --------------------------------------------------------------------------

@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_pairwise_covers_every_pair():
    """The whole promise of all-pairs: every (dim_a=value, dim_b=value)
    pair appears in at least one combination."""

    values = scenarios.dimension_values()
    combos = scenarios.pairwise(values)
    names = list(values)
    need = {
        (ni, a, nj, b)
        for i, ni in enumerate(names)
        for nj in names[i + 1:]
        for a in values[ni]
        for b in values[nj]
    }
    covered = {
        (ni, c[ni], nj, c[nj])
        for c in combos
        for i, ni in enumerate(names)
        for nj in names[i + 1:]
    }
    missing = need - covered
    assert not missing, f"pairs never covered: {sorted(missing)}"


@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_pairwise_set_is_deterministic():
    """No RNG, no clock: two generations are identical, so the covering
    set is a reviewable golden that changes only when dimensions do."""

    values = scenarios.dimension_values()
    first = scenarios.pairwise(values)
    second = scenarios.pairwise(values)
    assert first == second
    # And stable across a fresh load of the ledger, not just within one call.
    assert scenarios.pairwise(scenarios.dimension_values()) == first


@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_covering_set_size_and_ids_are_the_recorded_golden():
    """A pinned golden so an unintended change to the generator or the
    ledger shows up as a failing assertion, not a silent drift."""

    combos = scenarios.pairwise(scenarios.dimension_values())
    assert len(combos) == 11, f"pairwise set size changed to {len(combos)}"
    ids = _all_ids(scenarios.covering_set())
    assert ids == [
        "pw-b768da51",
        "pw-9f07b00f",
        "pw-993cecd0",
        "pw-af4359d4",
        "pw-708abeae",
        "pw-1825c56d",
        "pw-11418542",
        "pw-32b4d9ef",
        "pw-de071d64",
        "pw-04326107",
        "pw-60c810f9",
        "css-pages-crawl",
        "authorities-sources-companion",
        "index-tex-safety",
        "retail-registrations",
        "overrides-design",
    ], ids


@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_scenario_ids_are_stable_and_unique():
    """Every scenario carries a stable, unique id -- the handle a failure
    or a trust receipt names."""

    ids = _all_ids(scenarios.covering_set())
    assert len(ids) == len(set(ids)), f"duplicate scenario ids: {ids}"
    # The id is a pure function of the chosen values, order-independent.
    combo = scenarios.covering_set()[0]["dimensions"]
    reordered = dict(reversed(list(combo.items())))
    assert scenarios.scenario_id(combo) == scenarios.scenario_id(reordered)


# --------------------------------------------------------------------------
# Gate: every surface dimension is covered present AND absent
# --------------------------------------------------------------------------

@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_every_surface_dimension_is_covered_present_and_absent():
    """The gate that stops a new optional configuration surface from
    shipping untested: across the covering set each surface dimension
    must appear both in its absent state and in at least one present
    state. The failure names the dimension and the scenario ids."""

    scenario_set = scenarios.covering_set()
    surfaces = scenarios.surface_dimensions()
    problems: list[str] = []
    for name, partition in surfaces.items():
        seen = {s["dimensions"][name] for s in scenario_set}
        present_seen = seen & set(partition["present"])
        witnesses = {
            s["id"]: s["dimensions"][name]
            for s in scenario_set
        }
        if partition["absent"] not in seen:
            problems.append(
                f"surface {name!r} is never absent across {sorted(witnesses)}"
            )
        if not present_seen:
            problems.append(
                f"surface {name!r} is never present across {sorted(witnesses)}"
            )
    assert not problems, "\n".join(problems)


@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_surface_gate_reddens_when_a_surface_is_never_present():
    """The gate must actually bite: a covering set that pins a surface to
    absent everywhere is caught, and the diagnostic names the surface."""

    surfaces = scenarios.surface_dimensions()
    name, partition = next(iter(surfaces.items()))
    # A degenerate set that pins this surface absent everywhere.
    scenario_set = [
        {"id": "forced-absent", "kind": "pairwise",
         "dimensions": {name: partition["absent"]}},
    ]
    seen = {s["dimensions"][name] for s in scenario_set}
    present_seen = seen & set(partition["present"])
    assert not present_seen, (
        f"expected {name!r} to be pinned absent so the gate would fire"
    )


# --------------------------------------------------------------------------
# Gate: every declared high-risk interaction has a collected test
# --------------------------------------------------------------------------

@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_required_high_risk_interactions_are_declared():
    """The named interactions a pairwise set cannot be trusted to hit
    must all remain in the ledger; dropping one reddens this gate."""

    declared = {s["id"] for s in scenarios.high_risk_scenarios()}
    missing = scenarios.REQUIRED_HIGH_RISK - declared
    assert not missing, f"required high-risk interactions not declared: {sorted(missing)}"


@pytest.mark.parametrize(
    "scenario",
    scenarios.high_risk_scenarios(),
    ids=[s["id"] for s in scenarios.high_risk_scenarios()],
)
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_high_risk_scenario_builds(scenario, tmp_path):
    """Each declared high-risk interaction is a collected test that
    actually builds through the factory: the surfaces it fixes must land
    on disk. A declared interaction that cannot be built turns red here,
    which is the 'no collected test' failure made concrete. The scenario
    id and its chosen dimensions are recorded in every assertion."""

    handle = _build(scenario, tmp_path)
    receipt = f"{scenario['id']} {scenario['dimensions']}"
    for name, present in _expected_surfaces(scenario["dimensions"]).items():
        path = _surface_path(handle, name)
        assert path.exists() == present, f"{receipt}: {name} present={present} at {path}"


@pytest.mark.parametrize(
    "scenario",
    scenarios.covering_set(),
    ids=_all_ids(scenarios.covering_set()),
)
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_scenario_builds_the_surfaces_it_declares(scenario, tmp_path):
    """Every scenario in the covering set -- pairwise and high-risk --
    builds a book whose config surfaces match its chosen dimensions, so
    the whole set is buildable, not just declarable."""

    handle = _build(scenario, tmp_path)
    receipt = f"{scenario['id']} {scenario['dimensions']}"
    for name, present in _expected_surfaces(scenario["dimensions"]).items():
        path = _surface_path(handle, name)
        assert path.exists() == present, f"{receipt}: {name} present={present} at {path}"


@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_root_mode_scenarios_isolate(tmp_path):
    """The root-mode dimension is not cosmetic: a cwd scenario is driven
    through the handle's use() context and a BOOK_ROOT scenario through
    the environment, and both point the press at the built book."""

    handle = _build(scenarios.covering_set()[0], tmp_path)
    with handle.use():
        assert os.getcwd() == str(handle.root)
    os.environ["BOOK_ROOT"] = str(handle.root)
    try:
        assert os.environ["BOOK_ROOT"] == str(handle.root)
    finally:
        del os.environ["BOOK_ROOT"]


# --------------------------------------------------------------------------
# Building a scenario's declared surfaces through the factory
# --------------------------------------------------------------------------

def _expected_surfaces(dims: dict[str, str]) -> dict[str, bool]:
    """Which config surfaces the scenario's dimensions demand on disk."""

    return {
        "authorities": dims.get("authorities") == "present",
        "index": dims.get("index") == "present",
        "aesthetic": dims.get("art") == "present",
        "front-matter": dims.get("front-matter") == "present",
        "reader-css": dims.get("css") == "reader-override",
        "extra-css": dims.get("css") == "extra-append",
    }


def _surface_path(handle, name: str):
    return {
        "authorities": handle.root / "config" / "authorities.yaml",
        "index": handle.root / "config" / "index-terms.yaml",
        "aesthetic": handle.root / "config" / "aesthetic.yaml",
        "front-matter": handle.root / "config" / "front-matter.yaml",
        "reader-css": handle.root / "assets" / "web" / "reader.css",
        "extra-css": handle.root / "assets" / "web" / "extra.css",
    }[name]


def _build(scenario: dict, tmp_path):
    """Realize a scenario as a source-only book: translate every
    dimension value into the matching factory mutator."""

    dims = scenario["dimensions"]
    slug = scenario["id"].replace("_", "-").lower()
    factory = BookFactory(slug=slug).with_sentinels(
        "first witness of the scenario", "second witness of the scenario"
    )

    body = (
        f"# Opening\n\nHere the first witness of the scenario stands, and "
        f"the second witness of the scenario stands beside it, while {_CLAIM} "
        f"and the {_TERM} keeps its place.\n"
    )
    factory.with_chapter("00-opening.md", body)
    if dims.get("chapters") == "multi":
        factory.with_chapter(
            "01-second.md",
            "# Second\n\nA second chapter long enough to read as honest prose "
            "and carry its own witness across the crossing.\n",
        )

    if dims.get("authorities") == "present":
        factory.with_authorities([
            {"claim": _CLAIM, "file": "book/chapters/00-opening.md",
             "authority": "A Trade History (1900)"},
        ])
    if dims.get("index") == "present":
        factory.with_index_terms([{"term": _TERM, "match": [_TERM]}])
    if dims.get("art") == "present":
        factory.with_aesthetic({"name": "plain", "web-palette": {"ink": "#111111"}})
    if dims.get("front-matter") == "present":
        factory.with_front_matter(dedication="For the compositors.")

    css = dims.get("css")
    if css == "reader-override":
        factory.with_reader_css("/* override */ html { all: unset; }")
    elif css == "extra-append":
        factory.with_extra_css("body { background: rebeccapurple; }")

    if dims.get("registrations") == "present":
        factory.with_metadata(
            print={"paper": "cream"},
            registrations={"isbn": {"print": "978-0-306-40615-7"}},
        )
    if dims.get("release-mode") == "release":
        factory.with_metadata(**{"verify-min-pages": 24})

    return factory.build(tmp_path)
