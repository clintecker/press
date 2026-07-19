"""The fixture provenance manifest is itself audited: the shipped
manifest must account for every checked-in regression fixture, and the
auditor must turn red when an entry or a file goes missing, when two
entries claim one file, when an invariant is unknown, or when the
manifest's diagnostic drifts from the fixture's inline one.

Facts once: test_shipped_manifest_holds runs the same audit the selftest
check runs, so the CLI and this suite cannot disagree about whether the
real manifest is sound. The remaining cases build tiny synthetic
manifests and fixture trees so a failure names exactly which guarantee
broke.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from press import fixture_provenance


INVARIANTS = [
    {"id": "INV-editorial-battery", "enforcer": "style_audit"},
    {"id": "INV-editorial-jargon", "enforcer": "jargon_lint"},
]


def write_fixture(directory: Path, name: str, expect: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(
        f"<!-- expect: {expect} -->\n# Fixture\n\nBody.\n", encoding="utf-8"
    )


def entry(**overrides):
    base = {
        "file": "em-dash.md",
        "kind": "source",
        "invariant": "INV-editorial-battery",
        "provenance": "a clean chapter",
        "mutation": "one em dash",
        "expected_result": "rejected",
        "checker": "style_audit",
        "expect": "em dash",
        "regenerate": "hand-authored",
    }
    base.update(overrides)
    return base


def test_shipped_manifest_holds():
    from press import invariants

    problems = fixture_provenance.audit(
        fixture_provenance.load(),
        fixture_provenance.KNOWN_BAD,
        invariants.load(),
    )
    assert problems == [], problems


def test_selftest_check_passes():
    fixture_provenance.check()


def test_sound_synthetic_manifest_holds(tmp_path):
    write_fixture(tmp_path, "em-dash.md", "em dash")
    problems = fixture_provenance.audit([entry()], tmp_path, INVARIANTS)
    assert problems == [], problems


def test_orphan_fixture_file_fails(tmp_path):
    write_fixture(tmp_path, "em-dash.md", "em dash")
    write_fixture(tmp_path, "curly-quotes.md", "curly")
    problems = fixture_provenance.audit([entry()], tmp_path, INVARIANTS)
    assert any("curly-quotes.md" in p and "absent" in p for p in problems), problems


def test_removing_entry_turns_the_auditor_red(tmp_path):
    """Prove the auditor turns red when a manifest entry is removed: an
    entry drops, its fixture file remains, the orphan is reported."""

    write_fixture(tmp_path, "em-dash.md", "em dash")
    with_entry = fixture_provenance.audit([entry()], tmp_path, INVARIANTS)
    assert with_entry == [], with_entry
    without_entry = fixture_provenance.audit([], tmp_path, INVARIANTS)
    assert any("em-dash.md" in p and "absent" in p for p in without_entry), without_entry


def test_missing_fixture_file_fails(tmp_path):
    """An entry naming a file that has left the tree is a finding."""

    problems = fixture_provenance.audit([entry(file="ghost.md")], tmp_path, INVARIANTS)
    assert any("ghost.md" in p and "no such fixture file" in p for p in problems), problems


def test_duplicate_entry_fails(tmp_path):
    write_fixture(tmp_path, "em-dash.md", "em dash")
    problems = fixture_provenance.audit([entry(), entry()], tmp_path, INVARIANTS)
    assert any("duplicate" in p for p in problems), problems


def test_unknown_invariant_fails(tmp_path):
    write_fixture(tmp_path, "em-dash.md", "em dash")
    problems = fixture_provenance.audit(
        [entry(invariant="INV-does-not-exist")], tmp_path, INVARIANTS
    )
    assert any("unknown invariant" in p for p in problems), problems


def test_checker_must_match_invariant_enforcer(tmp_path):
    write_fixture(tmp_path, "em-dash.md", "em dash")
    problems = fixture_provenance.audit(
        [entry(checker="jargon_lint")], tmp_path, INVARIANTS
    )
    assert any("is not the enforcer" in p for p in problems), problems


def test_diagnostic_drift_fails(tmp_path):
    write_fixture(tmp_path, "em-dash.md", "em dash")
    problems = fixture_provenance.audit(
        [entry(expect="something else")], tmp_path, INVARIANTS
    )
    assert any("disagrees with" in p for p in problems), problems


def test_source_fixture_without_inline_expect_fails(tmp_path):
    (tmp_path / "em-dash.md").write_text("# Fixture\n\nBody.\n", encoding="utf-8")
    problems = fixture_provenance.audit([entry()], tmp_path, INVARIANTS)
    assert any("no inline expect comment" in p for p in problems), problems


def test_missing_required_field_fails(tmp_path):
    write_fixture(tmp_path, "em-dash.md", "em dash")
    incomplete = entry()
    del incomplete["mutation"]
    problems = fixture_provenance.audit([incomplete], tmp_path, INVARIANTS)
    assert any("missing fields" in p and "mutation" in p for p in problems), problems


def test_unknown_field_fails(tmp_path):
    write_fixture(tmp_path, "em-dash.md", "em dash")
    problems = fixture_provenance.audit([entry(surprise="x")], tmp_path, INVARIANTS)
    assert any("unknown fields" in p for p in problems), problems


def test_binary_kind_requires_digest_or_generator(tmp_path):
    (tmp_path / "blob.md").write_text("binary stand-in", encoding="utf-8")
    without = entry(file="blob.md", kind="damaged-artifact")
    del without["expect"]
    problems = fixture_provenance.audit([without], tmp_path, INVARIANTS)
    assert any("source_digest or generator" in p for p in problems), problems
    with_generator = entry(
        file="blob.md", kind="damaged-artifact", generator="press build v1.11.2"
    )
    del with_generator["expect"]
    assert fixture_provenance.audit([with_generator], tmp_path, INVARIANTS) == []


def test_load_rejects_non_mapping(tmp_path):
    bad = tmp_path / "fixtures.yaml"
    bad.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="fixtures"):
        fixture_provenance.load(bad)
