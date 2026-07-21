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

from . import invariants

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


# The slug invariant's evidence, stated once: the pytest suite
# parametrizes over these same tuples, so the two runners cannot
# disagree about what a slug is.
GOOD_SLUGS = ("make-ready", "a", "book-2", "9lives")
BAD_SLUGS = ("../escape", "a/b", "a\\b", "A-Cap", "spa ce", "", "-lead",
             "dot.seg", "semi;colon", "tick`", "new\nline", "<tag>")


def check_slug_invariant() -> None:
    from . import booklib

    for good in GOOD_SLUGS:
        assert booklib.validate_slug(good) == good
    for bad in BAD_SLUGS:
        try:
            booklib.validate_slug(bad)
        except SystemExit:
            continue
        raise AssertionError(f"slug invariant admitted {bad!r}")


def clear_book_caches() -> None:
    """Every booklib cache emptied, so a borrowed or fixture book cannot
    leak into the caller's world through a memoized answer."""

    from . import booklib

    for cache in (booklib.root, booklib.metadata, booklib.book,
                  booklib.house_rules):
        cache.cache_clear()


def borrow_book(path):
    """Point booklib at a fixture book, restoring the caller's world
    afterward: every cache cleared both ways, BOOK_ROOT restored to its
    prior value rather than deleted."""

    import contextlib
    import os

    @contextlib.contextmanager
    def borrowed():
        previous = os.environ.get("BOOK_ROOT")
        os.environ["BOOK_ROOT"] = str(path)
        clear_book_caches()
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop("BOOK_ROOT", None)
            else:
                os.environ["BOOK_ROOT"] = previous
            clear_book_caches()

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
        with borrow_book(book):
            try:
                package_source.main()
            except SystemExit as exc:
                assert ".env" in str(exc), exc
            else:
                raise AssertionError("secret file did not block the archive")
            (book / ".env").unlink()
            package_source.main()
            source_zip = book / "dist" / "policy-proof-source.zip"
            with zipfile.ZipFile(source_zip) as archive:
                names = archive.namelist()
                assert not any("escape" in n for n in names), "symlink archived"
                deflated = [i for i in archive.infolist()
                            if i.compress_type == zipfile.ZIP_DEFLATED]
                assert deflated, "no member was deflated"

            from . import verify_archives

            # The audit's damage pair for archives: an appended member
            # the policy did not admit, and untracked private files,
            # must both fail digest-exact verification.
            assert verify_archives.verify_source_zip(source_zip, "policy-proof") == []
            with zipfile.ZipFile(source_zip, "a") as archive:
                archive.writestr("policy-proof/private-notes.md", "not for anyone")
            appended = verify_archives.verify_source_zip(source_zip, "policy-proof")
            assert any("did not admit" in f for f in appended), appended

            import subprocess as sp

            # A commit hook exports its in-progress index. A nested git command
            # must not inherit that repository identity or it stages this
            # fixture into the caller's commit and runs the caller's hooks.
            import os

            nested_git_env = os.environ.copy()
            for name in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_WORK_TREE"):
                nested_git_env.pop(name, None)

            sp.run(["git", "init", "-q"], cwd=book, env=nested_git_env, check=True)
            sp.run(["git", "add", "-A"], cwd=book, env=nested_git_env, check=True)
            sp.run(
                ["git", "-c", "user.email=proof@press", "-c", "user.name=Proof",
                 "commit", "-qm", "fixture"],
                cwd=book, env=nested_git_env, check=True,
            )
            (book / "private-working-notes.md").write_text("draft", encoding="utf-8")
            package_source.main()
            with zipfile.ZipFile(source_zip) as archive:
                assert not any("private-working-notes" in n for n in archive.namelist()), (
                    "untracked file published"
                )
            assert verify_archives.verify_source_zip(source_zip, "policy-proof") == []

            # A flipped byte inside a site zip member is a different book.
            site_dir = book / "dist" / "site"
            site_dir.mkdir(parents=True)
            (site_dir / "index.html").write_text("<html>true text</html>", encoding="utf-8")
            import shutil as sh

            sh.make_archive(str(book / "dist" / "policy-proof-site"), "zip",
                            root_dir=book / "dist", base_dir="site")
            site_zip = book / "dist" / "policy-proof-site.zip"
            assert verify_archives.verify_site_zip(site_zip, site_dir) == []
            with zipfile.ZipFile(site_zip, "w") as archive:
                archive.writestr("site/index.html", "<html>trxe text</html>")
            tampered = verify_archives.verify_site_zip(site_zip, site_dir)
            assert any("bytes disagree" in f for f in tampered), tampered


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


