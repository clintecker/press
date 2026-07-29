"""The press checking itself: press selftest.

Documentation drift is a checker's job, not a promise (checkers over
conventions). This target fails when the CLI grows a target the usage
text or README does not name, when a documented target loses its route,
or when the arithmetic the pipeline trusts (ISBN, ISSN, EAN-13) stops
agreeing with the canonical examples. CI runs it on every push to the
press.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import invariants

from .selftest_book import (
    check_authorities_ledger,
    check_editions_agree,
    check_editorial_checkers,
    check_extension_conformance,
    check_format_witnesses,
    check_jargon_parity,
    check_registry,
    check_scaffold_neutrality,
    check_site_identity,
    check_slug_invariant,
    check_source_policy,
)
from .selftest_release import (
    check_command_catalog,
    check_commerce_config,
    check_commerce_release_gate,
    check_contract_mirror,
    check_docs,
    check_edition_manifest,
    check_migration,
    check_profile_seals,
    check_provider_contract,
    check_provider_qualification,
    check_receipt_chain,
    check_release_grammar,
)

GOOD_SLUGS = ("make-ready", "a", "book-2", "9lives")
BAD_SLUGS = (
    "../escape",
    "a/b",
    "a\\b",
    "A-Cap",
    "spa ce",
    "",
    "-lead",
    "dot.seg",
    "semi;colon",
    "tick`",
    "new\nline",
    "<tag>",
)


def clear_book_caches() -> None:
    """Every booklib cache emptied, so a borrowed or fixture book cannot
    leak into the caller's world through a memoized answer."""

    from . import booklib

    for cache in (booklib.root, booklib.metadata, booklib.book, booklib.house_rules):
        cache.cache_clear()


def borrow_book(path):
    """Point booklib at a fixture book, restoring the caller's world
    afterward: every cache cleared both ways, BOOK_ROOT restored to its
    prior value rather than deleted."""

    import contextlib

    from . import adapters

    @contextlib.contextmanager
    def borrowed():
        previous = adapters.environment.get("BOOK_ROOT")
        adapters.environment.set("BOOK_ROOT", str(path))
        clear_book_caches()
        try:
            yield
        finally:
            if previous is None:
                adapters.environment.unset("BOOK_ROOT")
            else:
                adapters.environment.set("BOOK_ROOT", previous)
            clear_book_caches()

    return borrowed()


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
        raise SystemExit(f"selftest: console() returned {code}, not the failing tool's 43")

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
                            f"selftest: metadata refusal {str(exc)!r} does not mention {wants!r}"
                        )
                else:
                    raise SystemExit(f"selftest: metadata content {content!r} was accepted")
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
                        "selftest: banned-pattern refusal does not name house-rules.yaml"
                    )
            else:
                raise SystemExit("selftest: malformed banned pattern was accepted")


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
    undocumented = sorted(key for key in consumed | house if key not in skill)
    if undocumented:
        raise SystemExit(
            "book-aesthetics.md does not document keys the aesthetic "
            f"engine consumes: {', '.join(undocumented)}"
        )
    for subkey in ("ink", "muted", "accent", "link"):
        if subkey not in skill:
            raise SystemExit(f"book-aesthetics.md omits the book-colors subkey {subkey!r}")


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
    front_x = bleed + trim_w + spine  # perfect-bound front-panel edge
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

    verify_coverwrap.scanline(
        barcode_image(22, False), bleed + trim_w, bleed, wrap_w, "9780306406157"
    )
    try:
        verify_coverwrap.scanline(Image.new("L", size, 180), bleed + trim_w, bleed, wrap_w, None)
    except SystemExit as exc:
        assert "white card" in str(exc), exc
    else:
        raise AssertionError("missing barcode card passed the wrap verifier")
    try:
        verify_coverwrap.scanline(
            barcode_image(3, False), bleed + trim_w, bleed, wrap_w, "9780306406157"
        )
    except SystemExit as exc:
        assert "transitions" in str(exc), exc
    else:
        raise AssertionError("threadbare barcode passed the wrap verifier")
    try:
        verify_coverwrap.scanline(
            barcode_image(22, True), bleed + trim_w, bleed, wrap_w, "9780306406157"
        )
    except SystemExit as exc:
        assert "quiet zone" in str(exc), exc
    else:
        raise AssertionError("ink in the quiet zone passed the wrap verifier")


