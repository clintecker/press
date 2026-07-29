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

    fake = fakes.FakeProcessRunner(results=[subprocess.CalledProcessError(1, ["pandoc"])])
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

    fake = fakes.FakeProcessRunner(by_command={"git": subprocess.CalledProcessError(128, "git")})
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
    fake_runner._queue.append(ProcessResult(1, b"clean-prose.md:1: rewrite: avoid 'utilize'\n"))

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
        lambda pages: cw.wrap_geometry(6.0, 9.0, 0.115, True, 0.125, 0.0, 0.0, 0.0, "paperback"),
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
        "latexmk",
        "-lualatex",
        "-interaction=nonstopmode",
        "coverwrap.tex",
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
    fake = fakes.FakeProcessRunner(by_command={"epubcheck": OSError("Exec format error")})
    monkeypatch.setattr(adapters, "process_runner", fake)
    with pytest.raises(SystemExit) as excinfo:
        verify_formats.epubcheck(tmp_path / "book.epub")
    assert "present but cannot run" in str(excinfo.value)


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
        "pdftoppm",
        "-png",
        "-r",
        "150",
        str(wrap),
        str(out_dir / "wrap"),
    )
    assert recorded.check is True
    assert recorded.capture is True


def test_check_print_safe_parses_pdfimages_ppi_through_runner(tmp_path, fake_runner, fake_env):
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


def test_check_print_safe_softens_when_pdfimages_absent(tmp_path, capsys, fake_runner, fake_env):
    from press import verify_coverwrap

    wrap = _blank_pdf(tmp_path / "wrap.pdf")
    env = fake_env(present_tools=[])  # pdfimages not on PATH

    # No transparency and no resolution tool: the check softens to a note and
    # never reaches for the runner.
    verify_coverwrap.check_print_safe(wrap)
    assert "pdfimages" in env.which_calls
    assert not any(r.argv and r.argv[0] == "pdfimages" for r in fake_runner.runs)
    assert "pdfimages absent" in capsys.readouterr().out


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

    monkeypatch.setattr(commerce, "release_gate", lambda root, book: (["blocked"], "1 problem"))
    # booklib.root() now reads BOOK_ROOT through the same environment adapter,
    # so the fake must carry it too or root() falls back to cwd and refuses.
    env = fake_env(values={"PRESS_RELEASE": "1", "BOOK_ROOT": str(scaffolded_book)})
    # A release build fails closed when the gate has problems.
    assert cli._commerce_gate() == 1
    assert "PRESS_RELEASE" in env.reads


def test_commerce_gate_advisory_when_press_release_unset(scaffolded_book, fake_env, monkeypatch):
    from press import __main__ as cli
    from press import commerce

    monkeypatch.setattr(commerce, "release_gate", lambda root, book: (["blocked"], "1 problem"))
    env = fake_env(values={"BOOK_ROOT": str(scaffolded_book)})
    # Same problems, no PRESS_RELEASE: advisory, exit 0.
    assert cli._commerce_gate() == 0
    assert "PRESS_RELEASE" in env.reads


# --------------------------------------------------------------------------
# __main__._run_render drives pdftoppm through the runner with check=True.
# --------------------------------------------------------------------------


def test_run_render_routes_pdftoppm_through_runner(scaffolded_book, fake_runner, monkeypatch):
    from press import __main__ as cli
    from press import build

    monkeypatch.setattr(build, "build_target", lambda name: None)
    assert cli._run_render([]) == 0

    recorded = fake_runner.runs[-1]
    assert recorded.argv[0] == "pdftoppm"
    assert recorded.check is True


# booklib reads BOOK_ROOT and PRESS_RELEASE through the environment
# --------------------------------------------------------------------------


def test_root_reads_book_root_through_environment(scaffolded_book, fake_env):
    from press import booklib

    fake = fake_env(values={"BOOK_ROOT": str(scaffolded_book)})
    booklib.root.cache_clear()
    try:
        resolved = booklib.root()
    finally:
        booklib.root.cache_clear()
    assert resolved == scaffolded_book.resolve()
    # the fake actually served the read: proof the call crossed the adapter
    # and did not touch os.environ (which would leave the fake untouched).
    assert "BOOK_ROOT" in fake.reads


def test_require_release_witnesses_early_returns_off_press_release(fake_env):
    from press import booklib

    fake = fake_env(values={})  # PRESS_RELEASE unset
    assert booklib.require_release_witnesses() is None
    assert "PRESS_RELEASE" in fake.reads


