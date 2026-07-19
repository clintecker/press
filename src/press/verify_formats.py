"""Verify non-PDF build artifacts contain the book and expected structure."""

from __future__ import annotations

import argparse
import html.parser
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from . import booklib


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
    return len(list((booklib.root() / "assets" / "woodcuts").glob("*.jpg")))


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

    if shutil.which("epubcheck") is None:
        # Strictness keys on the toolchain's own promise (PRESS_TOOLCHAIN,
        # set in the image), not the ambient CI variable: CI=false would
        # read truthy, and an image predating epubcheck must degrade to
        # this warning rather than fail every book while :latest catches up.
        if os.environ.get("PRESS_TOOLCHAIN"):
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
        result = subprocess.run(
            ["epubcheck", str(path)], capture_output=True, text=True
        )
    except OSError as exc:
        # A tool that exists but cannot execute (a container without
        # binfmt jar support, a broken wrapper) is a toolchain fault,
        # not an EPUB fault; say so instead of a traceback.
        raise SystemExit(f"epubcheck is present but cannot run ({exc}); "
                         "the toolchain image is broken") from exc
    if result.returncode != 0:
        raise SystemExit(
            f"epubcheck failed on {path} (exit {result.returncode}):\n"
            f"{result.stdout}{result.stderr}"
        )
    print(f"epubcheck passed: {path.name}")


def verify_plaintext(path: Path, label: str) -> None:
    text = " ".join(path.read_text(encoding="utf-8").split())
    for sentinel in booklib.sentinels():
        if not sentinel_present(sentinel, text):
            raise SystemExit(f"{label} missing sentinel: {sentinel}")
    require_witnesses(text, label)


def docx_visible_text(document: bytes) -> str:
    """The w:t node text, joined: what a reader sees, not the markup."""

    import xml.etree.ElementTree as ET

    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
    root_el = ET.fromstring(document)
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
        woodcuts = list((path / "assets" / "woodcuts").glob("*.jpg"))
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
    witness = manuscript_witness()
    print(
        f"Verified {', '.join(verified)} "
        f"({len(booklib.sentinels())} sentinel(s), the title, and the "
        f"manuscript line '{witness[:40]}...' as witnesses)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