def check_site_identity() -> None:
    """The audit's damage case for site identity: a duplicated chapter
    page must fail on its witness appearing twice, and a removed
    chapter must fail on its witness appearing nowhere."""

    import shutil
    import tempfile

    from . import scaffold, verify_formats

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
                    f"<html><body><p>{witness}</p>"
                    f"<p>{booklib.book().title}</p></body></html>"
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

    with tempfile.TemporaryDirectory() as tmp:
        book = Path(tmp) / "ledger-proof"
        scaffold.main([str(book), "--author", "Ledger Prover"])
        preface = book / "book" / "chapters" / "00-preface.md"
        preface.write_text(preface.read_text() + (
            "\n\nThe lead type was cast at dawn by careful hands."
            "\nIt is said the press ran all night. Some say the press ran all night twice.\n"
        ))
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


def check_honest_refusals() -> None:
    """Bad input gets a named refusal, never a traceback or an
    injection: config parse errors are locatable, a failing tool's
    exit code passes through the console entry, a malformed banned
    pattern names its file, and metadata reaching HTML or generated
    appendices is escaped."""

    import subprocess
    import tempfile

    from . import booklib, build, gen_authorities, scaffold, style_audit
    from . import __main__ as cli

    fragment = build.cover_fragment_html('The "Devil\'s" <Case> & Co.')
    if "<Case>" in fragment or 'The "Devil' in fragment:
        raise SystemExit("selftest: cover fragment does not escape the title")
    if "&amp; Co." not in fragment:
        raise SystemExit("selftest: cover fragment lost the escaped ampersand")

    term = gen_authorities.print_safe("foo\\input{/etc/hostname}")
    if "\\" in term:
        raise SystemExit("selftest: print_safe let a backslash through to TeX")

    def failing_tool(argv=None):
        raise subprocess.CalledProcessError(43, ["pandoc"])

    original = cli.main
    cli.main = failing_tool
    try:
        code = cli.console()
    finally:
        cli.main = original
    if code != 43:
        raise SystemExit(
            f"selftest: console() returned {code}, not the failing tool's 43"
        )

    with tempfile.TemporaryDirectory() as tmp:
        book = Path(tmp) / "refusal-proof"
        scaffold.main([str(book), "--author", "Refusal Prover"])
        metadata_file = book / "config" / "metadata.yaml"
        sound_metadata = metadata_file.read_text()
        with borrow_book(book):
            for content, wants in (
                ('title: "Unclosed', "metadata.yaml"),
                ("", "empty"),
                ("- just\n- a\n- list\n", "mapping"),
            ):
                metadata_file.write_text(content)
                booklib.metadata.cache_clear()
                try:
                    booklib.metadata()
                except SystemExit as exc:
                    if wants not in str(exc):
                        raise SystemExit(
                            f"selftest: metadata refusal {str(exc)!r} "
                            f"does not mention {wants!r}"
                        )
                else:
                    raise SystemExit(
                        f"selftest: metadata content {content!r} was accepted"
                    )
            metadata_file.write_text(sound_metadata)
            booklib.metadata.cache_clear()
            (book / "config" / "house-rules.yaml").write_text(
                'banned-patterns:\n  "\\\\bleverage(": "banned verb"\n'
            )
            booklib.house_rules.cache_clear()
            try:
                style_audit.banned_book_patterns()
            except SystemExit as exc:
                if "house-rules.yaml" not in str(exc):
                    raise SystemExit(
                        "selftest: banned-pattern refusal does not name "
                        "house-rules.yaml"
                    )
            else:
                raise SystemExit(
                    "selftest: malformed banned pattern was accepted"
                )


