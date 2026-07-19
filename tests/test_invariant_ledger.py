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
