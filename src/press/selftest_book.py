"""The selftest's manuscript, editorial, and build-surface checks.

Split out of ``selftest.py`` alongside :mod:`press.selftest_release`. These
verify a book's content and the build machinery: slug validity, the source
packager's refusals, format/edition witnesses, the editorial checkers,
site identity, the authorities ledger, the artifact registry, scaffold
neutrality, extension conformance, and jargon-checker parity.

``selftest.py`` re-exports every check defined here, so
``selftest.check_<name>``, the ordered ``CHECKS`` list, and
``quality_checks``' ``getattr(selftest, "check_<name>")`` keep resolving.
Shared helpers (``borrow_book``, the slug corpus, the jargon source
helpers) live in ``selftest.py`` and are imported lazily inside the
function bodies to dodge the re-export import cycle.
"""

from __future__ import annotations

import sys
from pathlib import Path


def check_slug_invariant() -> None:
    from . import booklib
    from .selftest import BAD_SLUGS, GOOD_SLUGS

    for good in GOOD_SLUGS:
        assert booklib.validate_slug(good) == good
    for bad in BAD_SLUGS:
        try:
            booklib.validate_slug(bad)
        except SystemExit:
            continue
        raise AssertionError(f"slug invariant admitted {bad!r}")


def _source_policy_refuses_secret(book, package_source) -> None:
    """A book carrying a secret file (.env) blocks the archive entirely."""

    try:
        package_source.main()
    except SystemExit as exc:
        assert ".env" in str(exc), exc
    else:
        raise AssertionError("secret file did not block the archive")


def _source_policy_archive_excludes(book, source_zip, package_source, verify_archives) -> None:
    """Without the secret, the archive builds, skips the symlink, deflates
    its members, and digest-verifies; an appended member the policy did not
    admit fails that verification."""

    import zipfile

    (book / ".env").unlink()
    package_source.main()
    with zipfile.ZipFile(source_zip) as archive:
        names = archive.namelist()
        assert not any("escape" in n for n in names), "symlink archived"
        deflated = [i for i in archive.infolist() if i.compress_type == zipfile.ZIP_DEFLATED]
        assert deflated, "no member was deflated"

    assert verify_archives.verify_source_zip(source_zip, "policy-proof") == []
    with zipfile.ZipFile(source_zip, "a") as archive:
        archive.writestr("policy-proof/private-notes.md", "not for anyone")
    appended = verify_archives.verify_source_zip(source_zip, "policy-proof")
    assert any("did not admit" in f for f in appended), appended