def check_aesthetic_schema() -> None:
    """The book-aesthetics skill documents every configuration key the
    aesthetic engine consumes, so a drafted aesthetic.yaml can actually
    reach the site and PDF; drift fails here, not in an author's
    confused draft."""

    from . import yamlio

    here = Path(__file__).resolve().parent
    skill = (here / "data" / "skills" / "book-aesthetics.md").read_text(encoding="utf-8")
    source = (here / "aesthetic.py").read_text(encoding="utf-8")
    consumed = set(re.findall(r'(?:merged|overrides)\.get\("([a-z-]+)"\)', source))
    consumed |= set(re.findall(r'\.get\("((?:web|pdf)-family)"\)', source))
    house = set(yamlio.load(here / "data" / "aesthetic-house.yaml") or {})
    undocumented = sorted(
        key for key in consumed | house if key not in skill
    )
    if undocumented:
        raise SystemExit(
            "book-aesthetics.md does not document keys the aesthetic "
            f"engine consumes: {', '.join(undocumented)}"
        )
    for subkey in ("ink", "muted", "accent", "link"):
        if subkey not in skill:
            raise SystemExit(
                f"book-aesthetics.md omits the book-colors subkey {subkey!r}"
            )


def check_coverwrap_detectors() -> None:
    """The wrap verifier's rendering checks, proven against deliberate
    damage: a flat front panel, a missing barcode, too few bars, and
    ink in the quiet zone each turn red on synthetic images."""

    from PIL import Image, ImageDraw

    from . import verify_coverwrap

    trim_w, spine, dpi = 6.0, 0.115, 50
    bleed = 0.125
    wrap_w = 2 * bleed + 2 * trim_w + spine
    wrap_h = 2 * bleed + 9.0
    size = (int(wrap_w * dpi), int(wrap_h * dpi))

    flat = Image.new("RGB", size, (200, 190, 180))
    front_x = bleed + trim_w + spine   # perfect-bound front-panel edge
    try:
        verify_coverwrap.check_front_panel(flat, front_x, wrap_w)
    except SystemExit as exc:
        assert "flat" in str(exc) or "blank" in str(exc), exc
    else:
        raise AssertionError("flat front panel passed the wrap verifier")

    def barcode_image(bars: int, quiet_ink: bool) -> Image.Image:
        # All geometry in inches scaled by dpi, and everything kept
        # inside scanline's crop window (which ends 0.05in past the
        # anchor): the first version advanced bars by raw pixels and
        # drew its quiet-zone ink outside the inspected region, so the
        # "damage" was invisible and the check asserted the wrong way.
        image = Image.new("L", size, 180)
        draw = ImageDraw.Draw(image)
        anchor_x, anchor_y = bleed + trim_w - 0.5, bleed + 0.5
        card_left = int((anchor_x - 1.6) * dpi)
        card_right = int(anchor_x * dpi)
        card_top = size[1] - int((anchor_y + 1.05) * dpi)
        card_bottom = size[1] - int((anchor_y - 0.32) * dpi)
        draw.rectangle((card_left, card_top, card_right, card_bottom), fill=255)
        bar_top = size[1] - int((anchor_y + 0.32 + 0.9) * dpi)
        bar_bottom = size[1] - int((anchor_y + 0.32) * dpi)
        # Bars live where the verifier expects the symbol: 95 modules
        # ending 0.15in inside the card's east edge; quiet-zone ink is
        # drawn in the right-hand zone beyond that expected span.
        symbol_right = int((anchor_x - 0.15) * dpi)
        symbol_left = symbol_right - int(95 * 0.0130 * dpi)
        x = symbol_left + 2
        for _ in range(bars):
            draw.rectangle((x, bar_top, x, bar_bottom), fill=0)
            x += 2
        if quiet_ink:
            zone = symbol_right + int(0.05 * dpi)
            draw.rectangle((zone, bar_top, zone + 1, bar_bottom), fill=0)
        return image

    verify_coverwrap.scanline(barcode_image(22, False), trim_w, wrap_w,
                              "9780306406157")
    try:
        verify_coverwrap.scanline(Image.new("L", size, 180), trim_w, wrap_w, None)
    except SystemExit as exc:
        assert "white card" in str(exc), exc
    else:
        raise AssertionError("missing barcode card passed the wrap verifier")
    try:
        verify_coverwrap.scanline(barcode_image(3, False), trim_w, wrap_w,
                                  "9780306406157")
    except SystemExit as exc:
        assert "transitions" in str(exc), exc
    else:
        raise AssertionError("threadbare barcode passed the wrap verifier")
    try:
        verify_coverwrap.scanline(barcode_image(22, True), trim_w, wrap_w,
                                  "9780306406157")
    except SystemExit as exc:
        assert "quiet zone" in str(exc), exc
    else:
        raise AssertionError("ink in the quiet zone passed the wrap verifier")


