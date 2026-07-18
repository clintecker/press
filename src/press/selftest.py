"""The press checking itself: press selftest.

Documentation drift is a checker's job, not a promise (checkers over
conventions). This target fails when the CLI grows a target the usage
text or README does not name, when a documented target loses its route,
or when the arithmetic the pipeline trusts (ISBN, ISSN, EAN-13) stops
agreeing with the canonical examples. CI runs it on every push to the
press.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

def modules() -> list[str]:
    """Every module in the package, derived so the list cannot drift."""

    return sorted(
        f"press.{path.stem}"
        for path in Path(__file__).resolve().parent.glob("*.py")
        if path.stem not in {"__init__", "__main__"}
    )


def check_imports() -> None:
    for name in modules():
        importlib.import_module(name)


def check_slug_invariant() -> None:
    from . import booklib

    for good in ("make-ready", "a", "book-2", "9lives"):
        assert booklib.validate_slug(good) == good
    for bad in ("../escape", "a/b", "a\\b", "A-Cap", "spa ce", "", "-lead",
                "dot.seg", "semi;colon", "tick`", "new\nline", "<tag>"):
        try:
            booklib.validate_slug(bad)
        except SystemExit:
            continue
        raise AssertionError(f"slug invariant admitted {bad!r}")


def check_source_policy() -> None:
    """The source packager refuses secrets, skips symlinks without
    dereferencing, and actually deflates its members."""

    import os
    import tempfile
    import zipfile

    from . import booklib, package_source, scaffold

    with tempfile.TemporaryDirectory() as tmp:
        book = Path(tmp) / "policy-proof"
        scaffold.main([str(book)])
        outside = Path(tmp) / "outside-secret.txt"
        outside.write_text("leak", encoding="utf-8")
        (book / "escape.txt").symlink_to(outside)
        (book / ".env").write_text("KEY=1", encoding="utf-8")
        os.environ["BOOK_ROOT"] = str(book)
        booklib.root.cache_clear()
        booklib.metadata.cache_clear()
        try:
            try:
                package_source.main()
            except SystemExit as exc:
                assert ".env" in str(exc), exc
            else:
                raise AssertionError("secret file did not block the archive")
            (book / ".env").unlink()
            package_source.main()
            with zipfile.ZipFile(book / "dist" / "policy-proof-source.zip") as archive:
                names = archive.namelist()
                assert not any("escape" in n for n in names), "symlink archived"
                deflated = [i for i in archive.infolist()
                            if i.compress_type == zipfile.ZIP_DEFLATED]
                assert deflated, "no member was deflated"
        finally:
            del os.environ["BOOK_ROOT"]
            booklib.root.cache_clear()
            booklib.metadata.cache_clear()


def check_arithmetic() -> None:
    from . import barcode, registrations

    assert barcode.validate("978-0-306-40615-7") == "9780306406157"
    pattern = barcode.modules("9780306406157")
    assert len(pattern) == 95 and pattern[:3] == pattern[-3:] == "101"
    assert pattern[45:50] == "01010"
    assert registrations.issn_valid("0378-5955")
    assert not registrations.issn_valid("0378-5954")
    assert not registrations.issn_valid("123X-5678")


def check_docs() -> None:
    from . import __main__ as cli

    here = Path(__file__).resolve().parent
    source = (here / "__main__.py").read_text(encoding="utf-8")
    readme = (here.parent.parent / "README.md")
    usage_words = set(re.findall(r"[a-z-]{2,}", cli.USAGE.split("usage:")[1]))
    routed = set(re.findall(r'target == "([a-z-]+)"', source)) | set(cli.FORMATS)
    missing_from_usage = sorted(routed - usage_words)
    if missing_from_usage:
        raise SystemExit(f"targets routed but absent from usage text: {missing_from_usage}")
    if readme.is_file():
        text = readme.read_text(encoding="utf-8")
        undocumented = sorted(
            t for t in routed if not re.search(rf"\b{re.escape(t)}\b", text)
        )
        if undocumented:
            raise SystemExit(f"targets absent from README: {undocumented}")


def main() -> int:
    check_imports()
    check_arithmetic()
    check_slug_invariant()
    check_source_policy()
    check_docs()
    print(f"Selftest passed: {len(modules())} modules import, arithmetic agrees "
          "with the canonical examples, usage and README name every target")
    return 0
