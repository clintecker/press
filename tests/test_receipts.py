"""Trust receipts chain, and the chain verifier refuses a broken chain.

A receipt system that only ever sees valid chains proves nothing. These
tests build a valid chain and prove it verifies, then tamper with,
drop, reorder, and mismatch it and prove each defect is caught.
"""

from __future__ import annotations

import dataclasses

import pytest

from press import receipts


def _receipt(layer, prereqs=None, proofs=("INV-config-slug",), clean=True,
             inputs=None, commit="abc123"):
    return receipts.Receipt(
        schema_version=receipts.SCHEMA_VERSION,
        layer=layer,
        source_commit=commit,
        tree_clean=clean,
        inputs=inputs or {"invariants": "d1", "fixtures": "d2", "scenarios": "d3",
                          "surfaces": "d4", "toolchain": "t1"},
        prerequisites=[r.digest() for r in (prereqs or [])],
        proofs=sorted(proofs),
        artifacts={},
        local_dev=not clean,
    )


def test_valid_chain_verifies():
    collection = _receipt("collection")
    unit = _receipt("unit", prereqs=[collection], proofs=["INV-config-slug", "INV-config-trim"])
    integration = _receipt("integration", prereqs=[unit], proofs=["INV-pdf-ink"])
    assert receipts.verify_chain([collection, unit, integration]) == []


def test_missing_prerequisite_is_caught():
    collection = _receipt("collection")
    unit = _receipt("unit", prereqs=[collection])
    # The chain omits the collection receipt the unit layer depends on.
    problems = receipts.verify_chain([unit])
    assert any("missing or tampered" in p for p in problems), problems


def test_tampered_receipt_is_caught():
    collection = _receipt("collection")
    unit = _receipt("unit", prereqs=[collection])
    # Tamper with the prerequisite after the unit layer recorded its
    # digest: the recorded prerequisite digest no longer resolves.
    tampered = dataclasses.replace(collection, proofs=["INV-config-trim"])
    problems = receipts.verify_chain([tampered, unit])
    assert any("missing or tampered" in p for p in problems), problems


def test_reordered_layers_are_caught():
    collection = _receipt("collection")
    integration = _receipt("integration", prereqs=[collection])
    # integration before unit: out of accumulated-trust order.
    unit = _receipt("unit", prereqs=[collection])
    problems = receipts.verify_chain([collection, integration, unit])
    assert any("out of accumulated-trust order" in p for p in problems), problems


def test_mismatched_inputs_are_caught():
    collection = _receipt("collection")
    # The unit layer ran against a different invariants manifest digest.
    unit = _receipt("unit", prereqs=[collection],
                    inputs={"invariants": "CHANGED", "fixtures": "d2",
                            "scenarios": "d3", "surfaces": "d4", "toolchain": "t1"})
    problems = receipts.verify_chain([collection, unit])
    assert any("input 'invariants' differs" in p for p in problems), problems


def test_release_refuses_dirty_tree_receipt():
    collection = _receipt("collection", clean=False)
    problems = receipts.verify_chain([collection], require_clean=True)
    assert any("dirty tree" in p for p in problems), problems


def test_release_allows_clean_tree_receipt():
    collection = _receipt("collection", clean=True)
    unit = _receipt("unit", prereqs=[collection])
    assert receipts.verify_chain([collection, unit], require_clean=True) == []


def test_receipt_digest_is_deterministic():
    a = _receipt("unit")
    b = _receipt("unit")
    assert a.digest() == b.digest()


def test_round_trips_through_json():
    chain = [_receipt("collection"), _receipt("unit")]
    restored = receipts.from_json(receipts.to_json(chain))
    assert [r.digest() for r in restored] == [r.digest() for r in chain]


def test_emit_marks_dirty_tree_as_local_dev():
    # The real repo tree is usually dirty during a test run; emit records
    # that honestly rather than claiming a clean release receipt.
    receipt = receipts.emit("unit", proofs=["INV-config-slug"])
    assert receipt.local_dev == (not receipt.tree_clean)


def test_unknown_layer_is_refused():
    with pytest.raises(SystemExit, match="unknown trust layer"):
        receipts.emit("not-a-layer", proofs=[])


