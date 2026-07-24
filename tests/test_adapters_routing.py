"""Proof that the migrated call sites truly go through the adapters.

The boundary gate proves the migrated modules hold no direct
subprocess/env/HTTP call; these tests prove the other half -- that each
site actually drives the injected adapter, with the exact argv, cwd, env
slice, and request it always did. Swapping in a fake is enough to observe
the call, with no live process, credential, or socket.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from press import adapters
from press.adapters import fakes, production
from press.adapters.protocols import ProcessResult


@pytest.fixture
def fake_runner(monkeypatch):
    fake = fakes.FakeProcessRunner()
    monkeypatch.setattr(adapters, "process_runner", fake)
    return fake


@pytest.fixture
def fake_env(monkeypatch):
    def _install(**kwargs):
        fake = fakes.FakeEnvironment(**kwargs)
        monkeypatch.setattr(adapters, "environment", fake)
        return fake

    return _install


@pytest.fixture
def fake_http(monkeypatch):
    def _install(responses):
        fake = fakes.FakeImageClient(responses=responses)
        monkeypatch.setattr(adapters, "image_client", fake)
        return fake

    return _install


# --------------------------------------------------------------------------
# build.run
# --------------------------------------------------------------------------


def test_build_run_drives_runner_with_book_env(scaffolded_book, fake_runner):
    from press import build

    build.run(["pandoc", "--version"])
    assert len(fake_runner.runs) == 1
    recorded = fake_runner.runs[0]
    assert recorded.argv == ("pandoc", "--version")
    assert recorded.cwd == str(scaffolded_book)
    assert recorded.check is True
    # the deterministic build environment the press has always injected
    assert recorded.env is not None
    assert recorded.env["SOURCE_DATE_EPOCH"] == "1784160000"
    assert recorded.env["BOOK_ROOT"] == str(scaffolded_book)
    assert "BOOK_PUBLISHER" in recorded.env


def test_build_run_propagates_calledprocesserror(scaffolded_book, monkeypatch):
    from press import build

    fake = fakes.FakeProcessRunner(
        results=[subprocess.CalledProcessError(1, ["pandoc"])]
    )
    monkeypatch.setattr(adapters, "process_runner", fake)
    with pytest.raises(subprocess.CalledProcessError):
        build.run(["pandoc"])


# --------------------------------------------------------------------------
# package_source.tracked_paths
# --------------------------------------------------------------------------


def test_tracked_paths_parses_git_ls_files(tmp_path, fake_runner):
    from press import package_source

    fake_runner._by_command["git"] = ProcessResult(0, b"a.md\0config/x.yaml\0")
    tracked = package_source.tracked_paths(tmp_path)
    assert tracked == {"a.md", "config/x.yaml"}
    assert fake_runner.runs[0].argv == ("git", "-C", str(tmp_path), "ls-files", "-z")
    assert fake_runner.runs[0].capture is True


def test_tracked_paths_returns_none_when_git_fails(tmp_path, monkeypatch):
    from press import package_source

    fake = fakes.FakeProcessRunner(
        by_command={"git": subprocess.CalledProcessError(128, "git")}
    )
    monkeypatch.setattr(adapters, "process_runner", fake)
    assert package_source.tracked_paths(tmp_path) is None


# --------------------------------------------------------------------------
# doctor.tool_runs
# --------------------------------------------------------------------------


def test_tool_runs_true_when_version_exits_zero(fake_runner):
    from press import doctor

    fake_runner._by_command["pandoc"] = ProcessResult(0)
    assert doctor.tool_runs("pandoc") is True
    assert fake_runner.runs[0].argv == ("pandoc", "--version")
    assert fake_runner.runs[0].capture is True


def test_tool_runs_false_when_binary_missing(monkeypatch):
    from press import doctor

    fake = fakes.FakeProcessRunner(by_command={"ghost": OSError("no such tool")})
    monkeypatch.setattr(adapters, "process_runner", fake)
    assert doctor.tool_runs("ghost") is False


# --------------------------------------------------------------------------
# art_commission.key_for + post_json
# --------------------------------------------------------------------------


def test_key_for_reads_credential_through_environment(fake_env):
    from press import art_commission

    fake_env(values={"OPENAI_API_KEY": "sk-live"})
    assert art_commission.key_for("openai") == "sk-live"


def test_key_for_refuses_when_unset(fake_env):
    from press import art_commission

    fake_env(values={})
    with pytest.raises(SystemExit) as excinfo:
        art_commission.key_for("gemini")
    assert "GEMINI_API_KEY" in str(excinfo.value)


def test_post_json_routes_through_http_client(fake_http):
    from press import art_commission

    client = fake_http([{"data": [{"b64_json": "AAA="}]}])
    body = art_commission.post_json(
        "https://api.openai.com/v1/images/generations",
        {"prompt": "x"},
        {"Authorization": "Bearer y"},
    )
    assert body["data"][0]["b64_json"] == "AAA="
    assert client.requests[0].kind == "json"


def test_post_json_translates_http_error_to_systemexit(fake_http):
    from press import art_commission

    fake_http([production.HttpError("api.openai.com", 401, "unauthorized")])
    with pytest.raises(SystemExit) as excinfo:
        art_commission.post_json("https://api.openai.com/v1/images/generations", {}, {})
    message = str(excinfo.value)
    assert "api.openai.com refused (401)" in message
    assert "unauthorized" in message


# --------------------------------------------------------------------------
# operator.run_workflow reaches for the claude CLI through the environment
# --------------------------------------------------------------------------


def test_run_workflow_needs_claude_on_path(scaffolded_book, fake_env, monkeypatch):
    from press import operator

    fake_env(present_tools=[])  # claude absent
    with pytest.raises(SystemExit) as excinfo:
        operator.run_workflow("editorial-passes", {"root": str(scaffolded_book)}, full_bash=False)
    assert "Claude Code CLI" in str(excinfo.value)


# --------------------------------------------------------------------------
# __main__.jargon_check runs the lint through the runner and DECODES its
# bytes into the report -- the migration's decode landmine.
# --------------------------------------------------------------------------


def test_jargon_check_routes_lint_and_decodes_report(scaffolded_book, fake_runner):
    from press import __main__ as cli

    # Non-ASCII lint output: bytes that must be UTF-8 decoded, not stringified.
    fake_runner._by_command[sys.executable] = ProcessResult(0, b"clean \xe2\x9c\x93", b"")
    assert cli.jargon_check() == 0

    recorded = fake_runner.runs[0]
    assert recorded.argv[:3] == (sys.executable, "-m", "press.jargon_lint")
    assert recorded.cwd == str(scaffolded_book)
    assert recorded.capture is True
    # The bytes result is decoded (not passed through as bytes, which would
    # raise TypeError on write_text) -- proving the decode step survives.
    report = (scaffolded_book / "build" / "jargon-report.txt").read_text(encoding="utf-8")
    assert "clean ✓" in report


def test_jargon_check_returns_lint_exit_code(scaffolded_book, fake_runner):
    from press import __main__ as cli

    fake_runner._by_command[sys.executable] = ProcessResult(3, b"rewrite: widget", b"")
    assert cli.jargon_check() == 3
    report = (scaffolded_book / "build" / "jargon-report.txt").read_text(encoding="utf-8")
    assert "rewrite: widget" in report


# --------------------------------------------------------------------------
# __main__._commerce_gate reads PRESS_RELEASE through the environment.
# --------------------------------------------------------------------------


def test_commerce_gate_reads_press_release_through_environment(
    scaffolded_book, fake_env, monkeypatch
):
    from press import __main__ as cli
    from press import commerce

    monkeypatch.setattr(
        commerce, "release_gate", lambda root, book: (["blocked"], "1 problem")
    )
    env = fake_env(values={"PRESS_RELEASE": "1"})
    # A release build fails closed when the gate has problems.
    assert cli._commerce_gate() == 1
    assert "PRESS_RELEASE" in env.reads


def test_commerce_gate_advisory_when_press_release_unset(
    scaffolded_book, fake_env, monkeypatch
):
    from press import __main__ as cli
    from press import commerce

    monkeypatch.setattr(
        commerce, "release_gate", lambda root, book: (["blocked"], "1 problem")
    )
    env = fake_env(values={})
    # Same problems, no PRESS_RELEASE: advisory, exit 0.
    assert cli._commerce_gate() == 0
    assert "PRESS_RELEASE" in env.reads


# --------------------------------------------------------------------------
# __main__._run_render drives pdftoppm through the runner with check=True.
# --------------------------------------------------------------------------


def test_run_render_routes_pdftoppm_through_runner(
    scaffolded_book, fake_runner, monkeypatch
):
    from press import __main__ as cli
    from press import build

    monkeypatch.setattr(build, "build_target", lambda name: None)
    assert cli._run_render([]) == 0

    recorded = fake_runner.runs[-1]
    assert recorded.argv[0] == "pdftoppm"
    assert recorded.check is True
