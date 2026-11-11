"""The v1->v2 migration contract at the unit level: the pin regex reads both
sites and floats an immutable pin, diagnosis refuses a split or absent pin,
and apply/rollback are an exact byte round-trip that never touches owned
content. The full scaffolded-book proof lives in selftest.check_migration.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from press import migrate


def _book(tmp_path: Path, req: str, workflow: str) -> Path:
    (tmp_path / "requirements.txt").write_text(req, encoding="utf-8")
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "book.yml").write_text(workflow, encoding="utf-8")
    return tmp_path


REQ_V1 = "press @ git+https://github.com/clintecker/press@v1\n"
WF_V1 = "    uses: clintecker/press/.github/workflows/build.yml@v1\n"


@pytest.mark.layer("unit")
def test_pin_sites_finds_both(tmp_path):
    book = _book(tmp_path, REQ_V1, WF_V1)
    sites = migrate.pin_sites(book)
    paths = {s.path for s in sites}
    assert "requirements.txt" in paths
    assert ".github/workflows/book.yml" in paths
    assert all(s.major == 1 for s in sites)


@pytest.mark.layer("unit")
def test_absent_pin_is_diagnosed_not_crashed(tmp_path):
    diagnosis = migrate.diagnose(tmp_path)
    assert diagnosis.problems
    assert diagnosis.from_major is None


@pytest.mark.layer("unit")
def test_split_pin_is_refused(tmp_path):
    book = _book(tmp_path, REQ_V1, "    uses: clintecker/press/.github/workflows/build.yml@v2\n")
    diagnosis = migrate.diagnose(book)
    assert diagnosis.from_major is None
    assert any("more than one major" in p for p in diagnosis.problems)
    with pytest.raises(SystemExit):
        migrate.plan(book, 3)


@pytest.mark.layer("unit")
@pytest.mark.invariant("INV-migration-preview")
@pytest.mark.proof("negative")
def test_plan_writes_nothing(tmp_path):
    book = _book(tmp_path, REQ_V1, WF_V1)
    before = {p: p.read_bytes() for p in book.rglob("*") if p.is_file()}
    plan = migrate.plan(book, 2)
    assert plan.from_major == 1 and plan.to_major == 2
    assert len(plan.changes) == 2
    for path, original in before.items():
        assert path.read_bytes() == original


@pytest.mark.layer("unit")
@pytest.mark.invariant("INV-migration-safe")
@pytest.mark.proof("negative")
def test_apply_then_rollback_is_exact(tmp_path):
    book = _book(tmp_path, REQ_V1, WF_V1)
    before = {p: p.read_bytes() for p in book.rglob("*") if p.is_file()}
    migrate.apply(book, 2)
    assert all(s.major == 2 for s in migrate.pin_sites(book))
    assert (book / migrate.STATE_DIR / migrate.RECEIPT).is_file()
    migrate.rollback(book)
    assert all(s.major == 1 for s in migrate.pin_sites(book))
    # Every pre-migration file is byte-for-byte restored.
    for path, original in before.items():
        assert path.read_bytes() == original
    assert not (book / migrate.STATE_DIR / migrate.BACKUP).is_file()


@pytest.mark.layer("unit")
def test_immutable_pin_is_floated(tmp_path):
    book = _book(
        tmp_path,
        "press @ git+https://github.com/clintecker/press@v1.20.0\n",
        "    uses: clintecker/press/.github/workflows/build.yml@v1.20.0\n",
    )
    assert migrate.diagnose(book).from_major == 1
    migrate.apply(book, 2)
    text = (book / "requirements.txt").read_text(encoding="utf-8")
    assert "@v2" in text and "@v1.20.0" not in text


@pytest.mark.layer("unit")
def test_migrating_to_same_major_refused(tmp_path):
    book = _book(tmp_path, REQ_V1, WF_V1)
    with pytest.raises(SystemExit):
        migrate.plan(book, 1)


@pytest.mark.layer("unit")
def test_rollback_without_migration_refused(tmp_path):
    book = _book(tmp_path, REQ_V1, WF_V1)
    with pytest.raises(SystemExit):
        migrate.rollback(book)


@pytest.mark.layer("unit")
def test_status_reports_pin_and_receipt(tmp_path):
    book = _book(tmp_path, REQ_V1, WF_V1)
    assert "pinned to v1" in migrate.status(book)
    migrate.apply(book, 2)
    reported = migrate.status(book)
    assert "pinned to v2" in reported
    assert "rollback" in reported


@pytest.mark.layer("unit")
def test_diagnose_rejects_a_book_apply_repinned_only_halfway(tmp_path, monkeypatch):
    # The no-blind-verifier fixture for apply: regress the plan so apply
    # rewrites requirements.txt but skips the workflow, the half-migrated
    # book a lost pin site leaves. Diagnosis must name the split major
    # rather than read the book as migrated.
    book = _book(tmp_path, REQ_V1, WF_V1)
    real_plan = migrate.plan

    def plan_missing_the_workflow(root, to_major):
        full = real_plan(root, to_major)
        kept = tuple(c for c in full.changes if c.path == "requirements.txt")
        return migrate.MigrationPlan(full.from_major, full.to_major, kept, full.notes)

    monkeypatch.setattr(migrate, "plan", plan_missing_the_workflow)
    migrate.apply(book, 2)

    diagnosis = migrate.diagnose(book)
    assert diagnosis.from_major is None
    assert any("more than one major" in p for p in diagnosis.problems)


@pytest.mark.layer("unit")
def test_diagnose_rejects_a_book_rollback_restored_from_a_bad_backup(tmp_path):
    # The no-blind-verifier fixture for rollback: restore from a backup that
    # no longer holds the pre-migration bytes of one site (it was edited
    # after apply wrote it). The restored book is split across two majors,
    # and diagnosis must refuse it instead of reading it as rolled back.
    import json

    book = _book(tmp_path, REQ_V1, WF_V1)
    migrate.apply(book, 2)
    backup_path = book / migrate.STATE_DIR / migrate.BACKUP
    backup = json.loads(backup_path.read_text(encoding="utf-8"))
    backup["files"][".github/workflows/book.yml"] = WF_V1.replace("@v1", "@v3")
    backup_path.write_text(json.dumps(backup), encoding="utf-8")

    migrate.rollback(book)

    diagnosis = migrate.diagnose(book)
    assert diagnosis.from_major is None
    assert any("more than one major" in p for p in diagnosis.problems)


REQ_V2 = "press @ git+https://github.com/clintecker/press@v2\n"
WF_V2 = "    uses: clintecker/press/.github/workflows/build.yml@v2\n"


@pytest.mark.layer("unit")
def test_v2_to_v3_plan_does_not_claim_byte_for_byte_parity(tmp_path):
    plan = migrate.plan(_book(tmp_path, REQ_V2, WF_V2), 3)
    joined = " ".join(plan.notes)
    assert "byte-for-byte" not in joined
    assert "design major" in joined and "MIGRATION.md" in joined


@pytest.mark.layer("unit")
def test_v1_to_v2_plan_still_states_geometry_parity(tmp_path):
    plan = migrate.plan(_book(tmp_path, REQ_V1, WF_V1), 2)
    assert any("byte-for-byte" in n for n in plan.notes)


@pytest.mark.layer("unit")
def test_unknown_major_gets_the_neutral_note():
    note = migrate.design_note(3, 9)
    assert "byte-for-byte" not in note and "MIGRATION.md" in note and "v9" in note