# The release grammar's evidence, stated once for both runners.
GOOD_TAGS = ("v1.0.0", "v0.0.1", "v10.20.30")
BAD_TAGS = ("v1.0", "v1.0.0.0", "v1.0.0-rc1", "v1.0.0x", "v01.0.0",
            "1.0.0", "v1..0", "v1.0.0 ")


def check_receipt_chain() -> None:
    """The trust-receipt chain refuses a broken chain: a dirty-tree
    release receipt, a release whose package digest does not match the
    built object, and an incomplete chain that skips trust layers are
    each rejected."""

    from . import receipts

    inputs = {"invariants": "d", "fixtures": "d", "scenarios": "d",
              "surfaces": "d", "toolchain": "sha-x"}
    dirty = receipts.Receipt(
        schema_version=receipts.SCHEMA_VERSION, layer="release",
        source_commit="c", tree_clean=False, inputs=inputs,
        prerequisites=[], proofs=[],
        artifacts={"package": "PKG", "toolchain": "sha-x"}, local_dev=True)
    if not any("dirty tree" in p for p in receipts.verify_chain([dirty], require_clean=True)):
        raise SystemExit("selftest: receipt chain blessed a dirty-tree release")
    clean = receipts.Receipt(
        schema_version=receipts.SCHEMA_VERSION, layer="release",
        source_commit="c", tree_clean=True, inputs=inputs,
        prerequisites=[], proofs=[],
        artifacts={"package": "PKG", "toolchain": receipts.pinned_toolchain_digest()})
    if not any("package digest" in p for p in receipts.verify_release([clean], "OTHER")):
        raise SystemExit("selftest: release receipt blessed a package mismatch")
    # A two-layer placeholder standing in for every layer must be refused:
    # completeness is what turns the chain from an assertion into a proof.
    collection = receipts.Receipt(
        schema_version=receipts.SCHEMA_VERSION, layer="collection",
        source_commit="c", tree_clean=True, inputs=inputs, prerequisites=[],
        proofs=[], artifacts={})
    placeholder_release = receipts.Receipt(
        schema_version=receipts.SCHEMA_VERSION, layer="release",
        source_commit="c", tree_clean=True, inputs=inputs,
        prerequisites=[collection.digest()], proofs=[],
        artifacts={"package": "PKG", "toolchain": receipts.pinned_toolchain_digest()})
    if not any("incomplete release chain" in p
               for p in receipts.verify_release([collection, placeholder_release], "PKG")):
        raise SystemExit("selftest: release chain blessed a skipped trust layer")
    # The per-job release (#150) fails closed when a CI tier's receipt is
    # absent: a job that did not run leaves a missing receipt.
    tiers = [receipts.Receipt(
        schema_version=receipts.SCHEMA_VERSION, layer="quality", source_commit="c",
        tree_clean=True, inputs=inputs, prerequisites=[], proofs=[], artifacts={})]
    # 'integration' deliberately absent: its job did not run.
    if not any("missing tier receipt 'integration'" in p
               for p in receipts.verify_ci_release(tiers, "PKG")):
        raise SystemExit("selftest: per-job release blessed a missing CI tier")


