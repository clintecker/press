"""The round-0 producer ledger triage: no expired pending entry, no vague reason."""

import datetime as dt
import re
from pathlib import Path

from press import yamlio

ROOT = Path(__file__).resolve().parents[1]
LEDGER = yamlio.load(ROOT / ".celebrimbor" / "producers.yaml")
SURFACES = yamlio.load(ROOT / ".celebrimbor" / "surfaces.yaml")
WRITE_MARKERS = (
    "write_text",
    "write_bytes",
    ".write(",
    "open(",
    "yamlio.write",
    "subprocess",
    "unlink",
    "mkdir",
    "shutil",
    "os.replace",
)


def test_no_pending_producer_has_an_expired_review_date():
    today = dt.date.today()
    expired = {
        s: e["review_by"]
        for s, e in LEDGER["pending"].items()
        if dt.date.fromisoformat(str(e["review_by"])) < today
    }
    assert expired == {}


def test_every_pending_reason_names_the_owed_verifier_or_an_issue():
    for subject, entry in LEDGER["pending"].items():
        assert re.search(r"#\d+|verify|verifier", entry["reason"]), subject


def _source_of(subject: str) -> str:
    module, _, name = subject.partition(":")
    text = (ROOT / "src" / "press" / f"{module}.py").read_text()
    if not name:
        return text
    m = re.search(rf"^def {name}\(.*?(?=^def |\Z)", text, re.S | re.M)
    assert m, subject
    return m.group(0)


RECLASSIFIED = [
    "catalog:render_usage",
    "catalog:render_global_help",
    "catalog:render_command_help",
    "yamlio:dump",
    "invariants:render",
    "selftest:render_reference",
    "qualification:render",
    # The scenarios module default was `producer`; covering_set is the one
    # public callable that inherited it (every other carries its own role).
    # The module text as a whole holds `load`'s read-only `.open(`.
    "scenarios:covering_set",
]  # extend per Class B decisions


def test_reclassified_callables_write_nothing():
    for subject in RECLASSIFIED:
        body = _source_of(subject)
        assert not any(m in body for m in WRITE_MARKERS), subject


def test_reclassified_callables_are_ratified_pure():
    for subject in RECLASSIFIED:
        module, _, name = subject.partition(":")
        entry = SURFACES["modules"][module]
        assert entry.get("overrides", {}).get(name, entry["role"]) == "pure", subject
