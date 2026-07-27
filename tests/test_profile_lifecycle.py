"""The print-profile lifecycle: scaffold, prove, seal (#221).

These tests pin the seal gate (a shipped profile that is unsealed or whose
geometry drifted from its seal is refused -- the design-contract law) and the
scaffolder (a new profile starts from proven geometry and loads as valid
data). The golden-copy toolchain proof -- every shipped profile renders at its
declared trim -- lives in tests/test_visual_regression.py, where the toolchain
guard is.
"""

from __future__ import annotations

import pytest

from press import booklib
from press import profile_lifecycle as pl
from press import profiles


def _isolated_profiles(tmp_path, monkeypatch):
    """A profiles directory seeded with the real house profile, so a
    scaffold's base loads and its output, reload, and seal all share one
    directory without touching the packaged data."""

    real = booklib.DATA / "profiles" / f"{profiles.HOUSE}.yaml"
    (tmp_path / real.name).write_text(real.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(profiles, "profiles_dir", lambda: tmp_path)
    return tmp_path


@pytest.mark.layer("unit")
def test_shipped_ledger_holds_and_covers_every_profile():
    # The ledger the press ships passes its own gate, and no shipped profile
    # is left unsealed.
    seals = pl.load_seals()
    assert seals, "the press ships a profile seal ledger"
    shipped = {p.stem for p in profiles.profiles_dir().glob("*.yaml")}
    assert shipped <= set(seals), f"unsealed profiles: {shipped - set(seals)}"
    assert pl.validate(seals) == []


@pytest.mark.layer("unit")
def test_seal_digest_matches_the_live_profile():
    # Each seal records the digest the profile actually has now.
    for pid, seal in pl.load_seals().items():
        assert seal.digest == profiles.digest(profiles.load(pid))


@pytest.mark.layer("unit")
def test_unsealed_profile_is_refused():
    seals = pl.load_seals()
    victim = next(iter(seals))
    without = {k: v for k, v in seals.items() if k != victim}
    problems = pl.validate(without)
    assert any("is not sealed" in p and victim in p for p in problems)


@pytest.mark.layer("unit")
def test_digest_drift_is_refused():
    # A profile whose geometry no longer matches its sealed digest is a
    # design-major decision, refused until re-sealed.
    seals = dict(pl.load_seals())
    victim = next(iter(seals))
    seals[victim] = pl.Seal(victim, seals[victim].design_major, "deadbeefdeadbeef", "2026-07-25")
    problems = pl.validate(seals)
    assert any("drifted from its seal" in p for p in problems)


@pytest.mark.layer("unit")
def test_design_major_mismatch_is_refused():
    seals = dict(pl.load_seals())
    victim = next(iter(seals))
    real = seals[victim]
    seals[victim] = pl.Seal(victim, real.design_major + 9, real.digest, real.qualified_on)
    problems = pl.validate(seals)
    assert any("design-major" in p for p in problems)


@pytest.mark.layer("unit")
def test_seal_for_a_missing_profile_is_refused():
    seals = dict(pl.load_seals())
    seals["no-such-profile"] = pl.Seal("no-such-profile", 1, "x", "2026-07-25")
    problems = pl.validate(seals)
    assert any("not a shipped profile" in p for p in problems)


@pytest.mark.layer("unit")
def test_empty_ledger_reports_nothing():
    # An install that ships no ledger cannot check, and says so by being
    # silent rather than crashing.
    assert pl.validate({}) == []


@pytest.mark.layer("unit")
def test_scaffold_produces_a_loadable_profile_at_the_declared_trim():
    from press import yamlio

    text = pl.scaffold("trade-5-5x8-5", "5.5x8.5")
    data = yamlio.loads(text)
    assert data["id"] == "trade-5-5x8-5"
    assert data["trim"] == {"width": 5.5, "height": 8.5}
    # A profile built from this text carries the declared trim and inherits
    # the base's proven typography.
    profile = profiles.Profile(data["id"], data)
    assert profile.trim == (5.5, 8.5)
    assert profile.ink == "single"
    assert profile.typography == profiles.load(profiles.HOUSE).typography


@pytest.mark.layer("unit")
def test_scaffold_can_declare_colour_ink():
    from press import yamlio

    data = yamlio.loads(pl.scaffold("photo-8x10", "8x10", ink="color"))
    assert data["ink"] == "color"
    assert profiles.Profile(data["id"], data).ink == "color"


@pytest.mark.layer("unit")
@pytest.mark.parametrize("bad", ["6", "6x9x2", "0x9", "widexhigh"])
def test_scaffold_refuses_a_malformed_trim(bad):
    with pytest.raises(SystemExit, match="trim"):
        pl.scaffold("x", bad)


@pytest.mark.layer("unit")
def test_scaffold_refuses_a_bad_ink_and_a_bad_id():
    with pytest.raises(SystemExit, match="ink"):
        pl.scaffold("x", "6x9", ink="duotone")
    with pytest.raises(SystemExit, match="slug"):
        pl.scaffold("not a slug", "6x9")


@pytest.mark.layer("unit")
def test_write_scaffold_lands_a_loadable_profile_and_refuses_overwrite(tmp_path, monkeypatch):
    _isolated_profiles(tmp_path, monkeypatch)
    out = pl.write_scaffold("digest-5x8", "5x8")
    assert out == tmp_path / "digest-5x8.yaml"
    # It loads through the reader books use, at the declared trim.
    assert profiles.load("digest-5x8").trim == (5.0, 8.0)
    # A second scaffold of the same id does not clobber the first.
    with pytest.raises(SystemExit, match="already exists"):
        pl.write_scaffold("digest-5x8", "5x8")


@pytest.mark.layer("unit")
def test_seal_records_the_live_digest_and_round_trips(tmp_path, monkeypatch):
    _isolated_profiles(tmp_path, monkeypatch)
    pl.write_scaffold("digest-5x8", "5x8")
    ledger = tmp_path / "seals.yaml"

    seal = pl.write_seal("digest-5x8", "a new digest trim", on="2026-07-25", path=ledger)
    assert seal.digest == profiles.digest(profiles.load("digest-5x8"))
    # The written ledger re-reads to exactly what was sealed.
    reloaded = pl.load_seals(ledger)
    assert reloaded["digest-5x8"] == seal
    # A scaffolded-then-sealed profile passes the gate.
    assert pl.validate(reloaded, profile_ids=["digest-5x8"]) == []


@pytest.mark.layer("unit")
def test_render_seals_is_deterministic():
    seals = pl.load_seals()
    assert pl.render_seals(seals) == pl.render_seals(seals)
    # And the shipped ledger is exactly the canonical rendering of its data,
    # so scaffolding/sealing reproduce it byte-for-byte.
    assert pl.SEALS.read_text(encoding="utf-8") == pl.render_seals(seals)


@pytest.mark.layer("unit")
def test_cli_validate_and_scaffold_and_seal(tmp_path, monkeypatch, capsys):
    assert pl.main(["validate"]) == 0  # the shipped ledger holds
    _isolated_profiles(tmp_path, monkeypatch)
    assert pl.main(["scaffold", "digest-5x8", "--trim", "5x8"]) == 0
    assert (tmp_path / "digest-5x8.yaml").is_file()
    # An unknown action is a locatable refusal, not a crash.
    assert pl.main(["frobnicate"]) == 2
    assert "usage:" in capsys.readouterr().out