def check_edition_manifest() -> None:
    """The edition manifest holds for a valid release-gated edition and
    refuses a forged identity and a byte mismatch: an order can only name
    the exact bytes the release approved."""

    import dataclasses

    from . import edition

    interior_sha = "1" * 64
    cover_sha = "2" * 64
    base = edition.EditionManifest(
        schema_version=edition.SCHEMA_VERSION, edition_id="",
        slug="proof-book", title="Proof", format="paperback", isbn=None,
        trim_width=6.0, trim_height=9.0, page_count=120, paper="cream",
        spine_width_in=0.3, bleed_in=0.125,
        interior=edition.ArtifactRef("interior", interior_sha, 4096),
        cover=edition.ArtifactRef("cover", cover_sha, 2048),
        toolchain_digest="sha-abc", source_commit="c0ffee", tree_clean=True,
        input_digests={"invariants": "d"}, receipt_digests=("r0",))
    manifest = dataclasses.replace(
        base, edition_id=edition._identity_digest(base))
    observed = edition.Observed(interior_sha, 4096, 120, cover_sha, 2048)
    if edition.verify_facts(manifest, observed):
        raise SystemExit("selftest: edition manifest rejected a valid edition")
    # A production fact changed without re-deriving identity is a forgery.
    forged = dataclasses.replace(manifest, page_count=manifest.page_count + 10)
    if not any("identity digest" in p for p in edition.verify_facts(forged, observed)):
        raise SystemExit("selftest: edition manifest blessed a forged identity")
    # The artifact on disk no longer hashes to the recorded digest.
    tampered = edition.Observed("0" * 64, 4096, 120, cover_sha, 2048)
    if not any("interior digest" in p for p in edition.verify_facts(manifest, tampered)):
        raise SystemExit("selftest: edition manifest blessed a byte mismatch")


def check_provider_qualification() -> None:
    """The provider record is well-formed, and only a passed physical
    inspection scoped to the edition qualifies a provider: marketing alone
    and a stale or wrong-edition inspection are refused."""

    from . import qualification as q

    problems = q.validate()
    if problems:
        raise SystemExit(f"selftest: provider qualification record invalid: {problems[:2]}")
    passed = {point: q.PASS for point in q.REQUIRED_CHECKLIST}
    # A single failed point cannot qualify: the physical gate is real.
    failed = q.PhysicalInspection("ed1", "lulu", "PB", "US", "inspector",
                                  {**passed, "barcode": "fail"})
    qual, probs = q.qualify(failed, "ed1")
    if qual is not None or not any("not passed" in p for p in probs):
        raise SystemExit("selftest: qualification honored a failed physical inspection")
    # A copy inspected against a different edition is stale.
    other = q.PhysicalInspection("edX", "lulu", "PB", "US", "inspector", passed)
    qual2, probs2 = q.qualify(other, "ed1")
    if qual2 is not None or not any("different edition" in p for p in probs2):
        raise SystemExit("selftest: qualification honored a stale inspection")


def check_commerce_config() -> None:
    """The print-order config verifier refuses an insecure origin, an
    unnamed seller, and an embedded secret; a policy page may be linked out
    or generated; and the CTA is emitted only for a sellable edition."""

    from . import commerce

    good = commerce.load({"commerce": {"print-ordering": {
        "enabled": True, "edition": "paperback",
        "storefront-url": "https://store.example.test/x", "seller-of-record": "Lulu",
        "support-url": "https://ex.test/s"}}})  # privacy/refund omitted -> generated
    if good is None or commerce.validate(good):
        raise SystemExit("selftest: commerce verifier rejected a valid config")
    if good.generated_kinds() != ["privacy", "refund"]:
        raise SystemExit("selftest: an omitted policy link should be generated")
    if not commerce.should_emit(good, sellable=True) or commerce.should_emit(good, sellable=False):
        raise SystemExit("selftest: commerce CTA emission ignored edition sellability")
    bad = commerce.load({"commerce": {"print-ordering": {
        "enabled": True, "edition": "paperback", "storefront-url": "http://insecure",
        "seller-of-record": "", "support-url": "https://ex.test/s?api_key=sk_live_x",
        "privacy-url": "http://x"}}})
    problems = commerce.validate(bad)
    for needle in ("storefront-url must be https", "seller-of-record",
                   "privacy-url must be https", "secret"):
        if not any(needle in p for p in problems):
            raise SystemExit(f"selftest: commerce verifier missed {needle!r}")


