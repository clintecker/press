"""The per-module coverage ratchet's comparison is pure and catches a
regression. The measurement side (running the suite under coverage) is a
CI gate, not re-run here; this proves the policy that decides pass/fail.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_ratchet():
    path = ROOT / "scripts" / "coverage_ratchet.py"
    spec = importlib.util.spec_from_file_location("coverage_ratchet", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_a_module_dropping_below_baseline_regresses():
    ratchet = _load_ratchet()
    baseline = {"receipts": 68.9, "impact": 83.7}
    # receipts fell far below its baseline; impact rose.
    current = {"receipts": 60.0, "impact": 90.0}
    regressions, new = ratchet.compare(current, baseline, tolerance=1.5)
    assert new == []
    assert len(regressions) == 1
    assert "receipts" in regressions[0]


def test_a_small_dip_within_tolerance_holds():
    ratchet = _load_ratchet()
    baseline = {"receipts": 68.9}
    current = {"receipts": 67.6}  # 1.3 under, within the 1.5 tolerance
    regressions, new = ratchet.compare(current, baseline, tolerance=1.5)
    assert regressions == []


def test_a_module_with_no_baseline_is_flagged_new():
    ratchet = _load_ratchet()
    regressions, new = ratchet.compare(
        {"receipts": 68.9, "brandnew": 40.0}, {"receipts": 68.9}, tolerance=1.5)
    assert regressions == []
    assert new == ["brandnew"]


def test_main_fails_when_measurement_contains_an_unbaselined_source_module(
        tmp_path, monkeypatch, capsys):
    """The executable gate, not only compare(), refuses a new module.

    This is the migration invariant that #178 exposed: adding source and
    tests without making an explicit baseline decision must keep CI red.
    """

    ratchet = _load_ratchet()
    baseline = tmp_path / "coverage-baseline.json"
    baseline.write_text(json.dumps({
        "tolerance": 0.5,
        "modules": {"receipts": 68.9},
    }), encoding="utf-8")
    monkeypatch.setattr(ratchet, "BASELINE", baseline)
    monkeypatch.setattr(
        ratchet, "measure", lambda: {"receipts": 68.9, "brandnew": 100.0})

    assert ratchet.main([]) == 1
    output = capsys.readouterr().out
    assert "modules with no coverage baseline" in output
    assert "brandnew" in output


def test_a_baselined_module_vanishing_is_a_regression():
    # A module dropping out of the measurement entirely must not pass
    # silently -- it means the report stopped covering it.
    ratchet = _load_ratchet()
    regressions, new = ratchet.compare(
        {"receipts": 68.9}, {"receipts": 68.9, "impact": 83.7}, tolerance=1.5)
    assert new == []
    assert any("impact" in r and "absent" in r for r in regressions)


def test_the_committed_baseline_is_well_formed():
    data = json.loads((ROOT / "quality" / "coverage-baseline.json").read_text())
    assert isinstance(data["tolerance"], (int, float))
    assert data["modules"]
    assert all(isinstance(v, (int, float)) for v in data["modules"].values())


def test_real_baseline_low_floors_are_all_justified():
    ratchet = _load_ratchet()
    modules = json.loads((ROOT / "quality" / "coverage-baseline.json")
                         .read_text(encoding="utf-8"))["modules"]
    # Every module floored below the line is on the reasoned allowlist, and no
    # allowlist entry has silently risen above it.
    assert ratchet.check_low_floors(modules) == []


def test_a_new_low_floor_without_a_reason_is_flagged():
    ratchet = _load_ratchet()
    modules = {m: 90.0 for m in ratchet.LOW_FLOOR_ALLOWED}  # clear the allowlist set
    modules["a_new_thin_module"] = 12.0
    issues = ratchet.check_low_floors(modules)
    assert any("a_new_thin_module" in i and "no reason" in i for i in issues)


def test_an_allowlisted_module_that_rose_is_flagged_stale():
    ratchet = _load_ratchet()
    someone = next(iter(ratchet.LOW_FLOOR_ALLOWED))
    modules = {m: 10.0 for m in ratchet.LOW_FLOOR_ALLOWED}
    modules[someone] = 95.0  # rose above the floor; its allowlist entry is stale
    issues = ratchet.check_low_floors(modules)
    assert any(someone in i and "remove it" in i for i in issues)