# The release grammar's evidence, stated once for both runners.
GOOD_TAGS = ("v1.0.0", "v0.0.1", "v10.20.30")
BAD_TAGS = ("v1.0", "v1.0.0.0", "v1.0.0-rc1", "v1.0.0x", "v01.0.0", "1.0.0", "v1..0", "v1.0.0 ")


def check_book_model() -> None:
    """The typed model normalizes what has two spellings and refuses
    what the v1 design cannot honor, with locatable errors."""

    from . import bookmodel

    root = Path("/nowhere")
    minimal = {
        "title": "Proof",
        "author": "One Writer",
        "slug": "proof",
        "date": "First edition, 2026",
    }
    book = bookmodel.load(root, minimal)
    assert book.authors == ("One Writer",), "string author not normalized"
    assert book.year == "2026"
    assert (book.trim_width, book.trim_height) == (6.0, 9.0)

    listed = bookmodel.load(root, {**minimal, "author": ["A", "B"]})
    assert listed.authors == ("A", "B")

    # Trim now comes from the design profile: a metadata trim that disagrees
    # with the selected profile (here the default house 6 x 9) is refused.
    try:
        bookmodel.load(root, {**minimal, "trim": {"width": 5, "height": 8}})
    except SystemExit as exc:
        assert "print.profile" in str(exc) and "5 x 8" in str(exc), exc
    else:
        raise AssertionError("metadata trim disagreeing with the profile accepted")

    # Selecting a different design profile changes the trim -- the whole point
    # of the v2 unlock. The house profile stays 6 x 9.
    novella = bookmodel.load(root, {**minimal, "print": {"profile": "novella-5x8"}})
    assert (novella.trim_width, novella.trim_height) == (5.0, 8.0), "profile trim ignored"

    try:
        bookmodel.load(root, {"title": "", "author": [], "slug": "Bad Slug"})
    except SystemExit as exc:
        message = str(exc)
        assert "metadata.yaml" in message
        assert "title" in message and "author" in message and "slug" in message.lower()
    else:
        raise AssertionError("defective configuration accepted")


