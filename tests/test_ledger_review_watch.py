import datetime as dt
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "ledger_review_watch",
    Path(__file__).resolve().parents[1] / "scripts" / "ledger_review_watch.py",
)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)

LEDGER = {
    "version": 1,
    "producers": {},
    "pending": {
        "a:x": {"reason": "owed verifier (#300)", "review_by": "2027-01-15"},
        "b:y": {"reason": "owed verifier (#301)", "review_by": "2027-06-01"},
        "c:z": {"reason": "already expired", "review_by": "2026-12-01"},
    },
}


def test_expiring_includes_soon_and_already_expired_but_not_far():
    rows = w.expiring(LEDGER, dt.date(2026, 12, 20), 30)
    assert [r[0] for r in rows] == ["c:z", "a:x"]  # soonest first


def test_nothing_expiring_is_empty():
    assert w.expiring(LEDGER, dt.date(2026, 6, 1), 30) == []


def test_issue_title_is_stable_and_body_lists_each_subject():
    title, body = w.render_issue(w.expiring(LEDGER, dt.date(2026, 12, 20), 30))
    assert title == "Producer ledger: pending entries expire within 30 days"
    assert "c:z" in body and "a:x" in body and "2027-01-15" in body


def test_issue_action_edits_an_existing_issue_and_creates_otherwise():
    assert w.issue_action(None) == "create"
    assert w.issue_action(412) == "edit"


def test_pick_existing_prefers_exact_title_over_decoys():
    issues = [
        {"number": 5, "title": "Re: " + w.TITLE + " (discussion)"},
        {"number": 9, "title": w.TITLE},
        {"number": 7, "title": w.TITLE},
    ]
    assert w.pick_existing(issues, w.TITLE) == 7


def test_pick_existing_returns_none_when_only_decoys():
    issues = [{"number": 5, "title": "Re: " + w.TITLE + " (discussion)"}]
    assert w.pick_existing(issues, w.TITLE) is None
    assert w.pick_existing([], w.TITLE) is None
