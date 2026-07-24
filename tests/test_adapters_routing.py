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
# scaffold.git_identity reads the git byline through the process runner
# --------------------------------------------------------------------------


def test_git_identity_drives_runner_and_decodes_name(fake_runner):
    from press import scaffold

    # Programmed as BYTES, the way the production runner always answers a
    # captured run; the site must decode them. If it forgets and strips the
    # raw bytes, `name or None` yields b"Ada Lovelace", not the str -- so
    # this equality is the fail-before/pass-after signal for the decode.
    fake_runner._by_command["git"] = ProcessResult(0, b"Ada Lovelace\n")
    assert scaffold.git_identity() == "Ada Lovelace"
    recorded = fake_runner.runs[0]
    assert recorded.argv == ("git", "config", "user.name")
    assert recorded.capture is True


def test_git_identity_none_when_name_unset(fake_runner):
    from press import scaffold

    # git exits nonzero (or clean) with empty stdout when no user.name is
    # configured; the empty byline collapses to None.
    fake_runner._by_command["git"] = ProcessResult(1, b"")
    assert scaffold.git_identity() is None


def test_git_identity_none_when_git_absent(monkeypatch):
    from press import scaffold

    fake = fakes.FakeProcessRunner(by_command={"git": OSError("no git")})
    monkeypatch.setattr(adapters, "process_runner", fake)
    assert scaffold.git_identity() is None
# check_the_checkers.diagnostics drives the jargon lint through the runner
# --------------------------------------------------------------------------


def test_diagnostics_runs_jargon_lint_through_runner(
    scaffolded_book, tmp_path, fake_runner, monkeypatch
):
    """The jargon-lint invocation goes through the process runner with the
    exact argv, captures output, and does not raise on the nonzero exit it
    inspects itself (check must be off)."""

    from press import check_the_checkers

    monkeypatch.setattr(check_the_checkers.booklib, "house_rules", lambda: {})
    fixture = tmp_path / "clean-prose.md"
    fixture.write_text("A calm and ordinary sentence.\n", encoding="utf-8")

    # A nonzero exit whose captured stdout names a rewrite the parser must
    # surface. Bytes on purpose: the runner never decodes.
    fake_runner._queue.append(
        ProcessResult(1, b"clean-prose.md:1: rewrite: avoid 'utilize'\n")
    )

    found = check_the_checkers.diagnostics(fixture)

    # The fake was actually driven: the jargon-lint argv, captured.
    recorded = fake_runner.runs[0]
    assert recorded.argv[1:4] == ("-m", "press.jargon_lint", "--fail-on")
    assert recorded.argv[4] == "rewrite"
    assert recorded.argv[-1] == str(fixture)
    assert recorded.capture is True
    assert recorded.check is False

    # The decode landmine: the bytes were decoded before the "rewrite:"
    # parse, so the diagnostic actually surfaces. Match bytes and it silently
    # disappears (or raises) and this assertion fails.
    assert any("rewrite: avoid 'utilize'" in d for d in found)
    assert any(d.startswith("jargon: ") for d in found)


def test_diagnostics_passes_jargon_allow_terms_to_runner(
    scaffolded_book, tmp_path, fake_runner, monkeypatch
):
    """A book's jargon-allow list becomes ``--allow`` argv on the faked run,
    proving the house-rules read reaches the command the runner sees."""

    from press import check_the_checkers

    monkeypatch.setattr(
        check_the_checkers.booklib, "house_rules", lambda: {"jargon-allow": ["leverage"]}
    )
    fixture = tmp_path / "clean-prose.md"
    fixture.write_text("A calm and ordinary sentence.\n", encoding="utf-8")

    check_the_checkers.diagnostics(fixture)

    argv = fake_runner.runs[0].argv
    assert "--allow" in argv
    assert argv[argv.index("--allow") + 1] == "leverage"
# gen_coverwrap.generate compiles the wrap through the process runner
# --------------------------------------------------------------------------


@pytest.fixture
def coverwrap_book(tmp_path, monkeypatch):
    """A factory book wired so ``gen_coverwrap.generate`` reaches its
    ``latexmk`` call with the heavy upstream helpers -- interior page count,
    wrap layout, print-safe asset prep -- stubbed to constants. Only the
    subprocess seam and its failure handling stay real, so a fake runner
    observes exactly the argv, cwd, and capture flag the module drives."""

    from tests.factories import BookFactory

    from press import gen_coverwrap as cw
    from press import print_safe

    handle = (
        BookFactory(slug="cw-routing")
        .with_metadata(publisher="Routing Press", **{"publisher-place": "Nowhere"})
        .build(tmp_path)
    )
    cover = handle.root / "assets" / "cover.jpg"
    cover.parent.mkdir(parents=True, exist_ok=True)
    cover.write_bytes(b"\xff\xd8\xff\xd9")  # a stand-in: prepare_cover is stubbed

    monkeypatch.setattr(cw, "interior_page_count", lambda interior: 100)
    monkeypatch.setattr(
        cw,
        "layout",
        lambda pages: cw.wrap_geometry(
            6.0, 9.0, 0.115, True, 0.125, 0.0, 0.0, 0.0, "paperback"
        ),
    )
    monkeypatch.setattr(print_safe, "prepare_cover", lambda *a, **k: {"cover": cover})
    return handle


