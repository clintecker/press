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


# --- the doctor panel row builder (pure) ---------------------------------


def _finding(name, state, category="tool", required=True, detail="why"):
    return doctor.Finding(name=name, category=category, state=state,
                          detail=detail, required=required)


def test_doctor_rows_project_every_finding_in_order():
    report = doctor.DoctorReport((
        _finding("pandoc", "ok"),
        _finding("epubcheck", "absent", required=False),
        _finding("lualatex", "missing"),
        _finding("python", "warn", category="python", required=False),
        _finding("python-deps", "ok", category="deps"),
    ))
    rows = desk_model.doctor_rows(report)
    assert [r.name for r in rows] == [
        "pandoc", "epubcheck", "lualatex", "python", "python-deps",
    ]
    assert rows[0].glyph == "*" and rows[0].state_word == "ok"
    assert rows[2].glyph == "!" and rows[2].state_word == "missing"
    assert rows[0].required is True and rows[1].required is False
    assert rows[0].purpose == "why"


def test_doctor_rows_glyph_covers_every_state():
    for state, (glyph, word) in desk_model.DOCTOR_STATE_GLYPH.items():
        rows = desk_model.doctor_rows(doctor.DoctorReport((_finding("t", state),)))
        assert rows[0].glyph == glyph
        assert rows[0].state_word == word


def test_doctor_rows_unknown_state_falls_back_to_a_query_glyph():
    rows = desk_model.doctor_rows(doctor.DoctorReport((_finding("t", "weird"),)))
    assert rows[0].glyph == "?" and rows[0].state_word == "weird"


# --- the build-log progress parser (pure) --------------------------------


def test_progress_event_reads_a_tool_invocation():
    event = desk_model.progress_event("+ pandoc --to pdf source.md")
    assert event is not None
    assert event.kind is desk_model.ProgressKind.INVOCATION
    assert event.detail == "pandoc --to pdf source.md"
    assert event.seconds is None


def test_progress_event_reads_a_completed_phase():
    event = desk_model.progress_event("  ¶ typeset    ✓ PDF · EPUB · web")
    assert event is not None
    assert event.kind is desk_model.ProgressKind.PHASE
    assert event.detail == "typeset"


def test_progress_event_ignores_a_pilcrow_that_is_not_a_known_phase():
    assert desk_model.progress_event("  ¶ frobnicate  ✓ nope") is None


def test_progress_event_parses_a_phase_wrapped_in_ansi_colour():
    coloured = "  \x1b[38;5;203m¶\x1b[0m verify     \x1b[38;5;108m✓ ok\x1b[0m"
    event = desk_model.progress_event(coloured)
    assert event is not None
    assert event.kind is desk_model.ProgressKind.PHASE
    assert event.detail == "verify"


def test_progress_event_reads_a_command_timing():
    event = desk_model.progress_event("  pandoc took 3.4s")
    assert event is not None
    assert event.kind is desk_model.ProgressKind.TIMING
    assert event.detail == "pandoc"
    assert event.seconds == 3.4


def test_progress_event_returns_none_for_ordinary_prose():
    assert desk_model.progress_event("just building the book now") is None


# --- the run progress accumulator (pure) ---------------------------------


def test_run_progress_folds_invocations_and_phases():
    progress = desk_model.RunProgress()
    lines = [
        "+ pandoc a.md",
        "  pandoc took 2.0s",
        "  ¶ check      ✓ style",
        "+ pandoc b.md",
        "  ¶ typeset    ✓ PDF",
        "  ¶ verify     ✓ match",
    ]
    moved = [progress.observe(desk_model.progress_event(line)) for line in lines]
    # Two invocations and three phase completions moved the display; the
    # timing line did not.
    assert moved == [True, False, True, True, True, True]
    assert progress.invocations == 2
    assert progress.phases_done == ("check", "typeset", "verify")
    assert progress.fraction == 1.0


def test_run_progress_ignores_none_and_repeated_phases():
    progress = desk_model.RunProgress()
    assert progress.observe(None) is False
    assert progress.observe(desk_model.progress_event("  ¶ check ✓ x")) is True
    # The same phase a second time does not advance.
    assert progress.observe(desk_model.progress_event("  ¶ check ✓ x")) is False
    assert progress.phases_done == ("check",)
    assert progress.fraction == 1 / 3


def test_run_progress_status_line_shows_ticks_dots_and_step_count():
    progress = desk_model.RunProgress()
    assert progress.status_line() == "· check · typeset · verify    0 steps"
    progress.observe(desk_model.progress_event("+ pandoc a.md"))
    progress.observe(desk_model.progress_event("  ¶ check ✓ x"))
    line = progress.status_line()
    assert "✓ check" in line
    assert "· typeset" in line
    assert "1 steps" in line
