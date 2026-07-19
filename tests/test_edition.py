"""The edition manifest: immutable identity, and a verifier that refuses
every way an order could name bytes the release did not approve.

A manifest that is only ever seen valid proves nothing; these build a
valid manifest, prove it holds, then forge its identity, tamper its
bytes, skip its receipts, and strand a stale qualification, and prove
each defect is named.
"""

from __future__ import annotations

import dataclasses

import pytest
from hypothesis import given
from hypothesis import strategies as st

from press import edition


def _manifest(**over) -> edition.EditionManifest:
    """A valid, release-gated manifest with a correctly derived identity."""

    base = edition.EditionManifest(
        schema_version=edition.SCHEMA_VERSION, edition_id="",
        slug="make-ready", title="Make Ready", format="paperback",
        isbn="9780306406157", trim_width=6.0, trim_height=9.0,
        page_count=180, paper="cream", spine_width_in=0.45, bleed_in=0.125,
        interior=edition.ArtifactRef("interior", "a" * 64, 500_000),
        cover=edition.ArtifactRef("cover", "b" * 64, 90_000),
        toolchain_digest="sha-202165d", source_commit="c0ffee1",
        tree_clean=True, input_digests={"invariants": "d1"},
        receipt_digests=("r0", "r1"))
    base = dataclasses.replace(base, **over)
    return dataclasses.replace(base, edition_id=edition._identity_digest(base))


def _observed(m: edition.EditionManifest) -> edition.Observed:
    return edition.Observed(m.interior.sha256, m.interior.byte_size,
                            m.page_count, m.cover.sha256, m.cover.byte_size)


# ---- L1 pure / property ----

def test_a_freshly_built_manifest_verifies():
    m = _manifest()
    assert edition.verify_facts(m, _observed(m)) == []


@pytest.mark.layer("property")
@given(pages=st.integers(min_value=24, max_value=2000),
       size=st.integers(min_value=1, max_value=10_000_000))
def test_canonical_identity_is_deterministic(pages, size):
    a = _manifest(page_count=pages,
                  interior=edition.ArtifactRef("interior", "c" * 64, size))
    b = _manifest(page_count=pages,
                  interior=edition.ArtifactRef("interior", "c" * 64, size))
    assert a.edition_id == b.edition_id
    assert a.digest() == b.digest()


def test_json_round_trip_preserves_identity_and_digest():
    m = _manifest()
    restored = edition.from_json(edition.to_json(m))
    assert restored == m
    assert restored.digest() == m.digest()


@pytest.mark.invariant("INV-edition-manifest")
@pytest.mark.layer("property")
@pytest.mark.proof("positive")
@given(field=st.sampled_from([
    "slug", "title", "format", "page_count", "paper", "trim_width",
    "spine_width_in", "toolchain_digest",
]))
def test_every_production_fact_moves_identity(field):
    m = _manifest()
    tweaks = {
        "slug": "other", "title": "Other", "format": "hardcover",
        "page_count": m.page_count + 1, "paper": "white",
        "trim_width": 6.14, "spine_width_in": m.spine_width_in + 0.01,
        "toolchain_digest": "sha-different",
    }
    moved = dataclasses.replace(m, **{field: tweaks[field]})
    assert edition._identity_digest(moved) != m.edition_id


@pytest.mark.layer("property")
@given(field=st.sampled_from(["source_commit", "tree_clean", "receipt_digests"]))
def test_provenance_does_not_move_identity(field):
    m = _manifest()
    tweaks = {"source_commit": "deadbee2", "tree_clean": False,
              "receipt_digests": ("r9",)}
    same = dataclasses.replace(m, **{field: tweaks[field]})
    # Provenance and capability are recorded but are not edition facts.
    assert edition._identity_digest(same) == m.edition_id


def test_a_provider_qualification_is_not_an_edition_fact():
    m = _manifest()
    qualified = dataclasses.replace(m, qualifications=(
        edition.ProviderQualification("lulu", "PB-BW", m.edition_id, "e" * 64),))
    # Adding a qualification must not change what the edition is.
    assert edition._identity_digest(qualified) == m.edition_id
    assert edition.verify_facts(qualified, _observed(qualified)) == []


def test_forbidden_key_scan_finds_nested_secrets():
    assert edition._forbidden_keys_present(
        {"price": 100, "nested": [{"secret": "x"}], "ok": 1}) == ["price", "secret"]
    assert edition._forbidden_keys_present(dataclasses.asdict(_manifest())) == []


