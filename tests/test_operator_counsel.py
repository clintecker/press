"""Counsel mode keeps its hands off the manuscript, and proves it.

`press improve` with no --apply is counsel, not surgery: it fingerprints
every manuscript and config byte before the workflow runs and again after,
and aborts if a single byte moved. Existing coverage only proves the
claude-absent refusal in run_workflow; this proves the fingerprint gate
itself -- the promise that a counsel run cannot silently edit the book.
"""

from __future__ import annotations

import pytest


def test_improve_counsel_aborts_when_workflow_touches_manuscript(scaffolded_book, monkeypatch):
    from press import operator

    chapter = next((scaffolded_book / "book" / "chapters").glob("*.md"))

    def mutating_workflow(name, args_obj, full_bash, extra_tools=None):
        # A counsel run must not do this; the stub stands in for a workflow
        # that misbehaves and edits the manuscript after the before-hash.
        chapter.write_text(chapter.read_text(encoding="utf-8") + "\nsmuggled\n", encoding="utf-8")
        # Write the report too, so that if the fingerprint guard is removed the
        # run reaches a clean `return 0` (no exception) -- the fail-when-broken
        # signal is then pytest.raises seeing no SystemExit at all.
        report = scaffolded_book / "build" / "editorial-report.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("# report\n", encoding="utf-8")
        return 0

    monkeypatch.setattr(operator, "run_workflow", mutating_workflow)

    with pytest.raises(SystemExit) as caught:
        operator.improve([])
    assert "counsel mode changed the manuscript" in str(caught.value)
