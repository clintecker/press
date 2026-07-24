"""Proof that the migrated call sites truly go through the adapters.

The boundary gate proves the migrated modules hold no direct
subprocess/env/HTTP call; these tests prove the other half -- that each
site actually drives the injected adapter, with the exact argv, cwd, env
slice, and request it always did. Swapping in a fake is enough to observe
the call, with no live process, credential, or socket.
"""

from __future__ import annotations

import subprocess

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
# verify_coverwrap.render + check_print_safe (issue #199)
# --------------------------------------------------------------------------


def _blank_pdf(path):
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with open(path, "wb") as handle:
        writer.write(handle)
    return path


def test_render_drives_runner_with_pdftoppm(tmp_path, fake_runner):
    from PIL import Image

    from press import verify_coverwrap

    wrap = tmp_path / "wrap.pdf"
    wrap.write_bytes(b"%PDF-1.4\n")
    out_dir = tmp_path / "render"
    out_dir.mkdir()
    # pdftoppm would write this page; the fake does not shell out, so stand
    # in the one page render() demands and prove the call was still made.
    Image.new("RGB", (10, 10), "white").save(out_dir / "wrap-1.png")

    image = verify_coverwrap.render(wrap, out_dir)
    assert isinstance(image, Image.Image)

    assert len(fake_runner.runs) == 1
    recorded = fake_runner.runs[0]
    assert recorded.argv == (
        "pdftoppm", "-png", "-r", "150", str(wrap), str(out_dir / "wrap"),
    )
    assert recorded.check is True
    assert recorded.capture is True


def test_check_print_safe_parses_pdfimages_ppi_through_runner(
    tmp_path, fake_runner, fake_env
):
    from press import verify_coverwrap

    wrap = _blank_pdf(tmp_path / "wrap.pdf")
    fake_env(present_tools=["pdfimages"])
    # A pdfimages -list listing, as bytes (the runner never sets text=True):
    # two header rows then one image well over the 600 PPI print cap.
    listing = (
        "page   num  type   width height color comp bpc  enc  interp  "
        "object ID x-ppi y-ppi size ratio\n"
        "----------------------------------------------------------------\n"
        "   1     0 image    1000  1200  rgb     3   8  jpeg   no        "
        "7  0   700   700  100K  2.0%\n"
    ).encode("utf-8")
    fake_runner._by_command["pdfimages"] = ProcessResult(0, listing)

    with pytest.raises(SystemExit) as excinfo:
        verify_coverwrap.check_print_safe(wrap)
    message = str(excinfo.value)
    # Decoded parse: the offending image reads "image 700x700ppi". Skip the
    # decode and the column comes through as b'image', so this exact
    # substring is absent -- the fail-before/pass-after signal.
    assert "image 700x700ppi" in message
    assert "over 600 PPI" in message

    run = next(r for r in fake_runner.runs if r.argv and r.argv[0] == "pdfimages")
    assert run.argv == ("pdfimages", "-list", str(wrap))
    assert run.capture is True


def test_check_print_safe_softens_when_pdfimages_absent(
    tmp_path, capsys, fake_runner, fake_env
):
    from press import verify_coverwrap

    wrap = _blank_pdf(tmp_path / "wrap.pdf")
    env = fake_env(present_tools=[])  # pdfimages not on PATH

    # No transparency and no resolution tool: the check softens to a note and
    # never reaches for the runner.
    verify_coverwrap.check_print_safe(wrap)
    assert "pdfimages" in env.which_calls
    assert not any(r.argv and r.argv[0] == "pdfimages" for r in fake_runner.runs)
    assert "pdfimages absent" in capsys.readouterr().out
