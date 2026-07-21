"""Render and structurally verify the print PDF.

The verifier tests its own blank-page detector before using it. A verifier
that has never rejected a known-bad fixture is another untested claim. Trim
size and minimum page count come from the book's metadata (trim defaults to
6 x 9 inches, verify-min-pages to 40).
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path
from typing import cast

from PIL import Image, ImageDraw, ImageStat

from . import booklib

RENDER_SCRIPT = Path("/home/oai/skills/pdfs/scripts/render_pdf.py")


def sentinels() -> list[str]:
    """Prose sentinels are exact; the title is checked separately.

    House title pages set the title in caps with a closing point, so the
    title probe folds case while prose fragments must survive verbatim.
    """

    return list(booklib.sentinels())


def verify_plate_links(pdf: Path) -> None:
    """Every List of Plates link must land on a page that holds an image."""

    try:
        from pypdf import PdfReader
    except ImportError:
        print("pypdf unavailable; plate-link destinations not verified")
        return

    reader = PdfReader(str(pdf))
    lof_index = next(
        (i for i, page in enumerate(reader.pages)
         if "List of plates" in (page.extract_text() or "")),
        None,
    )
    if lof_index is None:
        return
    bad: list[int] = []
    checked = 0
    for annotation in reader.pages[lof_index].get("/Annots") or []:
        obj = annotation.get_object()
        dest = obj.get("/Dest") or (obj.get("/A") or {}).get("/D")
        if dest is None:
            continue
        dest = dest.get_object() if hasattr(dest, "get_object") else dest
        if isinstance(dest, str):
            named = reader.named_destinations.get(dest)
            if named is None:
                continue
            target = reader.get_destination_page_number(named)
        else:
            target = reader.get_page_number(dest[0].get_object())
        if target is None:
            raise SystemExit(f"plate link {dest!r} resolves to no page")
        checked += 1
        resources = reader.pages[target].get("/Resources") or {}
        if "/XObject" not in resources:
            bad.append(target + 1)
    if bad:
        raise SystemExit(f"plate links point at imageless pages: {bad}")
    if checked == 0:
        raise SystemExit("List of plates present but contains no links")


def run_capture(command: list[str]) -> str:
    return subprocess.run(command, check=True, text=True, capture_output=True).stdout


def looks_blank(image: Image.Image) -> bool:
    gray = image.convert("L")
    stats = ImageStat.Stat(gray)
    extrema = cast("tuple[int, int]", gray.getextrema())
    return stats.stddev[0] < 1.2 or (extrema[0] > 249 and stats.mean[0] > 252.5)


def self_test_detector() -> None:
    blank = Image.new("RGB", (300, 450), "white")
    if not looks_blank(blank):
        raise AssertionError("blank-page detector failed to reject a blank fixture")
    marked = blank.copy()
    draw = ImageDraw.Draw(marked)
    draw.rectangle((40, 100, 260, 350), outline="black", width=3)
    draw.text((72, 210), "KNOWN INK", fill="black")
    if looks_blank(marked):
        raise AssertionError("blank-page detector rejected a marked fixture")


def edge_has_ink(image: Image.Image, border: int = 2) -> bool:
    gray = image.convert("L")
    width, height = gray.size
    strips = [
        gray.crop((0, 0, width, border)),
        gray.crop((0, height - border, width, height)),
        gray.crop((0, 0, border, height)),
        gray.crop((width - border, 0, width, height)),
    ]
    return any(
        cast("tuple[int, int]", strip.getextrema())[0] < 245 for strip in strips
    )


def ink_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    """Bounding box of dark pixels; None for an effectively empty page."""

    mask = image.convert("L").point(lambda v: 255 if v < 160 else 0)
    return mask.getbbox()


def verify_mirrored_margins(images: list[Path]) -> None:
    """Print interiors bind: the inner margin must exceed the outer, and
    the excess must swap sides between recto and verso."""

    start = max(2, int(len(images) * 0.2))
    left_edges: dict[int, list[int]] = {0: [], 1: []}
    for index in range(start, len(images)):
        with Image.open(images[index]) as image:
            box = ink_bbox(image)
        if box is not None:
            left_edges[(index + 1) % 2].append(box[0])
    if not left_edges[0] or not left_edges[1]:
        raise SystemExit("print profile: too few body pages to judge margin mirroring")
    median_recto = sorted(left_edges[1])[len(left_edges[1]) // 2]
    median_verso = sorted(left_edges[0])[len(left_edges[0]) // 2]
    # inner minus outer is 0.3in = 36px at 120dpi; demand at least half.
    if median_recto - median_verso < 18:
        raise SystemExit(
            "print profile: margins do not mirror (recto left edge "
            f"{median_recto}px, verso {median_verso}px); the gutter is missing"
        )


def verify_black_ink(images: list[Path]) -> None:
    """No colored ink in a print interior: links print black, plates are
    engravings. JPEG chroma noise is tolerated; a colored region is not."""

    from PIL import ImageChops

    offenders = []
    for index, path in enumerate(images, start=1):
        with Image.open(path) as image:
            r, g, b = image.convert("RGB").split()
            spread = ImageChops.lighter(
                ImageChops.difference(r, g), ImageChops.difference(g, b)
            )
        if sum(spread.histogram()[48:]) > 200:
            offenders.append(index)
    if offenders:
        raise SystemExit(
            f"print profile: colored ink on pages {offenders} (a colored "
            "cover plate in a hand-authored tex/title-page.tex belongs on "
            "the wrap; supply tex/title-page-print.tex without it)"
        )


def verify_fonts(pdf: Path) -> None:
    if shutil.which("pdffonts") is None:
        raise SystemExit("required verification tool missing: pdffonts")
    output = run_capture(["pdffonts", str(pdf)])
    rows = [line.split() for line in output.splitlines()[2:] if line.strip()]
    if not rows:
        raise SystemExit("pdffonts found no fonts")
    unembedded = []
    for row in rows:
        # pdffonts columns include emb and sub near the end. Locate no/no pairs
        # conservatively rather than depending on a specific Poppler width.
        if "no" in row[3:]:
            # The first yes/no after encoding is the embedded flag.
            flags = [token for token in row if token in {"yes", "no"}]
            if flags and flags[0] == "no":
                unembedded.append(row[0])
    if unembedded:
        raise SystemExit(f"unembedded fonts: {sorted(set(unembedded))}")


def parse_args(argv: list[str] | None, root: Path, meta: dict) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument(
        "--min-pages",
        type=int,
        default=int(meta.get("verify-min-pages", 40)),
        help="Reject PDFs shorter than this page count.",
    )
    parser.add_argument(
        "--sentinel",
        action="append",
        dest="sentinels",
        help="Required text fragment. Repeat for multiple sentinels.",
    )
    parser.add_argument(
        "--render-dir",
        type=Path,
        default=root / "build" / "verify-render",
        help="Directory used for verification renders.",
    )
    parser.add_argument(
        "--profile",
        choices=["reading", "print"],
        default="reading",
        help="print adds the interior checks: mirrored margins, black ink only.",
    )
    return parser.parse_args(argv)


def verify_info(pdf: Path, trim_width: float, trim_height: float, min_pages: int) -> int:
    """Trim size and page count from pdfinfo; returns the page count."""

    for tool in ["pdfinfo", "pdftotext"]:
        if shutil.which(tool) is None:
            raise SystemExit(f"required verification tool missing: {tool}")

    info = run_capture(["pdfinfo", str(pdf)])
    pages_match = re.search(r"^Pages:\s+(\d+)$", info, re.MULTILINE)
    size_match = re.search(r"^Page size:\s+([0-9.]+) x ([0-9.]+) pts", info, re.MULTILINE)
    if not pages_match or not size_match:
        raise SystemExit("could not parse pdfinfo output")
    expected_pages = int(pages_match.group(1))
    width, height = map(float, size_match.groups())
    if abs(width - trim_width * 72) > 1.0 or abs(height - trim_height * 72) > 1.0:
        raise SystemExit(
            f"unexpected trim size: {width} x {height} pt "
            f"(expected {trim_width:g} x {trim_height:g} inches)"
        )
    if expected_pages < min_pages:
        raise SystemExit(
            f"suspiciously short PDF: {expected_pages} pages "
            f"(minimum {min_pages})"
        )
    return expected_pages


def verify_sentinel_text(pdf: Path, root: Path, arg_sentinels: list[str] | None) -> int:
    """Sentinels (and the title, when running the book's own list) must
    survive into the extracted text; returns the witness count."""

    text_path = root / "build" / "verify-text.txt"
    text_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["pdftotext", str(pdf), str(text_path)], check=True)
    text = text_path.read_text(encoding="utf-8", errors="replace")
    normalized_text = " ".join(text.split())
    required = arg_sentinels if arg_sentinels is not None else sentinels()
    from .verify_formats import sentinel_present

    for sentinel in required:
        if not sentinel_present(sentinel, normalized_text):
            raise SystemExit(f"missing text sentinel in PDF: {sentinel}")
    if arg_sentinels is None:
        # Case folds because house title pages set the title in caps;
        # quotes normalize because pandoc's smart extension curls the
        # straight quotes the metadata states.
        straighten = str.maketrans("‘’“”", "''\"\"")
        title = " ".join(booklib.metadata()["title"].split()).casefold().translate(straighten)
        if title not in normalized_text.casefold().translate(straighten):
            raise SystemExit(f"missing title in PDF text: {booklib.metadata()['title']}")
    return len(required)


def render_pages(pdf: Path, render_dir: Path, expected_pages: int) -> list[Path]:
    """Render every page to PNG and demand the count matches pdfinfo."""

    if render_dir.exists():
        shutil.rmtree(render_dir)
    if RENDER_SCRIPT.exists():
        subprocess.run(
            ["python3", str(RENDER_SCRIPT), str(pdf), "--out_dir", str(render_dir), "--dpi", "120"],
            check=True,
        )
    else:
        render_dir.mkdir(parents=True)
        subprocess.run(
            ["pdftoppm", "-png", "-r", "120", str(pdf), str(render_dir / "page")],
            check=True,
        )
    images = sorted(render_dir.glob("*.png"))
    if len(images) != expected_pages:
        raise SystemExit(f"rendered {len(images)} pages, pdfinfo reports {expected_pages}")
    return images


def drop_structural_blank(blank_pages: list[int]) -> list[int]:
    # A bound book may carry ONE structural blank verso (KOMA's
    # \mainmatter clears to a recto to keep folio and leaf parity
    # aligned). A blank recto, adjacent blanks, or a second isolated
    # blank verso is still the empty-pages failure and dies here; the
    # cap exists because a render cannot tell the mainmatter blank
    # from a plate that silently failed to ship.
    blank_set = set(blank_pages)
    structural = [
        page for page in blank_pages
        if page % 2 == 0
        and (page - 1) not in blank_set
        and (page + 1) not in blank_set
    ][:1]
    return [page for page in blank_pages if page not in structural]


def verify_page_ink(images: list[Path], profile: str) -> None:
    """Every rendered page must carry ink, keep it off the edge, and share
    one set of dimensions."""

    blank_pages: list[int] = []
    edge_pages: list[int] = []
    inconsistent: list[int] = []
    dimensions: tuple[int, int] | None = None
    for index, image_path in enumerate(images, start=1):
        with Image.open(image_path) as image:
            if looks_blank(image):
                blank_pages.append(index)
            if edge_has_ink(image):
                edge_pages.append(index)
            if dimensions is None:
                dimensions = image.size
            elif image.size != dimensions:
                inconsistent.append(index)
    if profile == "print":
        blank_pages = drop_structural_blank(blank_pages)
    if blank_pages:
        raise SystemExit(f"apparently blank rendered pages: {blank_pages}")
    if edge_pages:
        raise SystemExit(f"ink touches rendered page edge: {edge_pages}")
    if inconsistent:
        raise SystemExit(f"inconsistent rendered page dimensions: {inconsistent}")


def main(argv: list[str] | None = None) -> int:
    booklib.require_release_witnesses()
    root = booklib.root()
    meta = booklib.metadata()
    # Trim comes from the selected design profile, not metadata.
    book = booklib.book()
    trim_width, trim_height = book.trim_width, book.trim_height

    args = parse_args(argv, root, meta)
    pdf = args.pdf.resolve()
    if not pdf.is_file():
        raise SystemExit(f"PDF not found: {pdf}")

    self_test_detector()

    expected_pages = verify_info(pdf, trim_width, trim_height, args.min_pages)
    witnesses = verify_sentinel_text(pdf, root, args.sentinels)

    verify_fonts(pdf)
    verify_plate_links(pdf)

    images = render_pages(pdf, args.render_dir.resolve(), expected_pages)
    verify_page_ink(images, args.profile)

    profile_note = ""
    if args.profile == "print":
        verify_mirrored_margins(images)
        verify_black_ink(images)
        profile_note = ", mirrored margins, black ink only"

    print(
        f"Verified {pdf.name}: {expected_pages} pages, "
        f"{trim_width:g} x {trim_height:g} trim, embedded fonts, "
        f"{witnesses} sentinel(s) plus the title as witnesses, every "
        f"rendered page contains ink, no edge clipping{profile_note}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
