"""Typed doctor findings: ``examine`` returns immutable data, ``main`` is a
renderer over it.

These prove issue #103's seam. Every probe is injected -- a fixed PATH, a
scripted ``--version`` verdict, a pinned interpreter version, a canned
dependency result -- so no test touches a real executable, sleeps on a
timeout, or mutates PATH. The differential test proves the CLI's exact
text and exit code derive solely from the report.
"""

from __future__ import annotations

import dataclasses

import pytest

from press import adapters, doctor
from press.adapters import fakes
from press.adapters.protocols import ProcessResult

ALL_TOOLS = [name for name, _purpose, _required in doctor.CHECKS]


def _run(**kwargs) -> doctor.DoctorReport:
    """Examine with all real Python deps reported present unless overridden,
    so a test isolates the facet it cares about."""

    kwargs.setdefault("deps_probe", lambda: None)
    return doctor.examine(**kwargs)


def _by_name(report: doctor.DoctorReport) -> dict[str, doctor.Finding]:
    return {f.name: f for f in report.findings}


# --------------------------------------------------------------------------
# examine returns pure data
# --------------------------------------------------------------------------


@pytest.mark.layer("unit")
def test_examine_returns_report_without_printing(capsys):
    env = fakes.FakeEnvironment(present_tools=ALL_TOOLS)
    report = _run(environment=env, runs=lambda tool: True, python_version=(3, 11))
    assert isinstance(report, doctor.DoctorReport)
    assert isinstance(report.findings, tuple)
    assert capsys.readouterr().out == ""