# ---- release receipt (#97) ----

def test_pinned_toolchain_digest_reads_build_yml():
    from press import receipts
    digest = receipts.pinned_toolchain_digest()
    assert digest.startswith("sha-") or digest == "unpinned"


def test_release_receipt_names_package_and_toolchain(monkeypatch):
    from press import receipts
    monkeypatch.setattr(receipts, "pinned_toolchain_digest", lambda: "sha-abc")
    monkeypatch.setattr(receipts, "current_inputs",
                        lambda toolchain_digest="unpinned": (
                            {"invariants": "d", "fixtures": "d", "scenarios": "d",
                             "surfaces": "d", "toolchain": toolchain_digest},
                            "commit", True))
    chain = [_receipt("collection", clean=True,
                      inputs={"invariants": "d", "fixtures": "d", "scenarios": "d",
                              "surfaces": "d", "toolchain": "sha-abc"}, commit="commit")]
    release = receipts.build_release_receipt("PKGDIGEST", chain)
    assert release.layer == "release"
    assert release.artifacts["package"] == "PKGDIGEST"
    assert release.artifacts["toolchain"] == "sha-abc"


def test_verify_release_accepts_a_matching_clean_chain(monkeypatch):
    from press import receipts
    monkeypatch.setattr(receipts, "pinned_toolchain_digest", lambda: "sha-abc")
    inputs = {"invariants": "d", "fixtures": "d", "scenarios": "d",
              "surfaces": "d", "toolchain": "sha-abc"}
    collection = _receipt("collection", clean=True, inputs=inputs, commit="c")
    release = receipts.Receipt(
        schema_version=receipts.SCHEMA_VERSION, layer="release",
        source_commit="c", tree_clean=True, inputs=inputs,
        prerequisites=[collection.digest()], proofs=[],
        artifacts={"package": "PKG", "toolchain": "sha-abc"})
    assert receipts.verify_release([collection, release], "PKG") == []


def test_verify_release_refuses_a_package_mismatch(monkeypatch):
    from press import receipts
    monkeypatch.setattr(receipts, "pinned_toolchain_digest", lambda: "sha-abc")
    inputs = {"invariants": "d", "fixtures": "d", "scenarios": "d",
              "surfaces": "d", "toolchain": "sha-abc"}
    release = receipts.Receipt(
        schema_version=receipts.SCHEMA_VERSION, layer="release",
        source_commit="c", tree_clean=True, inputs=inputs,
        prerequisites=[], proofs=[],
        artifacts={"package": "PKG", "toolchain": "sha-abc"})
    problems = receipts.verify_release([release], "DIFFERENT")
    assert any("package digest does not match" in p for p in problems)


def test_verify_release_refuses_a_toolchain_mismatch(monkeypatch):
    from press import receipts
    monkeypatch.setattr(receipts, "pinned_toolchain_digest", lambda: "sha-NEW")
    inputs = {"invariants": "d", "fixtures": "d", "scenarios": "d",
              "surfaces": "d", "toolchain": "sha-OLD"}
    release = receipts.Receipt(
        schema_version=receipts.SCHEMA_VERSION, layer="release",
        source_commit="c", tree_clean=True, inputs=inputs,
        prerequisites=[], proofs=[],
        artifacts={"package": "PKG", "toolchain": "sha-OLD"})
    problems = receipts.verify_release([release], "PKG")
    assert any("toolchain does not match" in p for p in problems)


def test_verify_release_refuses_a_dirty_tree():
    from press import receipts
    inputs = {"invariants": "d", "fixtures": "d", "scenarios": "d",
              "surfaces": "d", "toolchain": receipts.pinned_toolchain_digest()}
    release = receipts.Receipt(
        schema_version=receipts.SCHEMA_VERSION, layer="release",
        source_commit="c", tree_clean=False, inputs=inputs,
        prerequisites=[], proofs=[],
        artifacts={"package": "PKG", "toolchain": receipts.pinned_toolchain_digest()},
        local_dev=True)
    problems = receipts.verify_release([release], "PKG")
    assert any("dirty tree" in p for p in problems)
