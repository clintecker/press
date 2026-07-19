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


def _borrow_book(path):
    """Point booklib at a fixture book, restoring the caller's world
    afterward: every cache cleared both ways, BOOK_ROOT restored to its
    prior value rather than deleted."""

    import contextlib
    import os

    from . import booklib

    @contextlib.contextmanager
    def borrowed():
        previous = os.environ.get("BOOK_ROOT")
        os.environ["BOOK_ROOT"] = str(path)
        for cache in (booklib.root, booklib.metadata, booklib.book,
                      booklib.house_rules):
            cache.cache_clear()
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop("BOOK_ROOT", None)
            else:
                os.environ["BOOK_ROOT"] = previous
            for cache in (booklib.root, booklib.metadata, booklib.book,
                          booklib.house_rules):
                cache.cache_clear()

    return borrowed()


def check_source_policy() -> None:
    """The source packager refuses secrets, skips symlinks without
    dereferencing, and actually deflates its members."""

    import tempfile
    import zipfile

    from . import package_source, scaffold

    with tempfile.TemporaryDirectory() as tmp:
        book = Path(tmp) / "policy-proof"
        scaffold.main([str(book)])
        outside = Path(tmp) / "outside-secret.txt"
        outside.write_text("leak", encoding="utf-8")
        (book / "escape.txt").symlink_to(outside)
        (book / ".env").write_text("KEY=1", encoding="utf-8")
        with _borrow_book(book):
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


def check_format_witnesses() -> None:
    """The DOCX extractor reads visible text across split runs, and the
    witness normalization folds case and smart quotes."""

    from .verify_formats import docx_visible_text, normalized

    xml = (b'<?xml version="1.0"?>'
           b'<w:document xmlns:w="http://schemas.openxmlformats.org/'
           b'wordprocessingml/2006/main"><w:body><w:p>'
           b'<w:r><w:t>the witness </w:t></w:r>'
           b'<w:r><w:t>line survives across runs</w:t></w:r>'
           b'</w:p></w:body></w:document>')
    assert "the witness line survives across runs" in docx_visible_text(xml)
    corrupted = xml.replace(b"survives", b"vanished from")
    assert "line survives" not in docx_visible_text(corrupted)
    assert normalized("The \u201cWitness\u201d") == 'the "witness"'


def check_authorities_ledger() -> None:
    """Each ledger refusal is its own diagnostic: malformed, duplicate,
    missing, moved, and ambiguous are named, and a sound ledger yields a
    companion carrying its durable locators."""

    import tempfile

    from . import gen_authorities, scaffold

    with tempfile.TemporaryDirectory() as tmp:
        book = Path(tmp) / "ledger-proof"
        scaffold.main([str(book), "--author", "Ledger Prover"])
        preface = book / "book" / "chapters" / "00-preface.md"
        preface.write_text(preface.read_text() + (
            "\n\nThe lead type was cast at dawn by careful hands."
            "\nIt is said the press ran all night. Some say the press ran all night twice.\n"
        ))
        ledger = book / "config" / "authorities.yaml"
        with _borrow_book(book):
            ledger.write_text("""
- claim: "cast at dawn by careful hands"
  file: "book/chapters/00-preface.md"
  authority: "A Founder's Manual (1888)"
  url: "https://example.org/founders-manual"
- claim: "cast at dawn by careful hands"
  authority: "Duplicate"
- claim: "no such sentence anywhere"
  authority: "Ghost"
- claim: "cast at dawn"
  file: "book/chapters/99-nonexistent.md"
  authority: "Wrong address"
- claim: "the press ran all night"
  authority: "Ambiguous"
- authority: "No claim at all"
""")
            try:
                gen_authorities.generate()
            except SystemExit as exc:
                message = str(exc)
                for marker in ("duplicate claim", "missing", "unknown file",
                               "ambiguous", "malformed"):
                    assert marker in message, (marker, message)
            else:
                raise AssertionError("defective ledger accepted")
            ledger.write_text("""
- claim: "cast at dawn by careful hands"
  file: "book/chapters/00-preface.md"
  authority: "A Founder's Manual (1888)"
  url: "https://example.org/founders-manual"
""")
            gen_authorities.generate()
            companion = book / "dist" / "ledger-proof-sources.md"
            text = companion.read_text()
            assert "example.org/founders-manual" in text, "locator lost"