def check_commerce_release_gate() -> None:
    """The print-ordering release gate fails closed: a book advertising
    ordering cannot ship unless its edition passed a physical
    qualification; a book that sells nothing ships freely."""

    from . import commerce

    enabled = commerce.load({"commerce": {"print-ordering": {
        "enabled": True, "edition": "paperback",
        "storefront-url": "https://store.example.test/x", "seller-of-record": "Lulu",
        "support-url": "https://ex.test/s", "privacy-url": "https://ex.test/p",
        "refund-url": "https://ex.test/r"}}})
    if not any("no passed physical qualification" in p
               for p in commerce.release_problems(enabled, edition_qualified=False)):
        raise SystemExit("selftest: release gate shipped an unqualified commerce edition")
    if commerce.release_problems(enabled, edition_qualified=True):
        raise SystemExit("selftest: release gate blocked a qualified, valid edition")
    disabled = commerce.load({"commerce": {"print-ordering": {"enabled": False}}})
    if commerce.release_problems(disabled, edition_qualified=False):
        raise SystemExit("selftest: release gate blocked a book that sells nothing")


def check_provider_contract() -> None:
    """A print provider adapter keeps the neutral contract: money parses
    without float error, an unsupported capability is a typed refusal, an
    unknown status quarantines, and a submission timeout is an unknown
    outcome -- never a fabricated acceptance or a guessed transition."""

    from .providers import contract, fake

    cents = (contract.Money.parse("USD", "0.1")
             + contract.Money.parse("USD", "0.2")).minor_units
    if cents != 30:
        raise SystemExit("selftest: provider money parsing lost a cent to float")
    limited = fake.FakeProvider(capabilities=frozenset({contract.Capability.SUBMIT}))
    if not isinstance(limited.cancel("x"), contract.TypedError):
        raise SystemExit("selftest: adapter simulated an unsupported capability")
    if limited.normalize_status("mystery") != contract.ProviderStatus.UNKNOWN:
        raise SystemExit("selftest: adapter guessed an unknown provider status")
    timing_out = fake.FakeProvider()
    timing_out.script_submit("timeout")
    if not isinstance(timing_out.submit(fake.sample_submission()), contract.UnknownOutcome):
        raise SystemExit("selftest: adapter turned a submission timeout into a definite outcome")


