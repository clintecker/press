"""Verify non-PDF build artifacts contain the book and expected structure."""

from __future__ import annotations

import argparse
import html.parser
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


def plate_count() -> int:
    return len(list((booklib.root() / "assets" / "woodcuts").glob("*.jpg")))


def verify_html(path: Path) -> None:
    parser = VisibleText()
    parser.feed(path.read_text(encoding="utf-8"))
    text = " ".join(" ".join(parser.parts).split())
    for sentinel in booklib.sentinels():
        if " ".join(sentinel.split()) not in text:
            raise SystemExit(f"HTML missing sentinel: {sentinel}")
    if "<html" not in path.read_text(encoding="utf-8", errors="ignore").lower():
        raise SystemExit("HTML output has no html element")


def verify_epub(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if "mimetype" not in names or archive.read("mimetype") != b"application/epub+zip":
            raise SystemExit("EPUB has invalid mimetype")
        if "META-INF/container.xml" not in names:
            raise SystemExit("EPUB missing container.xml")
        raw = "\n".join(
            archive.read(name).decode("utf-8", errors="ignore")
            for name in names
            if name.endswith((".xhtml", ".html"))
        )
        parser = VisibleText()
        parser.feed(raw)
        text = " ".join(" ".join(parser.parts).split())
        for sentinel in booklib.sentinels():
            if " ".join(sentinel.split()) not in text:
                raise SystemExit(f"EPUB missing sentinel: {sentinel}")


def verify_plaintext(path: Path, label: str) -> None:
    text = " ".join(path.read_text(encoding="utf-8").split())
    for sentinel in booklib.sentinels():
        if sentinel not in text:
            raise SystemExit(f"{label} missing sentinel: {sentinel}")


def verify_docx(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        with archive.open("word/document.xml") as handle:
            document = handle.read().decode("utf-8", errors="replace")
        media = [name for name in archive.namelist() if name.startswith("word/media/")]
    flattened = " ".join(document.split())
    for sentinel in booklib.sentinels():
        if sentinel not in flattened:
            raise SystemExit(f"docx missing sentinel: {sentinel}")
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
    source_plates = plate_count()
    if source_plates:
        woodcuts = list((path / "assets" / "woodcuts").glob("*.jpg"))
        if len(woodcuts) < source_plates:
            raise SystemExit(f"site carries {len(woodcuts)} plates; expected {source_plates}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    parser.add_argument("epub", type=Path)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--text", type=Path)
    parser.add_argument("--docx", type=Path)
    parser.add_argument("--site", type=Path)
    args = parser.parse_args(argv)
    for path in [args.html, args.epub]:
        if not path.is_file() or path.stat().st_size < 1000:
            raise SystemExit(f"missing or suspicious artifact: {path}")
    verify_html(args.html)
    verify_epub(args.epub)
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
    print(f"Verified {', '.join(verified)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
