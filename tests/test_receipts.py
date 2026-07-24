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
    import re

    from press import receipts
    digest = receipts.pinned_toolchain_digest()
    # The immutable identity is the @sha256 digest, not the mutable sha- tag.
    assert digest == "unpinned" or re.fullmatch(r"sha256:[0-9a-f]{64}", digest)


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


def _full_chain(inputs, commit="c", clean=True, package="PKG"):
    """A complete trust chain: every pre-release layer, each extending the
    one before, terminated by a release receipt that extends them all."""

    chain = []
    for layer in receipts.LAYERS[:-1]:
        chain.append(_receipt(layer, prereqs=chain[-1:], proofs=[],
                              clean=clean, inputs=inputs, commit=commit))
    release = receipts.Receipt(
        schema_version=receipts.SCHEMA_VERSION, layer="release",
        source_commit=commit, tree_clean=clean, inputs=inputs,
        prerequisites=[r.digest() for r in chain], proofs=[],
        artifacts={"package": package, "toolchain": inputs["toolchain"]},
        local_dev=not clean)
    chain.append(release)
    return chain


def test_verify_release_accepts_a_complete_clean_chain(monkeypatch):
    from press import receipts
    monkeypatch.setattr(receipts, "pinned_toolchain_digest", lambda: "sha-abc")
    inputs = {"invariants": "d", "fixtures": "d", "scenarios": "d",
              "surfaces": "d", "toolchain": "sha-abc"}
    assert receipts.verify_release(_full_chain(inputs), "PKG") == []


def test_verify_release_refuses_a_two_layer_placeholder(monkeypatch):
    # The old thinness: a collection receipt standing in for every layer.
    # Completeness must refuse it now.
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
    problems = receipts.verify_release([collection, release], "PKG")
    assert any("incomplete release chain" in p for p in problems)


def test_completeness_names_a_missing_middle_layer():
    from press import receipts
    inputs = {"invariants": "d", "fixtures": "d", "scenarios": "d",
              "surfaces": "d", "toolchain": "t"}
    chain = _full_chain(inputs)
    without_scenario = [r for r in chain if r.layer != "scenario"]
    problems = receipts.verify_complete(without_scenario)
    assert any("scenario" in p and "missing" in p for p in problems)


def test_completeness_catches_a_broken_extend_link():
    from press import receipts
    inputs = {"invariants": "d", "fixtures": "d", "scenarios": "d",
              "surfaces": "d", "toolchain": "t"}
    chain = _full_chain(inputs)
    # Sever the graph layer's link to its predecessor (component).
    idx = next(i for i, r in enumerate(chain) if r.layer == "graph")
    chain[idx] = dataclasses.replace(chain[idx], prerequisites=[])
    problems = receipts.verify_complete(chain)
    assert any("graph" in p and "prerequisite link broken" in p for p in problems)


def test_build_full_chain_is_complete():
    from press import receipts
    chain = receipts.build_full_chain("PKG", receipts.pinned_toolchain_digest())
    assert [r.layer for r in chain] == receipts.LAYERS
    assert receipts.verify_complete(chain) == []


# ---- per-job release assembly (#150) ----

def _clean_ci(monkeypatch, commit="c"):
    from press import receipts
    monkeypatch.setattr(receipts, "pinned_toolchain_digest", lambda: "sha-abc")
    inputs = {"invariants": "d", "fixtures": "d", "scenarios": "d",
              "surfaces": "d", "toolchain": "sha-abc"}
    monkeypatch.setattr(receipts, "current_inputs",
                        lambda toolchain_digest="unpinned": (inputs, commit, True))
    return inputs


def _tiers(inputs, tiers=("quality", "integration"), commit="c"):
    return [_receipt(t, clean=True, inputs=inputs, commit=commit, proofs=[]) for t in tiers]


def test_ci_release_holds_when_every_tier_is_present(monkeypatch):
    from press import receipts
    inputs = _clean_ci(monkeypatch)
    chain = receipts.assemble_release(_tiers(inputs), "PKG")
    assert receipts.verify_ci_release(chain, "PKG") == []


def test_ci_release_fails_closed_when_a_job_did_not_run(monkeypatch):
    from press import receipts
    inputs = _clean_ci(monkeypatch)
    chain = receipts.assemble_release(_tiers(inputs, tiers=("quality",)), "PKG")
    assert any("missing tier receipt 'integration'" in p
               for p in receipts.verify_ci_release(chain, "PKG"))


def test_ci_release_fails_when_a_receipt_is_from_another_commit(monkeypatch):
    from press import receipts
    inputs = _clean_ci(monkeypatch)
    tiers = _tiers(inputs)
    tiers[1] = _receipt("integration", clean=True, inputs=inputs, commit="OTHER", proofs=[])
    chain = receipts.assemble_release(tiers, "PKG")
    assert any("disagree on source commit" in p
               for p in receipts.verify_ci_release(chain, "PKG"))


def test_ci_release_fails_on_a_package_mismatch(monkeypatch):
    from press import receipts
    inputs = _clean_ci(monkeypatch)
    chain = receipts.assemble_release(_tiers(inputs), "PKG")
    assert any("package does not match" in p
               for p in receipts.verify_ci_release(chain, "DIFFERENT"))


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


# ---- receipt command surface ----

def test_receipt_cli_refuses_an_unknown_or_incomplete_command(capsys):
    assert receipts.main([]) == 2
    assert receipts.main(["unknown"]) == 2
    output = capsys.readouterr().out
    assert "python3 -m press.receipts emit" in output
    assert "verify-release" in output


def test_receipt_cli_verifies_a_chain_and_names_a_broken_one(tmp_path, capsys):
    collection = _receipt("collection")
    good_path = tmp_path / "good.json"
    good_path.write_text(receipts.to_json([collection]), encoding="utf-8")
    assert receipts.main(["verify", str(good_path)]) == 0
    assert "receipt chain holds" in capsys.readouterr().out

    unit = _receipt("unit", prereqs=[collection])
    broken_path = tmp_path / "broken.json"
    broken_path.write_text(receipts.to_json([unit]), encoding="utf-8")
    assert receipts.main(["verify", str(broken_path)]) == 1
    output = capsys.readouterr().out
    assert "does not hold" in output
    assert "missing or tampered" in output
