"""Verify non-PDF build artifacts contain the book and expected structure."""

from __future__ import annotations

import argparse
import html.parser
import re
import zipfile
from pathlib import Path

from . import adapters, booklib


class VisibleText(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)



STRAIGHTEN = str.maketrans("\u2018\u2019\u201c\u201d", "''\"\"")


def normalized(text: str) -> str:
    return " ".join(text.split()).casefold().translate(STRAIGHTEN)


def sentinel_present(sentinel: str, text: str) -> bool:
    """Exact-case match with quotes straightened on both sides: pandoc's
    smart extension curls the straight quotes the config states."""

    needle = " ".join(sentinel.split()).translate(STRAIGHTEN)
    return needle in " ".join(text.split()).translate(STRAIGHTEN)


def manuscript_witness() -> str:
    """One long plain line of the manuscript, markup-free, that every
    format must carry: content survival proven even with an empty
    sentinel list."""

    best = ""
    for path in booklib.chapter_files():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if len(line) <= len(best) or len(line) < 40:
                continue
            if any(ch in line for ch in "*_`[]()<>\"'&#!|"):
                continue
            best = line
    return normalized(best)


def chapter_witnesses() -> dict[str, str]:
    """Each chapter's own longest markup-free line of 40+ characters.

    The per-chapter identity proof: a chapter whose witness is absent
    from a rendered surface is missing, and a witness appearing more
    than once is a duplicated or mis-mapped chapter. Chapters with no
    such line contribute nothing (and say so in the site check)."""

    witnesses: dict[str, str] = {}
    for path in booklib.chapter_files():
        best = ""
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if len(line) <= len(best) or len(line) < 40:
                continue
            if any(ch in line for ch in "*_`[]()<>\"'&#!|"):
                continue
            best = line
        if best:
            witnesses[path.name] = normalized(best)
    return witnesses


# A witness's fragment window: how many consecutive words make a fragment,
# and how far each fragment starts from the last. A witness "appears" in an
# edition when ANY of its fragments is a clean substring. Why fragments and
# not the whole line: two edition-specific extraction artifacts break a
# whole-line substring even though the content is present --
#   * a PDF's running head and foot (page number, book title, chapter title)
#     are injected into pdftotext's linear stream at every page boundary,
#     splitting a witness line that straddles a page;
#   * a DOCX glues a paragraph's first word to the previous paragraph's last
#     when their runs carry no separating space ("feast." + "I keep" ->
#     "feast.I keep"), corrupting the word at a witness's edge.
# Both damage only the fragments that overlap the seam; a long witness has
# many fragments, and any one clean fragment (a distinctive multi-word phrase
# that cannot appear by coincidence) proves the chapter's content survived.
# A genuinely dropped chapter has no fragment anywhere and fails.
_FRAGMENT_WORDS = 8
_FRAGMENT_STEP = 4


def _witness_fragments(witness: str) -> list[str]:
    """The distinctive sliding-window phrases of a normalized witness. A
    witness shorter than one window is itself the only fragment."""

    words = normalized(witness).split()
    if len(words) <= _FRAGMENT_WORDS:
        return [" ".join(words)] if words else []
    last = len(words) - _FRAGMENT_WORDS
    starts = list(range(0, last + 1, _FRAGMENT_STEP))
    if starts[-1] != last:
        starts.append(last)  # always include the tail window
    return [" ".join(words[i:i + _FRAGMENT_WORDS]) for i in starts]


def _chapter_present(witness: str, haystack: str) -> bool:
    """True if any distinctive fragment of the chapter's witness is a
    substring of the edition's normalized visible text."""

    return any(fragment and fragment in haystack for fragment in _witness_fragments(witness))


def verify_editions_agree(editions: dict[str, str], witnesses: dict[str, str]) -> None:
    """Hold the FULL per-chapter witness set against every edition at once.

    ``require_witnesses`` proves that *one* longest line per document
    survives; a format could drop every other line and still pass, the
    documented limit of INV-format-witness. This closes it: every chapter's
    own witness must appear in every edition's visible text, so a format that
    silently drops a chapter (or most of it) is caught by disagreeing with
    the editions that kept it.

    Pure and toolchain-free: it takes the already-extracted visible text of
    each edition (the caller runs pdftotext, unzips the EPUB, and so on) and
    the witness set, and raises a named refusal naming the edition and the
    chapters whose content it lost. "Appears" means a distinctive multi-word
    fragment of the witness is present, which survives a PDF's per-page
    furniture and a DOCX's paragraph-seam word-glue while still failing on a
    chapter whose words are actually gone. An empty witness set proves nothing
    here; ``require_witnesses`` already refuses a book that yields no witness.
    """

    if not witnesses:
        return
    for label in sorted(editions):
        haystack = normalized(editions[label])
        missing = sorted(
            chap for chap, witness in witnesses.items()
            if not _chapter_present(witness, haystack)
        )
        if missing:
            raise SystemExit(
                f"{label} disagrees with the manuscript: it is missing content "
                f"from {len(missing)} chapter(s) ({', '.join(missing)}); their "
                "witness lines appear in the other editions but not this one, so "
                "this format dropped content the rest of the book kept"
            )


