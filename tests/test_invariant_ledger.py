"""The invariant ledger is itself an invariant: it must validate, and
every reference it makes must resolve.

These tests exercise the ledger machinery directly (the selftest runs
the same validation), including the negative cases that prove the
validator refuses a broken ledger rather than rubber-stamping it.
"""

from __future__ import annotations

import pytest

from press import invariants


def test_shipped_ledger_holds():
    invariants.validate(invariants.load())


def test_ledger_resolves_from_cwd_when_the_packaged_path_is_absent(monkeypatch):
    # The ledger is a repo file, not package data. When the code runs from an
    # installed wheel (the desk end-to-end proof) the __file__-relative path
    # lands in site-packages and does not exist; load() must then find the
    # ledger relative to the working directory (the checkout root), or the
    # collection plugin breaks the whole suite under an installed wheel.
    from pathlib import Path

    monkeypatch.setattr(invariants, "LEDGER", Path("/nonexistent/quality/invariants.yaml"))
    resolved = invariants._ledger_path()
    assert resolved.is_file()
    assert resolved == Path.cwd() / "quality" / "invariants.yaml"
    # And load() succeeds through the fallback.
    assert isinstance(invariants.load(), list)


def test_ledger_path_returns_the_packaged_path_when_nothing_resolves(monkeypatch, tmp_path):
    # Both the packaged path and the cwd path absent: return the packaged
    # path so the caller's open() reports the real, expected location.
    from pathlib import Path

    missing = Path("/nonexistent/quality/invariants.yaml")
    monkeypatch.setattr(invariants, "LEDGER", missing)
    monkeypatch.chdir(tmp_path)  # no quality/ here
    assert invariants._ledger_path() == missing


def test_load_accepts_an_explicit_path(tmp_path):
    ledger = tmp_path / "l.yaml"
    ledger.write_text("invariants: []\n", encoding="utf-8")
    assert invariants.load(ledger) == []


def test_generated_doc_matches_ledger():
    from pathlib import Path

    doc = Path(invariants.__file__).resolve().parent.parent.parent / "docs" / "INVARIANTS.md"
    assert doc.read_text(encoding="utf-8") == invariants.render()


def test_validator_rejects_dangling_enforcer():
    bad = [{
        "id": "INV-x", "statement": "s", "risk": "r", "criticality": "standard",
        "owner": "booklib", "enforcer": "booklib.no_such_function",
        "layers": ["selftest"], "negative": ["none"], "ci_tier": "quality",
        "limitations": "l",
    }]
    with pytest.raises(SystemExit, match="resolves to nothing"):
        invariants.validate(bad)


def test_validator_rejects_dangling_proof():
    bad = [{
        "id": "INV-x", "statement": "s", "risk": "r", "criticality": "standard",
        "owner": "booklib", "enforcer": "booklib",
        "layers": ["selftest"], "negative": ["check_does_not_exist"],
        "ci_tier": "quality", "limitations": "l",
    }]
    with pytest.raises(SystemExit, match="no selftest"):
        invariants.validate(bad)


def test_validator_rejects_undefended_critical():
    bad = [{
        "id": "INV-x", "statement": "s", "risk": "r", "criticality": "critical",
        "owner": "booklib", "enforcer": "booklib",
        "layers": ["selftest"], "negative": ["none"], "ci_tier": "quality",
        "limitations": "l",
    }]
    with pytest.raises(SystemExit, match="no real negative proof"):
        invariants.validate(bad)


def test_validator_rejects_duplicate_id():
    entry = {
        "id": "INV-dup", "statement": "s", "risk": "r", "criticality": "standard",
        "owner": "booklib", "enforcer": "booklib",
        "layers": ["selftest"], "negative": ["none"], "ci_tier": "quality",
        "limitations": "l",
    }
    with pytest.raises(SystemExit, match="duplicate id"):
        invariants.validate([entry, dict(entry)])


# ---- the ledger-completeness gate (selftest.check_ledger_completeness) ----

def _critical(negative):
    return {
        "id": "INV-x", "statement": "s", "risk": "r", "criticality": "critical",
        "owner": "booklib", "enforcer": "booklib",
        "layers": ["integration"], "negative": negative, "ci_tier": "integration",
        "limitations": "l",
    }


def test_completeness_gate_holds_on_the_shipped_ledger():
    """Every critical invariant in the real ledger has a fast-tier proof and
    no invariant declares zero proofs -- the shipped tree passes the gate."""

    from press import selftest

    selftest.check_ledger_completeness()  # does not raise


def test_completeness_gate_flags_a_critical_invariant_with_no_fast_proof(monkeypatch):
    """A critical invariant whose only proof is 'integration' -- no runnable
    selftest check, no collected pytest test -- is caught, the exact case
    invariants.validate (which only resolves references) lets through."""

    from press import selftest

    monkeypatch.setattr(selftest.invariants, "load", lambda: [_critical(["integration"])])
    monkeypatch.setattr(selftest, "_invariants_with_pytest_proof", set)
    with pytest.raises(SystemExit, match="no fast-tier proof"):
        selftest.check_ledger_completeness()


def test_completeness_gate_accepts_a_collected_pytest_proof(monkeypatch):
    """The same integration-only critical invariant passes once a pytest test
    is collected for it: the collected signal is a valid fast proof."""

    from press import selftest

    monkeypatch.setattr(selftest.invariants, "load", lambda: [_critical(["integration"])])
    monkeypatch.setattr(selftest, "_invariants_with_pytest_proof", lambda: {"INV-x"})
    selftest.check_ledger_completeness()  # does not raise


def test_completeness_gate_accepts_a_runnable_selftest_check(monkeypatch):
    """A runnable selftest check named in the proofs is a fast proof even with
    no collected pytest test."""

    from press import selftest

    monkeypatch.setattr(
        selftest.invariants, "load",
        lambda: [_critical(["check_imports"])])  # a real selftest check
    monkeypatch.setattr(selftest, "_invariants_with_pytest_proof", set)
    selftest.check_ledger_completeness()  # does not raise


def test_completeness_gate_flags_an_invariant_with_only_none(monkeypatch):
    """An invariant declaring only the 'none' placeholder, with nothing
    collected, is a guard on paper and is refused."""

    from press import selftest

    standard = _critical(["none"])
    standard["criticality"] = "standard"
    monkeypatch.setattr(selftest.invariants, "load", lambda: [standard])
    monkeypatch.setattr(selftest, "_invariants_with_pytest_proof", set)
    with pytest.raises(SystemExit, match="declares no proof"):
        selftest.check_ledger_completeness()
