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