def html_visible_text(path: Path) -> str:
    """The visible text of a single HTML file (script and style stripped)."""

    parser = VisibleText()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    return " ".join(" ".join(parser.parts).split())


def epub_visible_text(path: Path) -> str:
    """The visible text across every xhtml/html member of an EPUB."""

    with zipfile.ZipFile(path) as archive:
        raw = "\n".join(
            archive.read(name).decode("utf-8", errors="ignore")
            for name in archive.namelist()
            if name.endswith((".xhtml", ".html"))
        )
    parser = VisibleText()
    parser.feed(raw)
    return " ".join(" ".join(parser.parts).split())


def site_visible_text(path: Path) -> str:
    """The visible text aggregated across every page of the reader site."""

    aggregate = VisibleText()
    for page in sorted(path.glob("*.html")):
        aggregate.feed(page.read_text(encoding="utf-8", errors="replace"))
    return " ".join(" ".join(aggregate.parts).split())


def docx_file_text(path: Path) -> str:
    """The visible w:t text of a DOCX on disk."""

    with zipfile.ZipFile(path) as archive:
        with archive.open("word/document.xml") as handle:
            return docx_visible_text(handle.read())


def plaintext_text(path: Path) -> str:
    """A plain-text or markdown edition, whitespace-folded."""

    return " ".join(path.read_text(encoding="utf-8").split())