def test_require_release_witnesses_honors_press_release_from_environment(scaffolded_book, fake_env):
    from press import booklib

    fake = fake_env(values={"BOOK_ROOT": str(scaffolded_book), "PRESS_RELEASE": "1"})
    # a fresh scaffold's witnesses are vacuous (no sentinels, 1-page floor),
    # so reading PRESS_RELEASE=1 through the fake must force the release refusal.
    for cache in (booklib.root, booklib.metadata, booklib.book):
        cache.cache_clear()
    try:
        with pytest.raises(SystemExit) as excinfo:
            booklib.require_release_witnesses()
    finally:
        for cache in (booklib.root, booklib.metadata, booklib.book):
            cache.cache_clear()
    assert "PRESS_RELEASE=1" in str(excinfo.value)
    assert "PRESS_RELEASE" in fake.reads


# --------------------------------------------------------------------------
# selftest.borrow_book redirects BOOK_ROOT through the environment adapter
# (issue #199). booklib.root() reads BOOK_ROOT through the same singleton, so
# borrow_book must write through it too -- the fake records the writes.
# --------------------------------------------------------------------------


def test_borrow_book_sets_and_unsets_book_root_through_environment(tmp_path, fake_env):
    from press import selftest

    fake = fake_env(values={})  # BOOK_ROOT absent, so exit unsets it
    book = tmp_path / "borrowed-book"
    with selftest.borrow_book(book):
        # inside the block, the adapter has been written the fixture's root...
        assert fake.writes[0] == ("BOOK_ROOT", str(book))
        assert fake.get("BOOK_ROOT") == str(book)
    # ...and the exit unset it, because there was no prior value to restore.
    assert fake.writes[-1] == ("BOOK_ROOT", None)
    assert fake.get("BOOK_ROOT") is None


def test_borrow_book_restores_a_prior_book_root_through_environment(tmp_path, fake_env):
    from press import selftest

    prior = str(tmp_path / "outer-book")
    fake = fake_env(values={"BOOK_ROOT": prior})
    book = tmp_path / "inner-book"
    with selftest.borrow_book(book):
        assert fake.writes[0] == ("BOOK_ROOT", str(book))
    # the prior value is restored by a set, not deleted.
    assert fake.writes[-1] == ("BOOK_ROOT", prior)
    assert fake.get("BOOK_ROOT") == prior


# --------------------------------------------------------------------------
def test_check_release_grammar_routes_tag_checks_through_runner(monkeypatch):
    from press import selftest

    script = Path(selftest.__file__).resolve().parent.parent.parent / "scripts" / "release.sh"
    if not script.is_file():
        # release.sh ships with the checkout, not the wheel; check_release_grammar
        # returns early without touching the runner, so there is nothing to prove.
        pytest.skip("release.sh not present (installed wheel, not a checkout)")

    # Good tags must exit 0, the trailing bad tags nonzero: program the good
    # ones and default the rest to a rejection, so the grammar loop is happy
    # while every run is still observed on the fake.
    fake = fakes.FakeProcessRunner(
        results=[ProcessResult(0)] * len(selftest.GOOD_TAGS),
        default=ProcessResult(1),
    )
    monkeypatch.setattr(adapters, "process_runner", fake)
    selftest.check_release_grammar()

    assert len(fake.runs) == len(selftest.GOOD_TAGS) + len(selftest.BAD_TAGS)
    first = fake.runs[0]
    assert first.argv[0] == "bash"
    assert first.argv[1].endswith("scripts/release.sh")
    assert first.argv[2] == "--check-tag"
    assert first.argv[3] in selftest.GOOD_TAGS
    assert first.capture is True
    assert first.check is False


# --------------------------------------------------------------------------
# selftest.check_source_policy runs its nested git init/add/commit with NO
# env, so the runner's GIT_* strip applies (issue #199). A recording runner
# that delegates to the real one proves both the routing and the env=None.
# --------------------------------------------------------------------------


def test_check_source_policy_runs_nested_git_with_env_none(monkeypatch):
    from press import selftest

    real = production.SubprocessRunner()
    recorded: list[tuple[tuple[str, ...], object]] = []

    class RecordingRunner:
        def run(self, argv, **kwargs):
            recorded.append((tuple(argv), kwargs.get("env")))
            return real.run(argv, **kwargs)

    monkeypatch.setattr(adapters, "process_runner", RecordingRunner())
    selftest.check_source_policy()

    # The nested-repo commands: `git init`, `git add`, and `git -c ... commit`.
    # (package_source's `git -C <root> ls-files` is a different repo probe and
    # is excluded by the second-word filter.)
    nested = [
        (argv, env)
        for argv, env in recorded
        if argv and argv[0] == "git" and len(argv) > 1 and argv[1] in ("init", "add", "-c")
    ]
    assert nested, "check_source_policy drove no nested git commands through the runner"
    for argv, env in nested:
        assert env is None, (argv, env)