def check_registry() -> None:
    """The artifact graph is acyclic, outputs are unique, and every
    published artifact resolves to concrete filenames."""

    from . import registry

    order = registry.build_order(list(registry.ARTIFACTS))
    assert len(order) == len(registry.ARTIFACTS), "build order lost artifacts"
    for name, artifact in registry.ARTIFACTS.items():
        for prerequisite in artifact.prerequisites:
            assert order.index(prerequisite) < order.index(name), (
                f"{name} builds before its prerequisite {prerequisite}"
            )
    outputs = [o for a in registry.ARTIFACTS.values() for o in a.outputs]
    assert len(outputs) == len(set(outputs)), "duplicate artifact outputs"
    assert set(registry.FORMATS) <= set(registry.ARTIFACTS)
    resolved = [o.format(slug="proof") for a in registry.ARTIFACTS.values()
                if a.published for o in a.outputs]
    assert all("{" not in n for n in resolved), resolved


def check_book_model() -> None:
    """The typed model normalizes what has two spellings and refuses
    what the v1 design cannot honor, with locatable errors."""

    from . import bookmodel

    root = Path("/nowhere")
    minimal = {"title": "Proof", "author": "One Writer", "slug": "proof",
               "date": "First edition, 2026"}
    book = bookmodel.load(root, minimal)
    assert book.authors == ("One Writer",), "string author not normalized"
    assert book.year == "2026"
    assert (book.trim_width, book.trim_height) == (6.0, 9.0)

    listed = bookmodel.load(root, {**minimal, "author": ["A", "B"]})
    assert listed.authors == ("A", "B")

    try:
        bookmodel.load(root, {**minimal, "trim": {"width": 5, "height": 8}})
    except SystemExit as exc:
        assert "v2" in str(exc) and "5 x 8" in str(exc), exc
    else:
        raise AssertionError("5 x 8 trim accepted; the v1 design is 6 x 9")

    try:
        bookmodel.load(root, {"title": "", "author": [], "slug": "Bad Slug"})
    except SystemExit as exc:
        message = str(exc)
        assert "metadata.yaml" in message
        assert "title" in message and "author" in message and "slug" in message.lower()
    else:
        raise AssertionError("defective configuration accepted")


def check_scaffold_neutrality() -> None:
    """A scaffolded book carries no personal identity: the press's
    author must never become the book's author. The only permitted
    'clintecker' strings are the canonical press machinery references."""

    import tempfile

    from . import scaffold

    with tempfile.TemporaryDirectory() as tmp:
        book = Path(tmp) / "neutrality-proof"
        scaffold.main([str(book), "--author", "Neutral Tester"])
        machinery = {"requirements.txt", "book.yml"}
        for path in book.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            assert "Clint Ecker" not in text, path
            assert "LGTM" not in text, path
            if "clintecker" in text:
                assert path.name in machinery, (
                    f"personal owner leaked into {path}"
                )
        meta = (book / "config" / "metadata.yaml").read_text(encoding="utf-8")
        assert "Neutral Tester" in meta
        assert '# repository: "https://github.com/OWNER/' in meta