def pdf_visible_text(path: Path) -> str:
    """The visible text of a PDF via pdftotext, a poppler tool the toolchain
    carries. Soft hyphens and the hyphens LuaLaTeX inserts at a line break
    are healed so a witness word broken across two lines still matches: a
    hyphen immediately before a newline rejoins its word. The caller gates on
    pdftotext being present; here its absence or failure is a named refusal."""

    if adapters.environment.which("pdftotext") is None:
        raise SystemExit("pdftotext is not installed; cannot read the PDF edition")
    result = adapters.process_runner.run(
        ["pdftotext", str(path), "-"], capture=True, check=False
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise SystemExit(f"pdftotext failed on {path} (exit {result.returncode}): {stderr}")
    text = result.stdout.decode("utf-8", errors="replace")
    # Heal end-of-line hyphenation before whitespace folds the newline away,
    # so a word LuaLaTeX broke across a line is rejoined, not left split.
    text = re.sub(r"­", "", text)
    text = re.sub(r"-\n(?=\w)", "", text)
    return text


def gather_editions(
    *,
    html: Path | None = None,
    epub: Path | None = None,
    markdown: Path | None = None,
    text: Path | None = None,
    docx: Path | None = None,
    site: Path | None = None,
    pdf: Path | None = None,
) -> dict[str, str]:
    """The visible text of every built edition present, keyed by a label.

    The PDF is included only when pdftotext is available (the toolchain
    tier); every other edition is extracted with no external tool, so the
    cross-edition agreement check runs even in a bare authoring sandbox for
    the formats that need no toolchain.
    """

    editions: dict[str, str] = {}
    if html is not None and html.is_file():
        editions["HTML"] = html_visible_text(html)
    if epub is not None and epub.is_file():
        editions["EPUB"] = epub_visible_text(epub)
    if markdown is not None and markdown.is_file():
        editions["markdown"] = plaintext_text(markdown)
    if text is not None and text.is_file():
        editions["text"] = plaintext_text(text)
    if docx is not None and docx.is_file():
        editions["docx"] = docx_file_text(docx)
    if site is not None and site.is_dir():
        editions["reader site"] = site_visible_text(site)
    if pdf is not None and pdf.is_file() and adapters.environment.which("pdftotext"):
        editions["PDF"] = pdf_visible_text(pdf)
    return editions


def require_witnesses(text: str, label: str) -> None:
    """Title and manuscript witness, normalized, in every format. A
    manuscript that yields no witness line cannot prove content
    survival at all, which is a refusal, not a free pass."""

    haystack = normalized(text)
    title = normalized(booklib.book().title)
    if title and title not in haystack:
        raise SystemExit(f"{label} does not carry the book title: {booklib.book().title}")
    witness = manuscript_witness()
    if not witness:
        raise SystemExit(
            f"{label}: no manuscript witness derivable; the book has no "
            "markup-free line of 40+ characters, so content survival "
            "cannot be proven (write one honest plain sentence)"
        )
    if witness not in haystack:
        raise SystemExit(
            f"{label} lost the manuscript witness line: {witness[:60]}..."
        )


def plate_count() -> int:
    return len(booklib.plate_files(booklib.root() / "assets" / "woodcuts"))


def verify_html(path: Path) -> None:
    parser = VisibleText()
    parser.feed(path.read_text(encoding="utf-8"))
    text = " ".join(" ".join(parser.parts).split())
    for sentinel in booklib.sentinels():
        if not sentinel_present(sentinel, text):
            raise SystemExit(f"HTML missing sentinel: {sentinel}")
    if "<html" not in path.read_text(encoding="utf-8", errors="ignore").lower():
        raise SystemExit("HTML output has no html element")
    require_witnesses(text, "HTML")


def verify_epub(path: Path) -> None:
    from . import registrations

    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if "mimetype" not in names or archive.read("mimetype") != b"application/epub+zip":
            raise SystemExit("EPUB has invalid mimetype")
        if "META-INF/container.xml" not in names:
            raise SystemExit("EPUB missing container.xml")
        opf = "\n".join(
            archive.read(name).decode("utf-8", errors="ignore")
            for name in names if name.endswith(".opf")
        )
        if re.search(r"<dc:date[^>]*/>|<dc:date[^>]*>\s*</dc:date>", opf):
            raise SystemExit(
                "EPUB carries an empty dc:date (retail validators reject "
                "it); the date field should contain a four-digit year"
            )
        epub_isbn = registrations.isbn("epub")
        if epub_isbn and epub_isbn not in opf:
            raise SystemExit(
                f"EPUB metadata is missing the registered ISBN {epub_isbn}"
            )
        raw = "\n".join(
            archive.read(name).decode("utf-8", errors="ignore")
            for name in names
            if name.endswith((".xhtml", ".html"))
        )
        parser = VisibleText()
        parser.feed(raw)
        text = " ".join(" ".join(parser.parts).split())
        for sentinel in booklib.sentinels():
            if not sentinel_present(sentinel, text):
                raise SystemExit(f"EPUB missing sentinel: {sentinel}")
        require_witnesses(text, "EPUB")


def epubcheck(path: Path) -> None:
    """Validate the EPUB with epubcheck, the validator retail channels run.

    Retail channels reject invalid EPUBs, so the press must reject them
    first. The toolchain image carries epubcheck; an authoring sandbox may
    not (it needs a Java runtime).
    """

    if adapters.environment.which("epubcheck") is None:
        # Strictness keys on the toolchain's own promise (PRESS_TOOLCHAIN,
        # set in the image), not the ambient CI variable: CI=false would
        # read truthy, and an image predating epubcheck must degrade to
        # this warning rather than fail every book while :latest catches up.
        if adapters.environment.get("PRESS_TOOLCHAIN"):
            raise SystemExit(
                "epubcheck missing from the press toolchain image; the "
                "retail-format gate cannot be skipped where releases are cut"
            )
        print(
            "WARNING: epubcheck not installed; EPUB validated structurally "
            "only. The press toolchain runs the full check in CI. "
            "(brew install epubcheck)"
        )
        return
    try:
        result = adapters.process_runner.run(
            ["epubcheck", str(path)], capture=True
        )
    except OSError as exc:
        # A tool that exists but cannot execute (a container without
        # binfmt jar support, a broken wrapper) is a toolchain fault,
        # not an EPUB fault; say so instead of a traceback.
        raise SystemExit(f"epubcheck is present but cannot run ({exc}); "
                         "the toolchain image is broken") from exc
    if result.returncode != 0:
        # ProcessResult carries bytes (the runner never sets text=True);
        # decode so the diagnostic reproduces the captured epubcheck report.
        stdout = result.stdout.decode("utf-8", errors="replace")
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise SystemExit(
            f"epubcheck failed on {path} (exit {result.returncode}):\n"
            f"{stdout}{stderr}"
        )
    print(f"epubcheck passed: {path.name}")


def verify_plaintext(path: Path, label: str) -> None:
    text = " ".join(path.read_text(encoding="utf-8").split())
    for sentinel in booklib.sentinels():
        if not sentinel_present(sentinel, text):
            raise SystemExit(f"{label} missing sentinel: {sentinel}")
    require_witnesses(text, label)


def docx_visible_text(document: bytes) -> str:
    """The w:t node text, joined: what a reader sees, not the markup.

    Unparseable bytes yield the empty string, not an XML traceback: the
    caller's witness check then fails locatably on the missing text,
    which is the honest way a corrupt DOCX surfaces.
    """

    import xml.etree.ElementTree as ET

    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
    try:
        root_el = ET.fromstring(document)
    except ET.ParseError:
        return ""
    return " ".join("".join(node.text or "" for node in root_el.iter(w)).split())


def verify_docx(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        with archive.open("word/document.xml") as handle:
            document = handle.read()
        media = [name for name in archive.namelist() if name.startswith("word/media/")]
    # Visible text is the w:t nodes, not the raw markup: a sentinel
    # split across runs or containing markup-active characters used to
    # defeat a raw substring search.
    flattened = docx_visible_text(document)
    for sentinel in booklib.sentinels():
        if not sentinel_present(sentinel, flattened):
            raise SystemExit(f"docx missing sentinel: {sentinel}")
    require_witnesses(flattened, "docx")
    expected_plates = plate_count()
    if len(media) < expected_plates:
        raise SystemExit(
            f"docx embeds {len(media)} images; expected at least {expected_plates} plates"
        )


def verify_site(path: Path) -> None:
    index = path / "index.html"
    if not index.is_file():
        raise SystemExit("site missing index.html")
    if not (path / "reader.css").is_file():
        raise SystemExit("site missing reader.css")
    chapter_pages = [p for p in path.glob("*.html") if p.name != "index.html"]
    expected = len(booklib.chapter_files())
    if len(chapter_pages) < expected:
        raise SystemExit(
            f"site has {len(chapter_pages)} chapter pages; expected at least {expected}"
        )
    # Identity, chapter by chapter: each chapter's own witness line must
    # appear exactly once across the site, so a missing chapter, a
    # duplicated page, or another book's pages cannot pass on count.
    page_texts: dict[str, str] = {}
    for page in chapter_pages:
        parser = VisibleText()
        parser.feed(page.read_text(encoding="utf-8", errors="replace"))
        page_texts[page.name] = normalized(" ".join(parser.parts))
    for chapter, witness in chapter_witnesses().items():
        carriers = [name for name, text in page_texts.items() if witness in text]
        if not carriers:
            raise SystemExit(
                f"reader site is missing {chapter}: its witness line "
                f'"{witness[:50]}..." appears on no page'
            )
        if len(carriers) > 1:
            raise SystemExit(
                f"reader site duplicates {chapter}: its witness line "
                f"appears on {len(carriers)} pages ({', '.join(sorted(carriers))})"
            )
    source_plates = plate_count()
    if source_plates:
        woodcuts = booklib.plate_files(path / "assets" / "woodcuts")
        if len(woodcuts) < source_plates:
            raise SystemExit(f"site carries {len(woodcuts)} plates; expected {source_plates}")
    aggregate = VisibleText()
    for page in sorted(path.glob("*.html")):
        aggregate.feed(page.read_text(encoding="utf-8", errors="replace"))
    site_text = " ".join(" ".join(aggregate.parts).split())
    for sentinel in booklib.sentinels():
        if not sentinel_present(sentinel, site_text):
            raise SystemExit(f"reader site missing sentinel: {sentinel}")
    require_witnesses(site_text, "reader site")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    parser.add_argument("epub", type=Path)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--text", type=Path)
    parser.add_argument("--docx", type=Path)
    parser.add_argument("--site", type=Path)
    parser.add_argument("--pdf", type=Path)
    args = parser.parse_args(argv)
    booklib.require_release_witnesses()
    for path in [args.html, args.epub]:
        if not path.is_file() or path.stat().st_size < 1000:
            raise SystemExit(f"missing or suspicious artifact: {path}")
    verify_html(args.html)
    verify_epub(args.epub)
    epubcheck(args.epub)
    verified = [args.html.name, args.epub.name]
    if args.markdown:
        verify_plaintext(args.markdown, "markdown")
        verified.append(args.markdown.name)
    if args.text:
        verify_plaintext(args.text, "text")
        verified.append(args.text.name)
    if args.docx:
        verify_docx(args.docx)
        verified.append(args.docx.name)
    if args.site:
        verify_site(args.site)
        verified.append(args.site.name + "/")

    # Cross-edition agreement: every chapter's witness in every edition, so a
    # format that dropped content the others kept is caught, not passed. The
    # PDF joins the set where pdftotext is present (the toolchain tier).
    witnesses = chapter_witnesses()
    editions = gather_editions(
        html=args.html, epub=args.epub, markdown=args.markdown,
        text=args.text, docx=args.docx, site=args.site, pdf=args.pdf,
    )
    verify_editions_agree(editions, witnesses)

    witness = manuscript_witness()
    print(
        f"Verified {', '.join(verified)} "
        f"({len(booklib.sentinels())} sentinel(s), the title, and the "
        f"manuscript line '{witness[:40]}...' as witnesses); "
        f"{len(editions)} editions agree on all {len(witnesses)} chapter witnesses"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