def test_coverwrap_generate_drives_latexmk_through_runner(coverwrap_book, monkeypatch):
    from press import gen_coverwrap as cw
    from press.adapters.protocols import ProcessResult

    # A nonzero return stops generate before it would copy a nonexistent PDF,
    # leaving the recorded run as the observable signal.
    fake = fakes.FakeProcessRunner(results=[ProcessResult(1, stdout=b"stopped")])
    monkeypatch.setattr(adapters, "process_runner", fake)
    with coverwrap_book.use():
        interior = coverwrap_book.root / "interior.pdf"  # stubbed reader ignores it
        with pytest.raises(SystemExit):
            cw.generate(interior, coverwrap_book.root / "dist" / "wrap.pdf")

    assert len(fake.runs) == 1, "the wrap must compile through the process runner"
    run = fake.runs[0]
    assert run.argv == (
        "latexmk", "-lualatex", "-interaction=nonstopmode", "coverwrap.tex",
    )
    assert run.cwd == str(coverwrap_book.root / "build" / "coverwrap")
    assert run.capture is True


def test_coverwrap_generate_decodes_stdout_tail_on_failure(coverwrap_book, monkeypatch):
    from press import gen_coverwrap as cw
    from press.adapters.protocols import ProcessResult

    # No coverwrap.log is written (the fake never runs latexmk), so the
    # diagnostic falls back to the captured stdout -- which is now BYTES. The
    # trailing 0xff proves errors="replace" decoding; an undecoded value would
    # render as a b'...' repr and this endswith would not hold.
    marker = "coverwrap latexmk boom"
    fake = fakes.FakeProcessRunner(
        results=[ProcessResult(1, stdout=marker.encode("utf-8") + b"\xff")]
    )
    monkeypatch.setattr(adapters, "process_runner", fake)
    with coverwrap_book.use():
        with pytest.raises(SystemExit) as excinfo:
            cw.generate(
                coverwrap_book.root / "interior.pdf",
                coverwrap_book.root / "dist" / "wrap.pdf",
            )
    message = str(excinfo.value)
    assert marker in message
    assert message.endswith(f"coverwrap TeX failed; log tail:\n{marker}�")
# verify_formats.epubcheck resolves the tool, the toolchain promise, and the
# validator run through the adapters.
# --------------------------------------------------------------------------


def test_epubcheck_absent_outside_toolchain_warns_and_returns(fake_env, capsys):
    from press import verify_formats

    env = fake_env(values={}, present_tools=[])  # epubcheck not on PATH
    # No PRESS_TOOLCHAIN, so the structural-only warning path, not a refusal.
    verify_formats.epubcheck(Path("book.epub"))
    assert env.which_calls == ["epubcheck"]
    assert "PRESS_TOOLCHAIN" in env.reads
    assert "WARNING: epubcheck not installed" in capsys.readouterr().out


def test_epubcheck_absent_inside_toolchain_refuses(fake_env):
    from press import verify_formats

    fake_env(values={"PRESS_TOOLCHAIN": "1"}, present_tools=[])
    with pytest.raises(SystemExit) as excinfo:
        verify_formats.epubcheck(Path("book.epub"))
    assert "missing from the press toolchain image" in str(excinfo.value)


def test_epubcheck_drives_runner_with_epubcheck_argv(fake_env, fake_runner, tmp_path):
    from press import verify_formats

    fake_env(present_tools=["epubcheck"])
    epub = tmp_path / "book.epub"
    fake_runner._by_command["epubcheck"] = ProcessResult(0)
    verify_formats.epubcheck(epub)
    assert len(fake_runner.runs) == 1
    recorded = fake_runner.runs[0]
    assert recorded.argv == ("epubcheck", str(epub))
    assert recorded.capture is True


def test_epubcheck_decodes_bytes_report_into_diagnostic(fake_env, fake_runner, tmp_path):
    from press import verify_formats

    fake_env(present_tools=["epubcheck"])
    # The runner returns BYTES; the diagnostic must decode them, not embed a
    # bytes-repr. Fails before the migration if stdout/stderr are used raw.
    fake_runner._by_command["epubcheck"] = ProcessResult(
        1, stdout=b"ERROR: bad spine item\n", stderr=b"WARN: missing nav\n"
    )
    with pytest.raises(SystemExit) as excinfo:
        verify_formats.epubcheck(tmp_path / "book.epub")
    message = str(excinfo.value)
    assert "ERROR: bad spine item" in message
    assert "WARN: missing nav" in message
    assert "b'" not in message  # decoded text, never a bytes-repr


def test_epubcheck_oserror_is_toolchain_fault(fake_env, monkeypatch, tmp_path):
    from press import verify_formats

    fake_env(present_tools=["epubcheck"])
    fake = fakes.FakeProcessRunner(
        by_command={"epubcheck": OSError("Exec format error")}
    )
    monkeypatch.setattr(adapters, "process_runner", fake)
    with pytest.raises(SystemExit) as excinfo:
        verify_formats.epubcheck(tmp_path / "book.epub")
    assert "present but cannot run" in str(excinfo.value)