@pytest.mark.layer("unit")
def test_findings_are_immutable():
    finding = doctor.Finding("pandoc", "tool", "ok", "every build target", True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        finding.state = "broken"  # type: ignore[misc]


@pytest.mark.layer("unit")
def test_examine_probes_path_through_injected_environment():
    """Every tool is resolved through the environment boundary, never a
    raw PATH lookup."""

    env = fakes.FakeEnvironment(present_tools=ALL_TOOLS)
    _run(environment=env, runs=lambda tool: True, python_version=(3, 11))
    assert env.which_calls == ALL_TOOLS


# --------------------------------------------------------------------------
# required / optional / missing / broken stay distinct
# --------------------------------------------------------------------------


@pytest.mark.layer("unit")
def test_required_tool_missing_denies_machine():
    present = [t for t in ALL_TOOLS if t != "pandoc"]
    env = fakes.FakeEnvironment(present_tools=present)
    report = _run(environment=env, runs=lambda tool: True, python_version=(3, 11))
    pandoc = _by_name(report)["pandoc"]
    assert (pandoc.state, pandoc.required, pandoc.category) == ("missing", True, "tool")
    assert "pandoc" in report.failing
    assert report.ready is False
    assert report.exit_code == 1


@pytest.mark.layer("unit")
def test_optional_tool_absent_does_not_deny_machine():
    present = [t for t in ALL_TOOLS if t != "epubcheck"]
    env = fakes.FakeEnvironment(present_tools=present)
    report = _run(environment=env, runs=lambda tool: True, python_version=(3, 11))
    epubcheck = _by_name(report)["epubcheck"]
    assert (epubcheck.state, epubcheck.required) == ("absent", False)
    assert "epubcheck" not in report.failing
    assert report.ready is True
    assert report.exit_code == 0


@pytest.mark.layer("unit")
def test_broken_required_tool_denies_machine():
    env = fakes.FakeEnvironment(present_tools=ALL_TOOLS)
    report = _run(
        environment=env,
        runs=lambda tool: tool != "lualatex",
        python_version=(3, 11),
    )
    lualatex = _by_name(report)["lualatex"]
    assert lualatex.state == "broken"
    assert lualatex.detail == "present but cannot execute; PDF and print builds"
    assert "lualatex" in report.failing
    assert report.exit_code == 1


@pytest.mark.layer("unit")
def test_broken_optional_tool_still_denies_machine():
    """A present-but-unrunnable binary is a machine fault even when the
    tool is optional -- preserving doctor's historical verdict."""

    env = fakes.FakeEnvironment(present_tools=ALL_TOOLS)
    report = _run(
        environment=env,
        runs=lambda tool: tool != "claude",
        python_version=(3, 11),
    )
    claude = _by_name(report)["claude"]
    assert (claude.state, claude.required) == ("broken", False)
    assert "claude" in report.failing
    assert report.exit_code == 1


# --------------------------------------------------------------------------
# environment keys
# --------------------------------------------------------------------------


@pytest.mark.layer("unit")
def test_environment_keys_report_but_never_deny():
    env = fakes.FakeEnvironment(
        values={"OPENAI_API_KEY": "sk-live"}, present_tools=ALL_TOOLS
    )
    report = _run(environment=env, runs=lambda tool: True, python_version=(3, 11))
    by_name = _by_name(report)
    assert by_name["OPENAI_API_KEY"].state == "ok"
    assert by_name["GEMINI_API_KEY"].state == "unset"
    assert by_name["OPENAI_API_KEY"].category == "key"
    assert report.failing == ()
    assert report.exit_code == 0


# --------------------------------------------------------------------------
# python version and dependency probes
# --------------------------------------------------------------------------


@pytest.mark.layer("unit")
@pytest.mark.parametrize("version", [(3, 9), (3, 14)])
def test_python_outside_range_warns_without_denying(version):
    env = fakes.FakeEnvironment(present_tools=ALL_TOOLS)
    report = _run(environment=env, runs=lambda tool: True, python_version=version)
    python = _by_name(report)["python"]
    assert python.state == "warn"
    assert "outside the tested range" in python.detail
    assert "python" not in report.failing
    assert report.exit_code == 0


@pytest.mark.layer("unit")
def test_python_deps_failure_denies_machine():
    env = fakes.FakeEnvironment(present_tools=ALL_TOOLS)
    report = doctor.examine(
        environment=env,
        runs=lambda tool: True,
        python_version=(3, 11),
        deps_probe=lambda: "No module named 'pypdf'",
    )
    deps = _by_name(report)["python-deps"]
    assert (deps.state, deps.category, deps.required) == ("missing", "deps", True)
    assert deps.detail == "No module named 'pypdf'"
    # The roll-call uses the identity "python-deps", not the "python" label.
    assert "python-deps" in report.failing
    assert report.exit_code == 1


@pytest.mark.layer("unit")
def test_fully_capable_machine_is_ready():
    env = fakes.FakeEnvironment(
        values={"OPENAI_API_KEY": "a", "GEMINI_API_KEY": "b"},
        present_tools=ALL_TOOLS,
    )
    report = doctor.examine(
        environment=env,
        runs=lambda tool: True,
        python_version=(3, 11),
        deps_probe=lambda: None,
    )
    assert report.failing == ()
    assert report.ready is True
    assert report.exit_code == 0
    # One finding per tool, key, plus python version and python deps.
    assert len(report.findings) == len(doctor.CHECKS) + len(doctor.KEYS) + 2


# --------------------------------------------------------------------------
# tool_runs routes through the process adapter
# --------------------------------------------------------------------------


@pytest.mark.layer("unit")
def test_tool_runs_uses_process_adapter(monkeypatch):
    fake = fakes.FakeProcessRunner(by_command={"pandoc": ProcessResult(0)})
    monkeypatch.setattr(adapters, "process_runner", fake)
    assert doctor.tool_runs("pandoc") is True
    assert fake.runs[0].argv == ("pandoc", "--version")


@pytest.mark.layer("unit")
def test_tool_runs_false_on_missing_binary(monkeypatch):
    fake = fakes.FakeProcessRunner(by_command={"ghost": OSError("nope")})
    monkeypatch.setattr(adapters, "process_runner", fake)
    assert doctor.tool_runs("ghost") is False


# --------------------------------------------------------------------------
# rendering: main prints exactly what the findings say
# --------------------------------------------------------------------------


@pytest.mark.layer("unit")
def test_render_finding_lines_match_legacy_gutter():
    ok = doctor.Finding("git", "tool", "ok", "scaffolding identity", True)
    assert doctor.render_finding(ok) == "  [     ok] git        scaffolding identity"
    missing = doctor.Finding("pandoc", "tool", "missing", "every build target", True)
    assert doctor.render_finding(missing) == (
        "  [MISSING] pandoc     every build target"
    )
    broken = doctor.Finding(
        "lualatex", "tool", "broken", "present but cannot execute; PDF builds", True
    )
    assert doctor.render_finding(broken) == (
        "  [ BROKEN] lualatex   present but cannot execute; PDF builds"
    )
    key = doctor.Finding("OPENAI_API_KEY", "key", "unset", "art commission", False)
    assert doctor.render_finding(key) == (
        "  [  unset] OPENAI_API_KEY   art commission"
    )
    deps = doctor.Finding("python-deps", "deps", "ok", "libs importable", True)
    assert doctor.render_finding(deps) == "  [     ok] python     libs importable"


def _render_expected(report: doctor.DoctorReport) -> str:
    lines = ["press doctor"]
    lines += [doctor.render_finding(f) for f in report.findings]
    if report.failing:
        lines.append("")
        lines.append(
            f"not ready: {', '.join(report.failing)} {doctor._NOT_READY_HINT}"
        )
    else:
        lines.append("")
        lines.append("this machine can make books")
    return "\n".join(lines) + "\n"


@pytest.mark.layer("unit")
@pytest.mark.parametrize(
    "present, runs_ok, deps, expect_code",
    [
        (ALL_TOOLS, True, None, 0),
        ([t for t in ALL_TOOLS if t != "pandoc"], True, None, 1),
        (ALL_TOOLS, False, None, 1),
        (ALL_TOOLS, True, "No module named 'yaml'", 1),
    ],
)
def test_main_renders_examine_report_exactly(
    monkeypatch, capsys, present, runs_ok, deps, expect_code
):
    """main() prints exactly render_finding over examine()'s findings, plus
    the roll-call, and returns exactly report.exit_code -- the differential
    that pins CLI text and exit to the typed report."""

    env = fakes.FakeEnvironment(
        values={"OPENAI_API_KEY": "x"}, present_tools=present
    )
    real_examine = doctor.examine

    def scripted_examine(**_kwargs) -> doctor.DoctorReport:
        return real_examine(
            environment=env,
            runs=lambda tool: runs_ok,
            python_version=(3, 11),
            deps_probe=lambda: deps,
        )

    # Both the reference report and main() must see the same probes.
    report = scripted_examine()
    monkeypatch.setattr(doctor, "examine", scripted_examine)

    code = doctor.main()
    out = capsys.readouterr().out

    assert code == expect_code
    assert code == report.exit_code
    assert out == _render_expected(report)