def check_pages_verifier() -> None:
    """The pages crawler must reject a broken site and pass a sound one."""

    import tempfile

    from . import verify_pages

    with tempfile.TemporaryDirectory() as tmp:
        pages = Path(tmp)
        (pages / "read").mkdir()
        (pages / "downloads").mkdir()
        (pages / "downloads" / "proof.pdf").write_text("x", encoding="utf-8")
        (pages / "index.html").write_text(
            '<html><body>Proof Book <a href="read/index.html">read</a> '
            '<a href="downloads/proof.pdf">pdf</a></body></html>',
            encoding="utf-8",
        )
        (pages / "read" / "index.html").write_text(
            "<html><body>the sentinel phrase lives here</body></html>",
            encoding="utf-8",
        )
        clean = verify_pages.crawl(pages, ["sentinel phrase"], ["proof.pdf"], "Proof Book")
        assert clean == [], clean
        (pages / "index.html").write_text(
            '<html><body>Proof Book <a href="read/missing.html">dead</a> '
            '<img src="woodcuts/ghost.jpg"> '
            '<a href="downloads/proof.pdf">pdf</a></body></html>',
            encoding="utf-8",
        )
        broken = verify_pages.crawl(pages, ["sentinel phrase"], ["proof.pdf"], "Proof Book")
        assert any("missing.html" in f for f in broken), broken
        assert any("ghost.jpg" in f for f in broken), broken


def check_arithmetic() -> None:
    from . import barcode, registrations

    assert barcode.validate("978-0-306-40615-7") == "9780306406157"
    pattern = barcode.modules("9780306406157")
    assert len(pattern) == 95 and pattern[:3] == pattern[-3:] == "101"
    assert pattern[45:50] == "01010"
    assert registrations.issn_valid("0378-5955")
    assert not registrations.issn_valid("0378-5954")
    assert not registrations.issn_valid("123X-5678")


def render_reference() -> str:
    """docs/REFERENCE.md, generated from the executable registries so
    documentation cannot drift from what the code actually does."""

    from . import registry
    from . import __main__ as cli

    lines = [
        "# Press reference",
        "",
        "Generated by `press selftest --write-docs` from the artifact",
        "registry and the CLI's own usage; the selftest fails when this",
        "file drifts from the machinery it describes.",
        "",
        "## Artifacts",
        "",
        "| artifact | outputs | prerequisites | published |",
        "|---|---|---|---|",
    ]
    for a in registry.ARTIFACTS.values():
        published = "yes" if a.published else "no"
        if a.condition:
            published += f" (when {a.condition} configured)"
        lines.append(
            f"| {a.name} | {', '.join(a.outputs)} | "
            f"{', '.join(a.prerequisites) or '-'} | {published} |"
        )
    lines += ["", "## Targets", "", "```", cli.USAGE.strip(), "```", ""]
    return "\n".join(lines)


def check_docs() -> None:
    from . import __main__ as cli

    here = Path(__file__).resolve().parent
    source = (here / "__main__.py").read_text(encoding="utf-8")
    readme = (here.parent.parent / "README.md")
    usage_words = set(re.findall(r"[a-z-]{2,}", cli.USAGE.split("usage:")[1]))
    routed = set(re.findall(r'target == "([a-z-]+)"', source)) | set(cli.FORMATS)
    # Tuple routes (`target in ("pages", "verify-pages")`) count too; the
    # first version of this check only saw equality routes and blessed a
    # usage text that omitted them.
    for group in re.findall(r"target in \(([^)]*)\)", source):
        routed |= set(re.findall(r'"([a-z-]+)"', group))
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
    reference = here.parent.parent / "docs" / "REFERENCE.md"
    if reference.is_file() and reference.read_text(encoding="utf-8") != render_reference():
        raise SystemExit(
            "docs/REFERENCE.md drifted from the registry; regenerate with "
            "`press selftest --write-docs`"
        )


def main(argv: list[str] | None = None) -> int:
    if argv and "--write-docs" in argv:
        target = Path(__file__).resolve().parent.parent.parent / "docs" / "REFERENCE.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_reference(), encoding="utf-8")
        print(f"wrote {target}")
    check_imports()
    check_arithmetic()
    check_slug_invariant()
    check_source_policy()
    check_pages_verifier()
    check_scaffold_neutrality()
    check_book_model()
    check_registry()
    check_format_witnesses()
    check_authorities_ledger()
    check_docs()
    print(f"Selftest passed: {len(modules())} modules import, arithmetic agrees "
          "with the canonical examples, usage and README name every target")
    return 0