def _source_policy_excludes_untracked(book, source_zip, package_source, verify_archives) -> None:
    """Untracked private files stay out of the archive.

    A commit hook exports its in-progress index. A nested git command must
    not inherit that repository identity or it stages this fixture into the
    caller's commit and runs the caller's hooks. Passing NO env is what
    enforces that: the process runner strips the GIT_* repository-binding
    variables for a git command whose env is None, so this book observes
    only itself. Handing it an explicit env would disable that strip.
    """

    import zipfile

    from . import adapters

    adapters.process_runner.run(["git", "init", "-q"], cwd=book, check=True)
    adapters.process_runner.run(["git", "add", "-A"], cwd=book, check=True)
    adapters.process_runner.run(
        [
            "git",
            "-c",
            "user.email=proof@press",
            "-c",
            "user.name=Proof",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=book,
        check=True,
    )
    (book / "private-working-notes.md").write_text("draft", encoding="utf-8")
    package_source.main()
    with zipfile.ZipFile(source_zip) as archive:
        assert not any("private-working-notes" in n for n in archive.namelist()), (
            "untracked file published"
        )
    assert verify_archives.verify_source_zip(source_zip, "policy-proof") == []


def _source_policy_site_bytes(book, verify_archives) -> None:
    """A flipped byte inside a site zip member is a different book."""

    import shutil
    import zipfile

    site_dir = book / "dist" / "site"
    site_dir.mkdir(parents=True)
    (site_dir / "index.html").write_text("<html>true text</html>", encoding="utf-8")

    shutil.make_archive(
        str(book / "dist" / "policy-proof-site"),
        "zip",
        root_dir=book / "dist",
        base_dir="site",
    )
    site_zip = book / "dist" / "policy-proof-site.zip"
    assert verify_archives.verify_site_zip(site_zip, site_dir) == []
    with zipfile.ZipFile(site_zip, "w") as archive:
        archive.writestr("site/index.html", "<html>trxe text</html>")
    tampered = verify_archives.verify_site_zip(site_zip, site_dir)
    assert any("bytes disagree" in f for f in tampered), tampered


def check_source_policy() -> None:
    """The source packager refuses secrets, skips symlinks without
    dereferencing, and actually deflates its members."""

    import tempfile

    from . import package_source, scaffold
    from .selftest import borrow_book

    with tempfile.TemporaryDirectory() as tmp:
        book = Path(tmp) / "policy-proof"
        scaffold.main([str(book)])
        outside = Path(tmp) / "outside-secret.txt"
        outside.write_text("leak", encoding="utf-8")
        (book / "escape.txt").symlink_to(outside)
        (book / ".env").write_text("KEY=1", encoding="utf-8")
        with borrow_book(book):
            from . import verify_archives

            source_zip = book / "dist" / "policy-proof-source.zip"
            # The audit's damage pair for archives: an appended member the
            # policy did not admit, and untracked private files, must both
            # fail digest-exact verification.
            _source_policy_refuses_secret(book, package_source)
            _source_policy_archive_excludes(book, source_zip, package_source, verify_archives)
            _source_policy_excludes_untracked(book, source_zip, package_source, verify_archives)
            _source_policy_site_bytes(book, verify_archives)


def check_format_witnesses() -> None:
    """The DOCX extractor reads visible text across split runs, and the
    witness normalization folds case and smart quotes."""

    from .verify_formats import docx_visible_text, normalized

    xml = (
        b'<?xml version="1.0"?>'
        b'<w:document xmlns:w="http://schemas.openxmlformats.org/'
        b'wordprocessingml/2006/main"><w:body><w:p>'
        b"<w:r><w:t>the witness </w:t></w:r>"
        b"<w:r><w:t>line survives across runs</w:t></w:r>"
        b"</w:p></w:body></w:document>"
    )
    assert "the witness line survives across runs" in docx_visible_text(xml)
    corrupted = xml.replace(b"survives", b"vanished from")
    assert "line survives" not in docx_visible_text(corrupted)
    assert normalized("The \u201cWitness\u201d") == 'the "witness"'


def check_editorial_checkers() -> None:
    """The checker self-test in the fast tier: run check_the_checkers over
    the packaged known-bad fixtures inside a clean scaffolded book (no book
    fixtures of its own), proving every declared rule still fires and the
    known-good fixture is accepted. INV-editorial-checkers had only an
    integration proof; this gives it a runnable fast-tier one."""

    import contextlib
    import io
    import tempfile

    from . import check_the_checkers, scaffold
    from .selftest import borrow_book

    with tempfile.TemporaryDirectory() as tmp:
        book = Path(tmp) / "checker-proof"
        scaffold.main([str(book), "--author", "Checker Prover"])
        with borrow_book(book):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = check_the_checkers.main()
            if code != 0:
                raise SystemExit(
                    "selftest: check_the_checkers rejected the packaged "
                    f"fixtures:\n{buffer.getvalue()}"
                )
            if "each" not in buffer.getvalue():
                raise SystemExit(
                    f"selftest: check_the_checkers produced no pass line; got:\n{buffer.getvalue()}"
                )


def check_editions_agree() -> None:
    """Cross-edition content agreement: editions that all carry every
    chapter's witness pass, and an edition that silently drops a chapter is
    named and refused. Pure and toolchain-free -- synthetic edition texts,
    no build. Proves INV-format-agreement closes INV-format-witness's
    one-line-per-document limit."""

    from . import verify_formats

    witnesses = {
        "01-one.md": "the first chapter carries this exact distinctive sentence about the shop",
        "02-two.md": "the second chapter speaks of the devil and the hell box in plain words",
    }
    everything = " ".join(witnesses.values())
    editions = {
        "HTML": f"front matter {everything} back matter",
        # The EPUB witness lines are split by furniture and reordered padding,
        # but each chapter's distinctive fragment still survives intact.
        "EPUB": (
            f"chapter one {witnesses['01-one.md']} PAGE 5 make ready "
            f"chapter two {witnesses['02-two.md']} colophon"
        ),
    }
    verify_formats.verify_editions_agree(editions, witnesses)  # agreement: no raise

    broken = dict(editions)
    broken["EPUB"] = witnesses["01-one.md"] + " but everything after is gone"
    try:
        verify_formats.verify_editions_agree(broken, witnesses)
    except SystemExit as exc:
        assert "02-two.md" in str(exc), exc
        assert "EPUB" in str(exc), exc
    else:
        raise AssertionError("an edition that dropped a chapter passed cross-edition agreement")


def check_site_identity() -> None:
    """The audit's damage case for site identity: a duplicated chapter
    page must fail on its witness appearing twice, and a removed
    chapter must fail on its witness appearing nowhere."""

    import shutil
    import tempfile

    from . import scaffold, verify_formats
    from .selftest import borrow_book

    with tempfile.TemporaryDirectory() as tmp:
        book = Path(tmp) / "identity-proof"
        scaffold.main([str(book), "--author", "Identity Prover"])
        chapter = book / "book" / "chapters" / "01-first.md"
        chapter.write_text(
            "# First\n\nThe first chapter carries this exact identity "
            "line and no other chapter repeats it anywhere.\n"
        )
        site = book / "dist" / "site"
        site.mkdir(parents=True)
        (site / "index.html").write_text("<html><body>contents</body></html>")
        (site / "reader.css").write_text("body{}")
        with borrow_book(book):
            from . import booklib

            witnesses = verify_formats.chapter_witnesses()
            for name, witness in witnesses.items():
                (site / name.replace(".md", ".html")).write_text(
                    f"<html><body><p>{witness}</p><p>{booklib.book().title}</p></body></html>"
                )
            verify_formats.verify_site(site)
            shutil.copy(site / "01-first.html", site / "duplicate-chapter.html")
            try:
                verify_formats.verify_site(site)
            except SystemExit as exc:
                assert "duplicates" in str(exc), exc
            else:
                raise AssertionError("duplicated chapter page passed verify_site")
            (site / "duplicate-chapter.html").unlink()
            page = site / "01-first.html"
            page.write_text("<html><body>replaced with other words</body></html>")
            try:
                verify_formats.verify_site(site)
            except SystemExit as exc:
                assert "missing" in str(exc), exc
            else:
                raise AssertionError("missing chapter text passed verify_site")


def check_authorities_ledger() -> None:
    """Each ledger refusal is its own diagnostic: malformed, duplicate,
    missing, moved, and ambiguous are named, and a sound ledger yields a
    companion carrying its durable locators."""

    import tempfile

    from . import gen_authorities, scaffold
    from .selftest import borrow_book

    with tempfile.TemporaryDirectory() as tmp:
        book = Path(tmp) / "ledger-proof"
        scaffold.main([str(book), "--author", "Ledger Prover"])
        preface = book / "book" / "chapters" / "00-preface.md"
        preface.write_text(
            preface.read_text()
            + (
                "\n\nThe lead type was cast at dawn by careful hands."
                "\nIt is said the press ran all night. Some say the press ran all night twice.\n"
            )
        )
        ledger = book / "config" / "authorities.yaml"
        with borrow_book(book):
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
                for marker in (
                    "duplicate claim",
                    "missing",
                    "unknown file",
                    "ambiguous",
                    "malformed",
                ):
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
    resolved = [
        o.format(slug="proof")
        for a in registry.ARTIFACTS.values()
        if a.published
        for o in a.outputs
    ]
    assert all("{" not in n for n in resolved), resolved


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
                assert path.name in machinery, f"personal owner leaked into {path}"
        meta = (book / "config" / "metadata.yaml").read_text(encoding="utf-8")
        assert "Neutral Tester" in meta
        assert '# repository: "https://github.com/OWNER/' in meta


def check_extension_conformance() -> None:
    """The extension contract has teeth: the reference third-party manifest
    conforms, and every hostile manifest is refused before execution -- a
    core-name collision, an unsupported contract major, a sealed-capability
    claim, and an unproven invariant each turn conformance red, while a
    structurally malformed manifest is refused at the parser boundary. The
    fixtures ship as package data, so an installed wheel proves this too."""

    from . import extensions

    fixtures = extensions.fixtures_dir()
    reference = extensions.load_manifest_file(fixtures / "reference.yaml")
    problems = extensions.conformance(reference)
    if problems:
        raise SystemExit(
            "the reference extension manifest must conform, but was refused:\n"
            + "\n".join(f"  - {p}" for p in problems)
        )

    # The malformed manifest is refused by the parser, before policy runs.
    try:
        extensions.load_manifest_file(fixtures / "hostile" / "malformed.yaml")
    except SystemExit:
        pass
    else:
        raise SystemExit(
            "hostile/malformed.yaml is structurally invalid but load_manifest accepted it"
        )

    # Every other hostile manifest parses but fails conformance.
    hostile = sorted(p for p in (fixtures / "hostile").glob("*.yaml") if p.name != "malformed.yaml")
    if not hostile:
        raise SystemExit("no hostile extension fixtures found to prove refusal")
    for path in hostile:
        manifest = extensions.load_manifest_file(path)
        if extensions.conforms(manifest):
            raise SystemExit(f"hostile extension {path.name} must be refused, but it conformed")


def _check_jargon_default_watchlist_agrees() -> None:
    """Both copies default to the very same watchlist file and status
    table, so identical matching code cannot still diverge on which terms
    it reads."""

    import importlib.util

    from . import jargon_lint as package_impl
    from .selftest import _jargon_impl_paths

    _, skill_copy = _jargon_impl_paths()
    spec = importlib.util.spec_from_file_location("press._jargon_skill_selftest", skill_copy)
    if spec is None or spec.loader is None:
        raise SystemExit("selftest: cannot load the portable jargon skill copy")
    skill_impl = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = skill_impl
    spec.loader.exec_module(skill_impl)

    if package_impl.STATUS_LEVEL != skill_impl.STATUS_LEVEL:
        raise SystemExit("selftest: jargon STATUS_LEVEL tables disagree")

    pkg_default = package_impl.parse_args([]).watchlist.resolve()
    skill_default = skill_impl.parse_args([]).watchlist.resolve()
    if pkg_default != skill_default:
        raise SystemExit(
            "selftest: jargon checkers default to different watchlists -- "
            f"package {pkg_default}, skill {skill_default}"
        )


def check_jargon_parity() -> None:
    """The package jargon checker and the portable skill copy share every
    line of parsing, normalization, matching, allowlist, and reporting
    logic, and resolve the same default watchlist; a fix or rule cannot
    land in one execution surface and silently skip the other. The
    behavioural corpus lives in tests/test_jargon_parity.py."""

    from .selftest import _jargon_impl_paths, _jargon_shared_defs

    package_copy, skill_copy = _jargon_impl_paths()
    for path in (package_copy, skill_copy):
        if not path.is_file():
            raise SystemExit(f"selftest: jargon checker missing at {path}")

    skill_source = skill_copy.read_text(encoding="utf-8")
    pkg_defs = _jargon_shared_defs(package_copy.read_text(encoding="utf-8"))
    skill_defs = _jargon_shared_defs(skill_source)

    if pkg_defs.keys() != skill_defs.keys():
        only_pkg = sorted(pkg_defs.keys() - skill_defs.keys())
        only_skill = sorted(skill_defs.keys() - pkg_defs.keys())
        raise SystemExit(
            "selftest: jargon checkers define different names -- "
            f"package only {only_pkg}, skill only {only_skill}"
        )

    drifted = sorted(name for name, body in pkg_defs.items() if skill_defs[name] != body)
    if drifted:
        raise SystemExit(
            "selftest: jargon checker logic drifted between the package copy and "
            f"the portable skill copy in: {drifted}. A matching or reporting fix "
            "must land in both src/press/jargon_lint.py and "
            "src/press/data/skills/overused-jargon/scripts/jargon_lint.py."
        )

    # The portable copy must not reach back into the package: an author runs it
    # standalone, from a checkout, with no press on the path.
    for forbidden in ("from . import", "import press", "from press "):
        if forbidden in skill_source:
            raise SystemExit(
                "selftest: the portable jargon skill imports the package "
                f"({forbidden!r}); it must stay importable without it."
            )

    _check_jargon_default_watchlist_agrees()
