"""Proof that the migrated call sites truly go through the adapters.

The boundary gate proves the migrated modules hold no direct
subprocess/env/HTTP call; these tests prove the other half -- that each
site actually drives the injected adapter, with the exact argv, cwd, env
slice, and request it always did. Swapping in a fake is enough to observe
the call, with no live process, credential, or socket.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

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
# verify_pdf: run_capture, tool probes, and page rendering
# --------------------------------------------------------------------------


def test_run_capture_drives_runner_and_decodes_bytes(fake_runner):
    """run_capture routes through the runner with capture+check and turns
    the runner's BYTES stdout into the ``str`` its callers regex over.
    Against the pre-migration code the fake is never driven and this argv
    assertion has nothing to read."""
    from press import verify_pdf

    fake_runner._by_command["pdfinfo"] = ProcessResult(0, b"Pages:          7\n")
    out = verify_pdf.run_capture(["pdfinfo", "book.pdf"])
    assert out == "Pages:          7\n"  # decoded to str, not left as bytes
    recorded = fake_runner.runs[0]
    assert recorded.argv == ("pdfinfo", "book.pdf")
    assert recorded.capture is True
    assert recorded.check is True


def test_run_capture_propagates_calledprocesserror(monkeypatch):
    """check=True must let the runner's CalledProcessError propagate; the
    wrapper never catches and rethrows it."""
    from press import verify_pdf

    fake = fakes.FakeProcessRunner(
        by_command={"pdffonts": subprocess.CalledProcessError(1, ["pdffonts"])}
    )
    monkeypatch.setattr(adapters, "process_runner", fake)
    with pytest.raises(subprocess.CalledProcessError):
        verify_pdf.run_capture(["pdffonts", "book.pdf"])


def test_verify_fonts_probes_pdffonts_through_environment(fake_env):
    """The pdffonts presence check goes through environment.which; with the
    tool absent the diagnostic is unchanged. The which_calls assertion is
    empty against the pre-migration shutil.which call."""
    from press import verify_pdf

    env = fake_env(present_tools=[])  # pdffonts absent
    with pytest.raises(SystemExit) as excinfo:
        verify_pdf.verify_fonts(Path("book.pdf"))
    assert "required verification tool missing: pdffonts" in str(excinfo.value)
    assert "pdffonts" in env.which_calls


def test_verify_info_probes_tools_and_parses_pdfinfo_through_runner(fake_env, fake_runner):
    """verify_info probes pdfinfo+pdftotext through the environment, then
    parses pdfinfo's decoded output from the runner (trim 6x9 in => 432x648
    pts, 50 pages >= 40)."""
    from press import verify_pdf

    env = fake_env(present_tools=["pdfinfo", "pdftotext"])
    fake_runner._by_command["pdfinfo"] = ProcessResult(
        0, b"Pages:          50\nPage size:      432 x 648 pts\n"
    )
    pages = verify_pdf.verify_info(Path("book.pdf"), 6.0, 9.0, 40)
    assert pages == 50
    assert env.which_calls == ["pdfinfo", "pdftotext"]
    assert fake_runner.runs[0].argv == ("pdfinfo", "book.pdf")
    assert fake_runner.runs[0].capture is True


def test_render_pages_drives_pdftoppm_through_runner(tmp_path, fake_runner, monkeypatch):
    """With the sandbox render script absent, render_pages falls back to
    pdftoppm through the runner. The fake produces no PNGs, so the page-count
    guard fires -- but only after the runner was driven with the pdftoppm
    argv. Against the pre-migration code the fake is never touched."""
    from press import verify_pdf

    monkeypatch.setattr(verify_pdf, "RENDER_SCRIPT", Path("/nonexistent/render_pdf.py"))
    with pytest.raises(SystemExit):  # 0 PNGs vs 3 expected
        verify_pdf.render_pages(Path("book.pdf"), tmp_path / "render", 3)
    recorded = fake_runner.runs[0]
    assert recorded.argv[0] == "pdftoppm"
    assert "-png" in recorded.argv
    assert recorded.check is True
