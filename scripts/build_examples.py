#!/usr/bin/env python3
"""Build each example book's PDF and render page previews for the gallery.

The gallery on the docs site argues "same pipeline, only the config differs".
The strongest form of that argument is the actual output, so this script
builds every book under examples/ with the real pipeline and renders a couple
of its pages to images. build_site.py then puts the previews and the
downloadable PDF on each gallery card.

This needs the full toolchain (LuaLaTeX, pandoc, pdftoppm, pdfinfo), so it
runs inside the press-toolchain image in CI, not on the pandoc-only docs
runner. Its output goes to build/examples/<slug>/:

    <slug>.pdf        the whole book
    preview-1.jpg     an early page (the title page, or the first chapter)
    preview-2.jpg     a later page (body text; a chapter opening where there
                      is one, so a drop cap shows)
    pages.txt         the PDF's page count

A book that fails to build is reported and skipped, and the script exits
non-zero, so a broken example turns the docs deploy red rather than shipping a
gallery card with a dead download.

    python3 scripts/build_examples.py            # all examples
    python3 scripts/build_examples.py tidepool-field-notes ...  # a subset
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
OUT = ROOT / "build" / "examples"

# Render at a size that stays crisp on a card without bloating the page.
PREVIEW_DPI = "110"


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def _page_count(pdf: Path) -> int:
    info = _run(["pdfinfo", str(pdf)], cwd=pdf.parent)
    for line in info.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[1])
    return 0


def _render_page(pdf: Path, page: int, stem: Path) -> bool:
    result = _run(
        ["pdftoppm", "-jpeg", "-r", PREVIEW_DPI, "-f", str(page), "-l", str(page),
         "-singlefile", str(pdf), str(stem)],
        cwd=pdf.parent,
    )
    return result.returncode == 0 and stem.with_suffix(".jpg").is_file()


def build_example(book: Path) -> bool:
    """Build one example to a PDF and two page previews. True on success."""
    slug = book.name
    built = _run([sys.executable, "-m", "press", "pdf"], cwd=book)
    pdf = book / "dist" / f"{slug}.pdf"
    if built.returncode != 0 or not pdf.is_file():
        tail = (built.stdout + built.stderr).strip().splitlines()[-8:]
        print(f"FAIL {slug}:\n  " + "\n  ".join(tail))
        return False

    dest = OUT / slug
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(pdf, dest / f"{slug}.pdf")

    pages = _page_count(pdf)
    (dest / "pages.txt").write_text(f"{pages}\n", encoding="utf-8")

    # Three pages that span the book: the opening (a generated title page, or
    # the first chapter); an early interior page (past any front matter, so a
    # chapter opening and its drop cap show); and the last page (where the
    # index, also-by, or about-the-author matter lives). Deduped and clamped,
    # so a short book simply shows fewer.
    targets = sorted({1, min(3, pages), pages})
    ok = True
    for slot, page in enumerate(targets, start=1):
        ok = _render_page(pdf, page, dest / f"preview-{slot}") and ok
    if not ok:
        print(f"FAIL {slug}: PDF built but a preview did not render")
        return False

    made = " ".join(sorted(p.name for p in dest.iterdir()))
    print(f"ok   {slug}: {pages} pages -> {made}")
    return True


def main(argv: list[str]) -> int:
    wanted = set(argv)
    books = sorted(
        d for d in EXAMPLES.iterdir()
        if (d / "config" / "metadata.yaml").is_file()
        and (not wanted or d.name in wanted)
    )
    if not books:
        print("no matching example books under examples/")
        return 1
    # A clean slate, so a rerun never serves a stale or half-built preview.
    if not wanted and OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    results = [build_example(book) for book in books]
    built = sum(results)
    print(f"\n+ built {built}/{len(results)} example books -> {OUT.relative_to(ROOT)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