def test_a_release_receipt_can_bind_the_edition_digest():
    # The manifest's identity is a stable digest a release receipt can
    # record as an artifact, binding a release to exactly this edition.
    from press import receipts

    m = _manifest()
    inputs = {"invariants": "d", "fixtures": "d", "scenarios": "d",
              "surfaces": "d", "toolchain": "sha-x"}
    release = receipts.Receipt(
        schema_version=receipts.SCHEMA_VERSION, layer="release",
        source_commit="c", tree_clean=True, inputs=inputs, prerequisites=[],
        proofs=[], artifacts={"edition": m.edition_id})
    assert release.artifacts["edition"] == m.edition_id
    # The receipt digest is stable, so the binding is verifiable.
    assert release.digest() == receipts.from_json(
        receipts.to_json([release]))[0].digest()


# ---- L3 adversarial: each defect must be named ----

@pytest.mark.invariant("INV-edition-manifest")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_forged_identity_is_refused():
    m = _manifest()
    forged = dataclasses.replace(m, page_count=m.page_count + 50)  # id not re-derived
    assert any("identity digest" in p for p in edition.verify_facts(forged, _observed(m)))


@pytest.mark.invariant("INV-edition-manifest")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_interior_byte_mismatch_is_refused():
    m = _manifest()
    tampered = dataclasses.replace(_observed(m), interior_sha256="0" * 64)
    assert any("interior digest" in p for p in edition.verify_facts(m, tampered))


@pytest.mark.invariant("INV-edition-manifest")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_page_fact_mismatch_is_refused():
    m = _manifest()
    tampered = dataclasses.replace(_observed(m), interior_pages=m.page_count + 3)
    assert any("page count" in p for p in edition.verify_facts(m, tampered))


@pytest.mark.invariant("INV-edition-manifest")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_manifest_without_receipts_is_not_sellable():
    m = _manifest(receipt_digests=())
    assert any("not release-gated" in p for p in edition.verify_facts(m, _observed(m)))


@pytest.mark.invariant("INV-edition-manifest")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_dirty_tree_manifest_is_not_sellable():
    m = _manifest(tree_clean=False)
    assert any("dirty tree" in p for p in edition.verify_facts(m, _observed(m)))


@pytest.mark.invariant("INV-edition-manifest")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_mutable_looking_reference_is_refused():
    m = _manifest(toolchain_digest="dist/latest.pdf")
    problems = edition.verify_facts(m, _observed(m))
    assert any("mutable path" in p for p in problems)


@pytest.mark.invariant("INV-edition-manifest")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_stale_qualification_is_refused():
    m = _manifest()
    stale = dataclasses.replace(m, qualifications=(
        edition.ProviderQualification("lulu", "PB", "f" * 64, "e" * 64),))
    assert any("stale" in p for p in edition.verify_facts(stale, _observed(stale)))


@pytest.mark.invariant("INV-edition-manifest")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_non_pdf_media_type_is_refused():
    m = _manifest(cover=edition.ArtifactRef("cover", "b" * 64, 90_000, "image/png"))
    m = dataclasses.replace(m, edition_id=edition._identity_digest(m))
    assert any("media type" in p for p in edition.verify_facts(m, _observed(m)))


@pytest.mark.invariant("INV-edition-manifest")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_future_schema_version_is_refused():
    m = _manifest()
    future = dataclasses.replace(m, schema_version=edition.SCHEMA_VERSION + 1)
    future = dataclasses.replace(future, edition_id=edition._identity_digest(future))
    assert any("schema version" in p for p in edition.verify_facts(future, _observed(future)))


# ---- L2 component: build from real artifacts ----

def _write_pdf(path, pages):
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=432, height=648)  # 6x9 in points
    with open(path, "wb") as handle:
        writer.write(handle)


@pytest.mark.layer("integration")
def test_build_from_artifacts_then_verify(scaffolded_book, monkeypatch):
    from press import booklib, receipts

    root = booklib.root()
    slug = booklib.slug()
    (root / "dist").mkdir(exist_ok=True)
    _write_pdf(edition.interior_path(root, slug), 96)
    _write_pdf(edition.cover_path(root, slug), 1)

    # Isolate the edition logic from the press repo's own git state.
    monkeypatch.setattr(receipts, "current_inputs",
                        lambda toolchain_digest="unpinned": (
                            {"invariants": "d"}, "c0ffee", True))
    monkeypatch.setattr(receipts, "pinned_toolchain_digest", lambda: "sha-xyz")
    receipt = receipts.emit("collection", proofs=[])
    manifest = edition.build([receipt], root=root)

    assert manifest.page_count == 96
    assert manifest.edition_id == edition._identity_digest(manifest)
    assert edition.verify(manifest, root) == []

    # Corrupt the interior on disk after the manifest was cut: verify must
    # refuse it (a rebuild after payment is forbidden).
    _write_pdf(edition.interior_path(root, slug), 97)
    assert any("interior digest" in p or "page count" in p
               for p in edition.verify(manifest, root))
