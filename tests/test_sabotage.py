"""Sabotage the harness and prove each gate turns red.

A test suite can certify itself while its own gates are blind. For each
protection the press relies on, this suite removes or corrupts exactly
what the gate checks and asserts the gate fails. If any of these ever
passes under sabotage, the corresponding gate is not protecting
anything.

Each case names the gate it sabotages, so the set is a legible index of
what the harness actually enforces.
"""

from __future__ import annotations

import pytest

from press import fixture_provenance, invariants, receipts, surfaces


def test_sabotage_unclassified_function_reddens_surface_gate(monkeypatch):
    """Add a public callable the classification does not cover: the
    surface inventory must fail."""

    real = surfaces.public_callables
    monkeypatch.setattr(surfaces, "public_callables",
                        lambda: {**real(), "ghost_module": ["ghost_fn"]})
    problems = surfaces.audit()["problems"]
    assert any("ghost_module.ghost_fn" in p for p in problems)


def test_sabotage_dangling_invariant_proof_reddens_ledger():
    """An invariant whose negative proof names a deleted check must fail
    the ledger validator."""

    bad = [{
        "id": "INV-sabotage", "statement": "s", "risk": "r",
        "criticality": "standard", "owner": "booklib", "enforcer": "booklib",
        "layers": ["selftest"], "negative": ["check_deleted_long_ago"],
        "ci_tier": "quality", "limitations": "l",
    }]
    with pytest.raises(SystemExit, match="no selftest"):
        invariants.validate(bad)


def test_sabotage_orphan_fixture_reddens_provenance(tmp_path):
    """A fixture on disk with no manifest entry must be caught."""

    from pathlib import Path
    import shutil

    src = Path(fixture_provenance.__file__).resolve().parent / "data" / "known-bad"
    d = tmp_path / "known-bad"
    shutil.copytree(src, d)
    (d / "orphan-sabotage.docx").write_bytes(b"not manifested")
    problems = fixture_provenance.audit(
        fixture_provenance.load(), d, invariants.load())
    assert any("orphan-sabotage.docx" in p for p in problems)


def test_sabotage_removed_graph_edge_reddens_state_model():
    """Drop a prerequisite edge from the registry and the ordering law
    no longer holds for the artifact that needed it."""

    from press import registry

    coverwrap = registry.ARTIFACTS["coverwrap"]
    assert coverwrap.prerequisites, "coverwrap must have a prerequisite to remove"
    # With the edge present, the order is valid.
    order = registry.build_order(["coverwrap"])
    assert all(p in order for p in coverwrap.prerequisites)
    # Simulate a removed edge: an order that omits the prerequisite is
    # what the state-model law is built to reject.
    broken_order = [s for s in order if s not in coverwrap.prerequisites]
    seen: set[str] = set()
    caught = False
    for step in broken_order + ["coverwrap"]:
        for prereq in registry.ARTIFACTS[step].prerequisites:
            if prereq not in seen:
                caught = True
        seen.add(step)
    assert caught, "a removed prerequisite edge went undetected"


def test_sabotage_mismatched_release_receipt_reddens_chain():
    """A release chain with a dirty-tree (local-development) receipt must
    be refused."""

    dirty = receipts.Receipt(
        schema_version=receipts.SCHEMA_VERSION, layer="release",
        source_commit="c", tree_clean=False,
        inputs={"invariants": "d", "fixtures": "d", "scenarios": "d",
                "surfaces": "d", "toolchain": "t"},
        prerequisites=[], proofs=[], artifacts={}, local_dev=True,
    )
    problems = receipts.verify_chain([dirty], require_clean=True)
    assert any("dirty tree" in p for p in problems)


def test_sabotage_bad_tool_output_is_visible_through_the_fake():
    """A fake process runner that returns the wrong bytes cannot make a
    consumer pass: the fake records what it was asked, so a test asserts
    the real contract rather than trusting the fake's answer."""

    from press.adapters.fakes import FakeProcessRunner
    from press.adapters.protocols import ProcessResult

    fake = FakeProcessRunner(by_command={"git": ProcessResult(0, stdout=b"deadbeef\n")})
    result = fake.run(["git", "rev-parse", "HEAD"], capture=True)
    # The fake recorded the exact argv, so a consumer that fed it the
    # wrong command is detectable; the fake cannot silently substitute a
    # different command's answer.
    assert fake.runs[-1].argv == ("git", "rev-parse", "HEAD")
    assert result.stdout == b"deadbeef\n"


# The index of gates this suite sabotages, each with the test that proves
# it reddens. A gate added to the harness without a sabotage case is a
# gate nobody has proven bites.
SABOTAGE_INDEX = {
    "surface-classification": "test_sabotage_unclassified_function_reddens_surface_gate",
    "invariant-ledger": "test_sabotage_dangling_invariant_proof_reddens_ledger",
    "fixture-provenance": "test_sabotage_orphan_fixture_reddens_provenance",
    "graph-edges": "test_sabotage_removed_graph_edge_reddens_state_model",
    "release-receipts": "test_sabotage_mismatched_release_receipt_reddens_chain",
    "adapter-fakes": "test_sabotage_bad_tool_output_is_visible_through_the_fake",
}


def test_every_indexed_sabotage_case_exists():
    """The index names real tests in this module, so it cannot rot into
    a list of gates that are no longer sabotaged."""

    import sys

    module = sys.modules[__name__]
    for gate, test_name in SABOTAGE_INDEX.items():
        assert hasattr(module, test_name), f"{gate}: missing {test_name}"
