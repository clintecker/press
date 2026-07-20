"""Provider qualification: the record is well-formed and explicit, and the
gate lets only a passed, edition-scoped physical inspection qualify a
provider. Marketing evidence, a failed point, a not-fit provider, and an
inspection of a different edition are each refused.
"""

from __future__ import annotations

import copy

import pytest

from press import edition, qualification as q


def _passed(**over):
    results = {point: q.PASS for point in q.REQUIRED_CHECKLIST}
    return q.PhysicalInspection(
        edition_id=over.get("edition_id", "ed-1"),
        provider=over.get("provider", "lulu"),
        product_id=over.get("product_id", "PB-BW-6x9"),
        region=over.get("region", "US"),
        inspector=over.get("inspector", "inspector"),
        results=over.get("results", results))


# ---- the record ----

def test_the_shipped_record_validates():
    assert q.validate() == []


def test_lulu_is_the_primary_provider():
    provs = q.providers()
    assert provs["lulu"].disposition == "primary"


def test_installed_package_falls_back_to_its_provider_record(monkeypatch, tmp_path):
    monkeypatch.setattr(q, "SOURCE_RECORD", tmp_path / "no-repository-here.yaml")
    record = q.load()
    assert record["schema_version"] == q.SCHEMA_VERSION
    assert "lulu" in record["providers"]


def test_packaged_provider_record_cannot_drift_from_repository_copy(
        monkeypatch, tmp_path):
    stale = tmp_path / "providers.yaml"
    stale.write_text("schema_version: 1\nproviders: {}\n", encoding="utf-8")
    monkeypatch.setattr(q, "PACKAGED_RECORD", stale)
    assert any("packaged provider record has drifted" in problem
               for problem in q.validate())


@pytest.mark.invariant("INV-provider-qualification")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_an_implicit_capability_is_refused():
    record = copy.deepcopy(q.load())
    del record["providers"]["lulu"]["capabilities"]["webhooks"]
    problems = q.validate(record)
    assert any("webhooks" in p and "not declared" in p for p in problems)


@pytest.mark.invariant("INV-provider-qualification")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_checklist_missing_a_point_is_refused():
    record = copy.deepcopy(q.load())
    record["physical_checklist"] = [p for p in record["physical_checklist"] if p != "barcode"]
    assert any("barcode" in p for p in q.validate(record))


@pytest.mark.invariant("INV-provider-qualification")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_an_unknown_capability_value_is_refused():
    record = copy.deepcopy(q.load())
    record["providers"]["lulu"]["capabilities"]["api"] = "maybe"
    assert any("api=" in p for p in q.validate(record))


# ---- the gate ----

def test_a_full_pass_qualifies_the_provider():
    qual, problems = q.qualify(_passed(edition_id="ed-1"), "ed-1")
    assert problems == []
    assert isinstance(qual, edition.ProviderQualification)
    assert qual.provider == "lulu"
    assert qual.qualified_for == "ed-1"
    # The qualification is verifiable evidence, and it satisfies the edition.
    manifest = _manifest_with(qual)
    assert edition.verify_facts(manifest, _observed(manifest)) == []


@pytest.mark.invariant("INV-provider-qualification")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_failed_point_cannot_qualify():
    results = {point: q.PASS for point in q.REQUIRED_CHECKLIST}
    results["spine"] = "fail"
    qual, problems = q.qualify(_passed(results=results), "ed-1")
    assert qual is None
    assert any("not passed" in p and "spine" in p for p in problems)


@pytest.mark.invariant("INV-provider-qualification")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_not_fit_provider_cannot_qualify():
    qual, problems = q.qualify(_passed(provider="48-hour-books"), "ed-1")
    assert qual is None
    assert any("cannot be qualified for production" in p for p in problems)


@pytest.mark.invariant("INV-provider-qualification")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_an_inspection_of_another_edition_is_stale():
    qual, problems = q.qualify(_passed(edition_id="ed-OTHER"), "ed-1")
    assert qual is None
    assert any("different edition" in p for p in problems)


def test_an_unknown_provider_is_refused():
    qual, problems = q.qualify(_passed(provider="acme-print"), "ed-1")
    assert qual is None
    assert any("unknown provider" in p for p in problems)


def test_render_lists_the_checklist_and_providers():
    text = q.render()
    # The checklist points and their descriptions are present.
    assert "content" in text and "tracking" in text
    assert "the EAN-13 scans" in text  # a checklist description
    # Providers render as cards with their id and disposition.
    assert "## Lulu" in text and "`lulu`" in text
    assert "Primary provider" in text


def test_qualification_cli_reports_the_validated_record(capsys):
    assert q.main([]) == 0
    output = capsys.readouterr().out
    assert "provider qualification record holds" in output
    assert "11-point physical checklist" in output


# ---- helpers tying qualification to the edition manifest ----

def _manifest_with(qual):
    import dataclasses

    base = edition.EditionManifest(
        schema_version=edition.SCHEMA_VERSION, edition_id="ed-1", slug="mk",
        title="MK", format="paperback", isbn=None, trim_width=6.0,
        trim_height=9.0, page_count=100, paper="cream", spine_width_in=0.25,
        bleed_in=0.125,
        interior=edition.ArtifactRef("interior", "a" * 64, 1000),
        cover=edition.ArtifactRef("cover", "b" * 64, 500),
        toolchain_digest="sha-x", source_commit="c", tree_clean=True,
        input_digests={}, receipt_digests=("r0",))
    # Bind the real identity, then attach the qualification against it.
    ident = edition._identity_digest(base)
    real_qual = dataclasses.replace(qual, qualified_for=ident)
    return dataclasses.replace(base, edition_id=ident, qualifications=(real_qual,))


def _observed(m):
    return edition.Observed(m.interior.sha256, m.interior.byte_size,
                            m.page_count, m.cover.sha256, m.cover.byte_size)