def check_release_grammar() -> None:
    """The release script's tag validation, exercised without any
    network: exactly vN.x.y, and the composite action's command
    grammar rejects shell syntax."""

    import subprocess

    script = Path(__file__).resolve().parent.parent.parent / "scripts" / "release.sh"
    if not script.is_file():
        return  # installed wheel; the script ships with the repo only
    good = GOOD_TAGS
    bad = BAD_TAGS
    for tag in good:
        result = subprocess.run(["bash", str(script), "--check-tag", tag],
                                capture_output=True)
        if result.returncode != 0:
            raise SystemExit(f"selftest: release grammar rejected valid {tag!r}")
    for tag in bad:
        result = subprocess.run(["bash", str(script), "--check-tag", tag],
                                capture_output=True)
        if result.returncode == 0:
            raise SystemExit(f"selftest: release grammar accepted invalid {tag!r}")

    action = script.parent.parent / "action.yml"
    text = action.read_text(encoding="utf-8")
    if "${{ inputs.command }}" in text.split("env:")[-1].split("run:")[-1]:
        raise SystemExit(
            "selftest: action.yml interpolates inputs.command into shell text"
        )
    # The action's grammar, proven against the audit's injection string.
    import re as re_mod

    grammar = re_mod.compile(r"^[a-z][a-z0-9-]*( [A-Za-z0-9._/=-]+)*$")
    assert grammar.match("all")
    assert grammar.match("art accept art/candidates/cover-1.png --as=cover")
    assert not grammar.match("all; touch /tmp/pwned")
    assert not grammar.match("all && rm -rf .")
    assert not grammar.match("$(id)")


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
            '<html><head>\n<script type="application/ld+json">\n'
            '{"@type": "Book", "name": "Proof Book"}\n</script>\n</head>'
            '<body>Proof Book <a href="read/index.html">read</a> '
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
        # The audit's deliberate-damage pair: a dead fragment anchor and
        # a stylesheet url() pointing at nothing must both be findings.
        (pages / "index.html").write_text(
            '<html><body>Proof Book <a href="read/index.html">read</a> '
            '<a href="#missing-fragment">dead anchor</a> '
            '<a href="read/index.html#nowhere">dead cross-page</a> '
            '<a href="downloads/proof.pdf">pdf</a></body></html>',
            encoding="utf-8",
        )
        (pages / "reader.css").write_text(
            "body { background: url(missing.png); }", encoding="utf-8"
        )
        damaged = verify_pages.crawl(pages, ["sentinel phrase"], ["proof.pdf"], "Proof Book")
        assert any("missing-fragment" in f for f in damaged), damaged
        assert any("nowhere" in f for f in damaged), damaged
        assert any("missing.png" in f for f in damaged), damaged
        (pages / "reader.css").unlink()
        (pages / "index.html").write_text(
            '<html><head>\n<script type="application/ld+json">\n'
            '{"@type": "Book", "name": "Proof Book"}\n</script>\n</head>'
            '<body id="top">Proof Book <a href="#top">top</a> '
            '<a href="read/index.html">read</a> '
            '<a href="downloads/proof.pdf">pdf</a></body></html>',
            encoding="utf-8",
        )
        sound = verify_pages.crawl(pages, ["sentinel phrase"], ["proof.pdf"], "Proof Book")
        assert sound == [], sound


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
    # Builders and verifiers per artifact, stated here so the table
    # stays generated; a registry artifact this map does not name
    # fails the selftest instead of silently missing a row.
    builders = {
        "pdf": "build (pandoc + latexmk)", "epub": "build",
        "html": "build", "markdown": "build", "txt": "build",
        "docx": "build", "site": "build", "source": "package_source",
        "sources": "gen_authorities", "pages": "build",
        "print": "build (print profile)", "coverwrap": "gen_coverwrap",
    }
    verifiers = {
        "pdf": "verify_pdf", "epub": "verify_formats + epubcheck",
        "html": "verify_formats", "markdown": "verify_formats",
        "txt": "verify_formats", "docx": "verify_formats",
        "site": "verify_formats + verify_archives",
        "source": "verify_archives", "sources": "verify_archives",
        "pages": "verify_pages", "print": "verify_pdf (print profile)",
        "coverwrap": "verify_coverwrap",
    }
    destinations = {
        "pages": "deployed as the Pages site",
        "print": "GitHub Release when built (print pack)",
        "coverwrap": "GitHub Release when built (print pack)",
    }
    lines += [
        "",
        "## Builders, verifiers, and destinations",
        "",
        "| artifact | builder | verifier | publication destination |",
        "|---|---|---|---|",
    ]
    for a in registry.ARTIFACTS.values():
        if a.published:
            destination = "Pages downloads + GitHub Release"
            if a.condition:
                destination += f" (when {a.condition} configured)"
        else:
            destination = destinations[a.name]
        lines.append(
            f"| {a.name} | {builders[a.name]} | {verifiers[a.name]} | "
            f"{destination} |"
        )
    lines += ["", "## Targets", "", "```text", cli.USAGE.strip(), "```", ""]
    return "\n".join(lines)


def _repo_root() -> Path | None:
    """The source checkout root, or None when the press runs from an
    installed wheel. Checks that read repo files (contract mirror,
    invariant ledger, doc drift) prove nothing from an install and skip
    rather than crash, so `press selftest` works either way."""

    root = Path(__file__).resolve().parent.parent.parent
    return root if (root / "CLAUDE.md").is_file() else None


def check_contract_mirror() -> None:
    """AGENTS.md is a generated mirror of CLAUDE.md (same contract,
    agents.md convention): identical below the heading line, so the
    two cannot drift apart again."""

    root = _repo_root()
    if root is None:
        return
    claude = (root / "CLAUDE.md").read_text(encoding="utf-8")
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    if agents.split("\n", 1)[1] != claude.split("\n", 1)[1]:
        raise SystemExit(
            "AGENTS.md has drifted from CLAUDE.md; regenerate it "
            "(the body below the heading must be identical)"
        )


