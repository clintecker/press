"""The press command line: python -m press <target>, or just press <target>.

Dependency edges live here, not in each book's Makefile, so a book cannot
verify a stale artifact or assemble pages before the archives they must
mirror exist.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Callable

from . import booklib

from .registry import FORMATS

from .catalog import render_usage

# Generated from the one command catalog so the usage text cannot drift
# from the commands the CLI dispatches or the desk offers.
USAGE = render_usage()


def jargon_check() -> int:
    """Run the jargon lint over the manuscript, report to build/jargon-report.txt."""

    root = booklib.root()
    allow = booklib.house_rules().get("jargon-allow") or []
    (root / "build").mkdir(exist_ok=True)
    files = [str(path) for path in booklib.chapter_files()]
    command = [
        sys.executable, "-m", "press.jargon_lint",
        "--fail-on", "rewrite",
        *[arg for term in allow for arg in ("--allow", term)],
        *files,
    ]
    result = subprocess.run(command, capture_output=True, text=True, cwd=root)
    report = root / "build" / "jargon-report.txt"
    report.write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode != 0:
        print(report.read_text(encoding="utf-8"))
        return result.returncode
    print("Jargon check passed: no rewrite-status terms (full audit in build/jargon-report.txt)")
    return 0


def check() -> int:
    from . import check_source, check_the_checkers, style_audit

    for step in (check_source.main, check_the_checkers.main, lambda: style_audit.main([])):
        code = step()
        if code:
            return code
    return jargon_check()


def verify_built() -> int:
    from . import verify_pdf

    # Anchored to the book root so BOOK_ROOT from any directory
    # verifies the book's artifacts, not the caller's.
    return verify_pdf.main([str(booklib.root() / "dist" / f"{booklib.slug()}.pdf")])


def verify_formats_built() -> int:
    from . import verify_formats

    dist = booklib.root() / "dist"
    slug = booklib.slug()
    return verify_formats.main([
        str(dist / f"{slug}.html"), str(dist / f"{slug}.epub"),
        "--markdown", str(dist / f"{slug}.md"), "--text", str(dist / f"{slug}.txt"),
        "--docx", str(dist / f"{slug}.docx"), "--site", str(dist / "site"),
    ])


def _run_new(args: list[str]) -> int:
    from . import scaffold

    return scaffold.main(args[1:])


def _run_config(args: list[str]) -> int:
    from . import config_cli

    return config_cli.main(args)


def _run_selftest(args: list[str]) -> int:
    from . import selftest

    return selftest.main(args[1:])


def _run_doctor(args: list[str]) -> int:
    from . import doctor

    return doctor.main()


def _run_art(args: list[str]) -> int:
    from . import art

    return art.main(args[1:])


def _run_improve(args: list[str]) -> int:
    from . import operator

    return operator.improve(args[1:])


def _run_aesthetic(args: list[str]) -> int:
    from . import operator

    return operator.aesthetic(args[1:])


def _run_research(args: list[str]) -> int:
    from . import operator

    return operator.research(args[1:])


def _run_skills(args: list[str]) -> int:
    from . import instruments

    return instruments.list_skills()


def _run_workflows(args: list[str]) -> int:
    from . import instruments

    return instruments.list_workflows()


def _run_desk(args: list[str]) -> int:
    from . import desk

    return desk.run(args[1:])


def _run_source(args: list[str]) -> int:
    from . import package_source

    return package_source.main()


def _run_pages(args: list[str]) -> int:
    from . import registry, verify_pages

    registry.build("pages")
    return verify_pages.main()


def _run_check(args: list[str]) -> int:
    return check()


def _run_style(args: list[str]) -> int:
    from . import style_audit

    return style_audit.main([])


def _run_verify(args: list[str]) -> int:
    from . import build

    build.build_target("pdf")
    return verify_built()


def _run_coverwrap(args: list[str]) -> int:
    from . import registry, verify_coverwrap

    registry.build("coverwrap")
    return verify_coverwrap.main()


def _run_publish(args: list[str]) -> int:
    from . import publish

    rest = [a for a in args[1:] if a != "--report-only"]
    if len(rest) != 1:
        print("usage: press publish kdp|ingram [--report-only]")
        return 2
    return publish.main(rest[0], report_only="--report-only" in args)


def _run_verify_print(args: list[str]) -> int:
    from . import registry, verify_coverwrap, verify_pdf

    registry.build("print")
    code = verify_pdf.main(
        [str(booklib.root() / "dist" / f"{booklib.slug()}-interior.pdf"),
         "--profile", "print"]
    )
    if code:
        return code
    # The wrap needs cover art; a coverless book still verifies its
    # interior (assets are optional, per the config contract).
    if (booklib.root() / "assets" / "cover.jpg").is_file():
        registry.build("coverwrap")
        return verify_coverwrap.main()
    print("no assets/cover.jpg; interior verified, wrap not built")
    return 0


def _run_verify_formats(args: list[str]) -> int:
    from . import build, package_source, verify_archives

    for name in ["epub", "html", "markdown", "site", "txt", "docx"]:
        build.build_target(name)
    package_source.main()
    code = verify_formats_built()
    if code:
        return code
    return verify_archives.main()


def _run_all(args: list[str]) -> int:
    code = check()
    if code:
        return code
    from . import build

    for name in FORMATS:
        build.build_target(name)
    from . import package_source

    package_source.main()
    build.build_target("pages")
    from . import verify_pages

    code = verify_pages.main()
    if code:
        return code
    code = verify_built()
    if code:
        return code
    code = verify_formats_built()
    if code:
        return code
    from . import verify_archives

    code = verify_archives.main()
    if code:
        return code
    return _commerce_gate()


def _commerce_gate() -> int:
    """The print-ordering release gate: a book advertising ordering may not
    ship unless its exact edition passed a physical qualification. Advisory
    in a development build; fail-closed under PRESS_RELEASE, like the
    witness gate."""

    import os

    from . import booklib, commerce

    problems, summary = commerce.release_gate(booklib.root(), booklib.book())
    print(f"commerce release gate: {summary}")
    if not problems:
        return 0
    for problem in problems:
        print(f"  - {problem}")
    if os.environ.get("PRESS_RELEASE"):
        return 1
    print("(commerce gate is advisory here; a release build (PRESS_RELEASE=1) "
          "enforces it)")
    return 0


def _run_render(args: list[str]) -> int:
    from . import build

    build.build_target("pdf")
    out = booklib.root() / "build" / "rendered-book"
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["pdftoppm", "-png", "-r", "160",
         str(booklib.root() / "dist" / f"{booklib.slug()}.pdf"), str(out / "page")],
        check=True,
    )
    return 0


def _run_wordcount(args: list[str]) -> int:
    from . import wordcount

    return wordcount.main()


def _run_clean(args: list[str]) -> int:
    for name in ["build", "dist"]:
        directory = booklib.root() / name
        if directory.exists():
            shutil.rmtree(directory)
    return 0


ROUTES: dict[str, Callable[[list[str]], int]] = {
    "new": _run_new,
    "config": _run_config,
    "selftest": _run_selftest,
    "doctor": _run_doctor,
    "art": _run_art,
    "improve": _run_improve,
    "aesthetic": _run_aesthetic,
    "research": _run_research,
    "skills": _run_skills,
    "workflows": _run_workflows,
    "desk": _run_desk,
    "source": _run_source,
    "pages": _run_pages,
    "verify-pages": _run_pages,
    "check": _run_check,
    "style": _run_style,
    "verify": _run_verify,
    "coverwrap": _run_coverwrap,
    "publish": _run_publish,
    "verify-print": _run_verify_print,
    "verify-formats": _run_verify_formats,
    "all": _run_all,
    "render": _run_render,
    "wordcount": _run_wordcount,
    "clean": _run_clean,
}


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        print(USAGE)
        return 2
    target = args[0]

    handler = ROUTES.get(target)
    if handler is not None:
        return handler(args)
    if target in FORMATS or target == "print":
        from . import build

        build.build_target(target)
        return 0
    print(USAGE)
    print(f"unknown target: {target}")
    return 2


def console() -> int:
    """The one entry for both `press` and `python -m press`: when a
    pipeline tool fails, its own output is the last word, carried out
    through its exit code, not wrapped in a Python traceback."""

    try:
        return main()
    except subprocess.CalledProcessError as exc:
        return exc.returncode


if __name__ == "__main__":
    raise SystemExit(console())
