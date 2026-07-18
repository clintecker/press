"""The press command line: python -m press <target>, or just press <target>.

Dependency edges live here, not in each book's Makefile, so a book cannot
verify a stale artifact or assemble pages before the archives they must
mirror exist.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

from . import booklib

from .registry import FORMATS

USAGE = """usage: press <target>

building        pdf epub html markdown site txt docx pages source all
checking        check style verify verify-formats verify-pages
print pack      print verify-print coverwrap publish kdp|ingram
utilities       render wordcount clean new <directory> selftest
instruments     skills workflows
art             art commission [targets] | art accept <file> --as <target>
operator        improve [--apply] | research | aesthetic ["<brief>"]
"""


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


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        print(USAGE)
        return 2
    target = args[0]

    if target == "new":
        from . import scaffold

        return scaffold.main(args[1:])
    if target == "selftest":
        from . import selftest

        return selftest.main()
    if target == "art":
        from . import art

        return art.main(args[1:])
    if target == "improve":
        from . import operator

        return operator.improve(args[1:])
    if target == "aesthetic":
        from . import operator

        return operator.aesthetic(args[1:])
    if target == "research":
        from . import operator

        return operator.research(args[1:])
    if target == "skills":
        from . import instruments

        return instruments.list_skills()
    if target == "workflows":
        from . import instruments

        return instruments.list_workflows()

    from . import build

    if target in FORMATS or target == "print":
        build.build_target(target)
        return 0
    if target == "source":
        from . import package_source

        return package_source.main()
    if target in ("pages", "verify-pages"):
        from . import registry, verify_pages

        registry.build("pages")
        return verify_pages.main()
    if target == "check":
        return check()
    if target == "style":
        from . import style_audit

        return style_audit.main([])
    if target == "verify":
        build.build_target("pdf")
        return verify_built()
    if target == "coverwrap":
        from . import registry

        registry.build("coverwrap")
        return 0
    if target == "publish":
        from . import publish

        if len(args) != 2:
            print("usage: press publish kdp|ingram")
            return 2
        return publish.main(args[1])
    if target == "verify-print":
        from . import verify_pdf

        build.build_target("print")
        return verify_pdf.main(
            [str(booklib.root() / "dist" / f"{booklib.slug()}-interior.pdf"),
             "--profile", "print"]
        )
    if target == "verify-formats":
        from . import package_source, verify_archives

        for name in ["epub", "html", "markdown", "site", "txt", "docx"]:
            build.build_target(name)
        package_source.main()
        code = verify_formats_built()
        if code:
            return code
        return verify_archives.main()
    if target == "all":
        code = check()
        if code:
            return code
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

        return verify_archives.main()
    if target == "render":
        build.build_target("pdf")
        out = booklib.root() / "build" / "rendered-book"
        out.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["pdftoppm", "-png", "-r", "160",
             str(booklib.root() / "dist" / f"{booklib.slug()}.pdf"), str(out / "page")],
            check=True,
        )
        return 0
    if target == "wordcount":
        from . import wordcount

        return wordcount.main()
    if target == "clean":
        for name in ["build", "dist"]:
            directory = booklib.root() / name
            if directory.exists():
                shutil.rmtree(directory)
        return 0
    print(USAGE)
    print(f"unknown target: {target}")
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
