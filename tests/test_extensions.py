"""The extension contract, proven. The reference third-party manifest
conforms; every hostile manifest is refused with a located reason; version
negotiation and collision detection read the live core names, so they can
never drift from what actually ships.
"""

from __future__ import annotations

import pytest

from press import extensions


@pytest.mark.layer("unit")
def test_reference_manifest_conforms():
    manifest = extensions.load_manifest_file(
        extensions.fixtures_dir() / "reference.yaml"
    )
    assert extensions.conformance(manifest) == []
    assert extensions.conforms(manifest)


@pytest.mark.layer("unit")
@pytest.mark.invariant("INV-extension-conformance")
@pytest.mark.proof("negative")
def test_collision_with_core_name_is_refused():
    manifest = extensions.load_manifest_file(
        extensions.fixtures_dir() / "hostile" / "collision.yaml"
    )
    problems = extensions.conformance(manifest)
    assert any("pdf" in p and "collides" in p for p in problems)


@pytest.mark.layer("unit")
@pytest.mark.invariant("INV-extension-conformance")
@pytest.mark.proof("negative")
def test_unsupported_contract_major_is_refused():
    manifest = extensions.load_manifest_file(
        extensions.fixtures_dir() / "hostile" / "version.yaml"
    )
    problems = extensions.conformance(manifest)
    assert any("contract major 99" in p for p in problems)


@pytest.mark.layer("unit")
@pytest.mark.invariant("INV-extension-seal")
@pytest.mark.proof("negative")
def test_sealed_capability_claim_is_refused():
    manifest = extensions.load_manifest_file(
        extensions.fixtures_dir() / "hostile" / "sealed.yaml"
    )
    problems = extensions.conformance(manifest)
    assert any("sealed capability" in p and "core-verification" in p for p in problems)


@pytest.mark.layer("unit")
@pytest.mark.invariant("INV-extension-seal")
@pytest.mark.proof("negative")
def test_unproven_invariant_is_refused():
    manifest = extensions.load_manifest_file(
        extensions.fixtures_dir() / "hostile" / "unproven.yaml"
    )
    problems = extensions.conformance(manifest)
    assert any("names no proof" in p for p in problems)


@pytest.mark.layer("unit")
@pytest.mark.invariant("INV-extension-conformance")
@pytest.mark.proof("negative")
def test_malformed_manifest_is_refused_at_the_parser():
    with pytest.raises(SystemExit):
        extensions.load_manifest_file(
            extensions.fixtures_dir() / "hostile" / "malformed.yaml"
        )


@pytest.mark.layer("unit")
def test_non_mapping_manifest_is_refused():
    with pytest.raises(SystemExit):
        extensions.load_manifest(["not", "a", "mapping"])  # type: ignore[arg-type]


@pytest.mark.layer("unit")
def test_missing_required_key_is_refused():
    with pytest.raises(SystemExit):
        extensions.load_manifest({"name": "x", "kind": "artifact"})  # no contract-major


@pytest.mark.layer("unit")
def test_list_valued_key_must_be_strings():
    with pytest.raises(SystemExit):
        extensions.load_manifest(
            {"name": "x", "kind": "artifact", "contract-major": 2, "provides": [1, 2]}
        )


@pytest.mark.layer("unit")
def test_publication_must_be_a_known_string():
    manifest = extensions.load_manifest(
        {"name": "x", "kind": "artifact", "contract-major": 2,
         "provides": ["x"], "publication": "semi-public"}
    )
    assert any("publication" in p for p in extensions.conformance(manifest))


@pytest.mark.layer("unit")
def test_unknown_dependency_is_refused():
    manifest = extensions.Manifest(
        name="needs-a-ghost",
        kind="artifact",
        contract_major=2,
        provides=("needs-a-ghost",),
        requires=("no-such-thing",),
    )
    problems = extensions.conformance(manifest)
    assert any("no-such-thing" in p for p in problems)


@pytest.mark.layer("unit")
def test_self_provided_dependency_resolves():
    # A dependency the manifest itself provides is knowable, so it conforms.
    manifest = extensions.Manifest(
        name="two-part",
        kind="artifact",
        contract_major=2,
        provides=("part-a", "part-b"),
        requires=("part-a",),
    )
    assert extensions.conformance(manifest) == []


@pytest.mark.layer("unit")
def test_collision_reads_live_core_names():
    # Every registered artifact and command is reserved; picking any one as a
    # provided name must collide. This proves the reserved set is the live
    # registry, not a hand-maintained list that could drift.
    from press import catalog, registry

    for reserved in (next(iter(registry.ARTIFACTS)), catalog.COMMANDS[0].name):
        manifest = extensions.Manifest(
            name="squatter",
            kind="artifact",
            contract_major=2,
            provides=(reserved,),
        )
        assert not extensions.conforms(manifest)


@pytest.mark.layer("unit")
def test_unknown_kind_is_refused():
    manifest = extensions.Manifest(
        name="what-am-i",
        kind="interpretive-dance",
        contract_major=2,
    )
    problems = extensions.conformance(manifest)
    assert any("not an extensible surface" in p for p in problems)


@pytest.mark.layer("unit")
def test_every_hostile_fixture_is_refused():
    # The whole adversary set, so a newly added hostile fixture is covered
    # without editing this test: each must be refused (malformed by the
    # parser, the rest by conformance).
    hostile = sorted((extensions.fixtures_dir() / "hostile").glob("*.yaml"))
    assert hostile, "no hostile fixtures found"
    for path in hostile:
        if path.name == "malformed.yaml":
            with pytest.raises(SystemExit):
                extensions.load_manifest_file(path)
        else:
            manifest = extensions.load_manifest_file(path)
            assert not extensions.conforms(manifest), path.name
