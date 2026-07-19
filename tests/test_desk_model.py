"""The DESK read model assembles the desk's facts from the registries,
reading only, and reflects artifact evidence states and capability
gating.
"""

from __future__ import annotations

from press import artifact_status, desk_model, doctor
from press.artifact_status import State
from tests import factories


def _report(failing_tools=()):
    findings = tuple(
        doctor.Finding(name=t, category="tool", state="missing",
                       detail="x", required=True)
        for t in failing_tools
    )
    return doctor.DoctorReport(findings)


def test_model_names_the_book(tmp_path):
    handle = factories.minimal().build(tmp_path)
    with handle.use():
        model = desk_model.build_model(handle.root, report=_report())
    assert model.identity.slug == handle.slug
    assert model.identity.title == handle.metadata["title"]
    assert "6 x 9" in model.identity.trim


def test_artifacts_start_absent(tmp_path):
    handle = factories.minimal().build(tmp_path)
    with handle.use():
        model = desk_model.build_model(handle.root, report=_report())
    assert model.artifacts
    assert all(row.state == State.ABSENT for row in model.artifacts)


def test_built_artifact_shows_present_or_verified(tmp_path):
    handle = factories.minimal().build(tmp_path)
    with handle.use():
        (handle.root / "dist").mkdir()
        (handle.root / "dist" / f"{handle.slug}.pdf").write_bytes(b"PDF")
        model = desk_model.build_model(handle.root, report=_report())
    pdf = next(r for r in model.artifacts if r.name == "pdf")
    assert pdf.state == State.PRESENT_UNVERIFIED


def test_verified_evidence_shows_current(tmp_path):
    handle = factories.minimal().build(tmp_path)
    with handle.use():
        dist = handle.root / "dist"
        dist.mkdir()
        (dist / f"{handle.slug}.pdf").write_bytes(b"PDF")
        evidence = artifact_status.record_evidence(dist, handle.slug, ("{slug}.pdf",))
        model = desk_model.build_model(handle.root, evidence=evidence, report=_report())
    pdf = next(r for r in model.artifacts if r.name == "pdf")
    assert pdf.state == State.VERIFIED_CURRENT


def test_missing_toolchain_blocks_build_commands(tmp_path):
    handle = factories.minimal().build(tmp_path)
    with handle.use():
        model = desk_model.build_model(handle.root, report=_report(["lualatex"]))
    assert not model.ready
    assert model.blocked_reason("pdf") == "missing lualatex"
    assert model.blocked_reason("wordcount") is None


def test_ready_machine_blocks_nothing(tmp_path):
    handle = factories.minimal().build(tmp_path)
    with handle.use():
        model = desk_model.build_model(handle.root, report=_report())
    assert model.ready
    assert model.blocked_reason("pdf") is None


def test_commands_come_from_the_catalog(tmp_path):
    from press import catalog

    handle = factories.minimal().build(tmp_path)
    with handle.use():
        model = desk_model.build_model(handle.root, report=_report())
    assert model.commands == catalog.COMMANDS