def check_pages_verifier() -> None:
    """The pages crawler must reject a broken site and pass a sound one."""

    import tempfile

    from . import verify_pages

    with tempfile.TemporaryDirectory() as tmp:
        pages = Path(tmp)
        (pages / "read").mkdir()
        (pages / "downloads").mkdir()
        (pages / "downloads" / "proof.pdf").write_text("x", encoding="utf-8")
        head = (
            '<meta property="og:title" content="Proof Book">\n'
            '<meta name="twitter:card" content="summary_large_image">\n'
            '<script type="application/ld+json">\n'
            '{"@type": "Book", "name": "Proof Book"}\n</script>\n'
        )
        (pages / "index.html").write_text(
            f"<html><head>\n{head}</head>"
            '<body>Proof Book <a href="read/index.html">read</a> '
            '<a href="downloads/proof.pdf">pdf</a></body></html>',
            encoding="utf-8",
        )
        (pages / "read" / "index.html").write_text(
            f"<html><head>\n{head}</head><body>the sentinel phrase lives here</body></html>",
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
            f"<html><head>\n{head}</head>"
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
        "pdf": "build (pandoc + latexmk)",
        "epub": "build",
        "html": "build",
        "markdown": "build",
        "txt": "build",
        "docx": "build",
        "site": "build",
        "source": "package_source",
        "sources": "gen_authorities",
        "pages": "build",
        "print": "build (print profile)",
        "coverwrap": "gen_coverwrap",
    }
    verifiers = {
        "pdf": "verify_pdf",
        "epub": "verify_formats + epubcheck",
        "html": "verify_formats",
        "markdown": "verify_formats",
        "txt": "verify_formats",
        "docx": "verify_formats",
        "site": "verify_formats + verify_archives",
        "source": "verify_archives",
        "sources": "verify_archives",
        "pages": "verify_pages",
        "print": "verify_pdf (print profile)",
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
        lines.append(f"| {a.name} | {builders[a.name]} | {verifiers[a.name]} | {destination} |")
    lines += ["", "## Targets", "", "```text", cli.USAGE.strip(), "```", ""]
    return "\n".join(lines)


def _repo_root() -> Path | None:
    """The source checkout root, or None when the press runs from an
    installed wheel. Checks that read repo files (contract mirror,
    invariant ledger, doc drift) prove nothing from an install and skip
    rather than crash, so `press selftest` works either way."""

    root = Path(__file__).resolve().parent.parent.parent
    return root if (root / "CLAUDE.md").is_file() else None


def _jargon_impl_paths() -> tuple[Path, Path]:
    """The two jargon checker sources: the package copy press check runs,
    and the portable skill copy an author can run without the package."""

    package = Path(__file__).resolve().parent
    package_copy = package / "jargon_lint.py"
    skill_copy = package / "data" / "skills" / "overused-jargon" / "scripts" / "jargon_lint.py"
    return package_copy, skill_copy


def _jargon_shared_defs(source: str) -> dict[str, str]:
    """Top-level function and class source, keyed by name, minus parse_args
    (whose only sanctioned difference is how each copy finds its default
    watchlist) and diagnostics_for (the package-only in-process seam
    celebrimbor's known_bad gate calls; it is not part of the portable skill)."""

    import ast

    skip = {"parse_args", "diagnostics_for"}
    defs: dict[str, str] = {}
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name not in skip:
            segment = ast.get_source_segment(source, node)
            defs[node.name] = segment or ""
    return defs


# The one ordered list of invariant checks. main() runs it and the
# pytest suite parametrizes over it, so the CLI and the test runner
# cannot disagree about which invariants the press proves.
CHECKS = [
    check_arithmetic,
    check_slug_invariant,
    check_jargon_parity,
    check_source_policy,
    check_pages_verifier,
    check_scaffold_neutrality,
    check_book_model,
    check_registry,
    check_format_witnesses,
    check_editions_agree,
    check_editorial_checkers,
    check_site_identity,
    check_authorities_ledger,
    check_honest_refusals,
    check_release_grammar,
    check_receipt_chain,
    check_edition_manifest,
    check_provider_qualification,
    check_profile_seals,
    check_commerce_config,
    check_commerce_release_gate,
    check_provider_contract,
    check_coverwrap_detectors,
    check_aesthetic_schema,
    check_contract_mirror,
    check_migration,
    check_extension_conformance,
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
        (docs / "PROVIDER-QUALIFICATION.md").write_text(qualification.render(), encoding="utf-8")
        # The packaged provider record is a generated projection of the one
        # canonical ledger (quality/providers.yaml), not a hand-kept mirror.
        qualification.PACKAGED_RECORD.write_text(qualification.render_packaged(), encoding="utf-8")
        print(
            f"wrote {docs / 'REFERENCE.md'}, {docs / 'INVARIANTS.md'}, "
            f"{docs / 'PROVIDER-QUALIFICATION.md'}, and "
            f"{qualification.PACKAGED_RECORD}"
        )
    for check in CHECKS:
        check()
    print(
        f"Selftest passed: {len(CHECKS)} checks, arithmetic agrees "
        "with the canonical examples, usage and README name every target"
    )
    return 0