def check_command_catalog() -> None:
    """The CLI and the desk read one command catalog, so their surfaces
    cannot drift: every catalog command is dispatchable, every route is
    a catalog command, and the usage text is the catalog's own
    rendering."""

    from . import __main__ as cli, catalog

    routes = set(cli.ROUTES)
    formats = set(cli.FORMATS) | {"print"}
    for command in catalog.COMMANDS:
        target = command.alias_of or command.name
        if not (command.name in routes or command.name in formats
                or target in routes or target in formats):
            raise SystemExit(f"catalog command {command.name!r} is not dispatchable")
    known = catalog.canonical_targets()
    for route in routes:
        if route not in known:
            raise SystemExit(f"route {route!r} is not in the command catalog")
    if cli.USAGE != catalog.render_usage():
        raise SystemExit("cli.USAGE is not the catalog's rendering; regenerate it")


def check_docs() -> None:
    from . import __main__ as cli

    here = Path(__file__).resolve().parent
    readme = (here.parent.parent / "README.md")
    usage_words = set(re.findall(r"[a-z-]{2,}", cli.USAGE.split("usage:")[1]))
    routed = set(cli.ROUTES) | set(cli.FORMATS) | {"print"}
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
    invariants_doc = here.parent.parent / "docs" / "INVARIANTS.md"
    if invariants_doc.is_file() and invariants_doc.read_text(encoding="utf-8") != invariants.render():
        raise SystemExit(
            "docs/INVARIANTS.md drifted from quality/invariants.yaml; "
            "regenerate with `press selftest --write-docs`"
        )
    from . import qualification
    quals_doc = here.parent.parent / "docs" / "PROVIDER-QUALIFICATION.md"
    if quals_doc.is_file() and quals_doc.read_text(encoding="utf-8") != qualification.render():
        raise SystemExit(
            "docs/PROVIDER-QUALIFICATION.md drifted from quality/providers.yaml; "
            "regenerate with `press selftest --write-docs`"
        )


def check_invariant_ledger() -> None:
    """The invariant ledger validates: schema holds and every enforcer
    and proof it names resolves to a real function or fixture. The
    ledger is a repo file, not package data, so an installed wheel has
    nothing to validate here."""

    if not invariants.LEDGER.is_file():
        return
    invariants.validate(invariants.load())


def check_fixture_provenance() -> None:
    """Every checked-in regression fixture carries a provenance manifest
    entry, and no entry names a fixture that has left the tree."""

    from . import fixture_provenance

    fixture_provenance.check()


# The one ordered list of invariant checks. main() runs it and the
# pytest suite parametrizes over it, so the CLI and the test runner
# cannot disagree about which invariants the press proves.
CHECKS = [
    check_imports,
    check_arithmetic,
    check_slug_invariant,
    check_source_policy,
    check_pages_verifier,
    check_scaffold_neutrality,
    check_book_model,
    check_registry,
    check_format_witnesses,
    check_site_identity,
    check_authorities_ledger,
    check_honest_refusals,
    check_release_grammar,
    check_receipt_chain,
    check_edition_manifest,
    check_provider_qualification,
    check_commerce_config,
    check_commerce_release_gate,
    check_provider_contract,
    check_coverwrap_detectors,
    check_aesthetic_schema,
    check_contract_mirror,
    check_invariant_ledger,
    check_fixture_provenance,
    check_command_catalog,
    check_docs,
]


def main(argv: list[str] | None = None) -> int:
    if argv and "--write-docs" in argv:
        docs = Path(__file__).resolve().parent.parent.parent / "docs"
        docs.mkdir(parents=True, exist_ok=True)
        from . import qualification
        (docs / "REFERENCE.md").write_text(render_reference(), encoding="utf-8")
        (docs / "INVARIANTS.md").write_text(invariants.render(), encoding="utf-8")
        (docs / "PROVIDER-QUALIFICATION.md").write_text(
            qualification.render(), encoding="utf-8")
        print(f"wrote {docs / 'REFERENCE.md'}, {docs / 'INVARIANTS.md'}, "
              f"and {docs / 'PROVIDER-QUALIFICATION.md'}")
    for check in CHECKS:
        check()
    print(f"Selftest passed: {len(modules())} modules import, arithmetic agrees "
          "with the canonical examples, usage and README name every target")
    return 0
