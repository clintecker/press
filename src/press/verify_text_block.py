"""The PDF text block: no body page inks past the measure (INV-pdf-text-block).

The measure is the build's own geometry, read from the design profile (the
reading PDF) and the print header (the bound interior), never sampled from
the pages, so a ragged book and a two-page book are judged alike. The ink
primitives the page verifiers share (``ink_bbox``, ``body_start``) live here
too, so ``verify_pdf`` depends on this module and never the other way round.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from PIL import Image

from . import booklib, profiles


def ink_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    """Bounding box of dark pixels; None for an effectively empty page."""

    mask = image.convert("L").point(lambda v: 255 if v < 160 else 0)
    return mask.getbbox()


def body_start(images: list[Path]) -> int:
    """Index of the first body page when the PDF states none: the first 20
    percent of a book (and never fewer than two pages) is taken to be cover,
    title, and front matter."""

    return max(2, int(len(images) * 0.2))


def first_body_index(pdf: Path) -> int | None:
    """Index of the first page whose label is arabic (folio 1 of the main
    matter); None when the PDF carries no such label. The house numbers
    front matter in roman, so this is exactly where the Contents ends."""

    from pypdf import PdfReader

    reader = PdfReader(pdf)
    # pypdf invents decimal labels for a PDF without /PageLabels; those say
    # nothing about where the front matter ends.
    if "/PageLabels" not in cast("dict", reader.trailer["/Root"]):
        return None
    return next((i for i, label in enumerate(reader.page_labels) if label.isdigit()), None)


# The running head and the folio sit outside the text block; a page is judged
# on its middle 84 percent. An overrun of more than TEXT_BLOCK_SLACK px at the
# 120 dpi render (0.05in) is ink past the measure, not antialiasing or a
# protruded punctuation mark.
TEXT_BLOCK_BAND = 0.08
TEXT_BLOCK_SLACK = 6
PRINT_HEADER = booklib.DATA / "tex" / "print-header.tex"

# (trim width in inches, right margin in inches per measure class)
Geometry = tuple[float, dict[int, float]]


def _measure_class(index: int, profile: str) -> int:
    """Pages that share a measure: recto (1) and verso (0) in a bound print
    interior whose gutter shifts the block, one class (0) otherwise."""

    return (index + 1) % 2 if profile == "print" else 0


def print_margins() -> tuple[float, float]:
    """(inner, outer) in inches of the print interior, read from the
    print-header.tex the print build includes last: its ``\\geometry`` line
    overrides the design profile's inner and outer for every print book."""

    text = PRINT_HEADER.read_text(encoding="utf-8")
    match = re.search(r"\\geometry\{inner=([\d.]+)in,outer=([\d.]+)in\}", text)
    if match is None:
        raise SystemExit(f"{PRINT_HEADER.name} states no inner/outer geometry")
    return float(match.group(1)), float(match.group(2))


def text_block_geometry(profile: str, design: profiles.Profile | None = None) -> Geometry:
    """The text block's right edge as the build sets it: the design profile's
    trim, and its right margin per measure class. The reading PDF is
    one-sided, so every page's right margin is the profile's outer; a print
    recto's right margin is the print header's outer and a verso's its
    inner (the gutter swaps sides)."""

    design = design or profiles.active()
    width, _height = design.trim
    if profile == "print":
        inner, outer = print_margins()
        right = {1: outer, 0: inner}
    else:
        right = {0: design.margins["outer"]}
    if not all(0 < margin < width for margin in right.values()):
        raise SystemExit(
            f"{design.id}: right margins {sorted(right.values())}in leave no text block "
            f"on a {width:g}in page"
        )
    return width, right


def text_block_right(
    images: list[Path], profile: str, geometry: Geometry | None = None
) -> dict[int, int]:
    """The text block's right edge in render pixels per measure class,
    scaled from the geometry by the rendered page width (so the render dpi
    never needs restating)."""

    trim_width, right_margins = geometry or text_block_geometry(profile)
    with Image.open(images[0]) as image:
        width = image.width
    scale = width / trim_width
    return {cls: round(width - margin * scale) for cls, margin in right_margins.items()}


def text_block_overruns(
    images: list[Path], profile: str, start: int | None = None, geometry: Geometry | None = None
) -> list[tuple[int, int]]:
    """(page number, px past the text block) for every inked body page from
    index ``start`` (default body_start); negative when the ink stops short,
    as ragged verse and code do. The running-head and folio bands are
    cropped away first."""

    measure = text_block_right(images, profile, geometry)
    first = body_start(images) if start is None else start
    overruns: list[tuple[int, int]] = []
    for index in range(first, len(images)):
        with Image.open(images[index]) as image:
            width, height = image.size
            band = int(height * TEXT_BLOCK_BAND)
            box = ink_bbox(image.crop((0, band, width, height - band)))
        if box is not None:
            overruns.append((index + 1, box[2] - measure[_measure_class(index, profile)]))
    return overruns


def verify_text_block(
    images: list[Path], profile: str, start: int | None = None, geometry: Geometry | None = None
) -> None:
    """No body page inks past the text block: a code line or table cell that
    will not break runs into the margin, and a reader sees it cut or cramped
    against the trim. The measure is the build's own geometry, not a sample
    of the pages, so a ragged book and a two-page book are judged alike.
    Front matter (pages before ``start``, which main reads from the PDF's
    page labels) and the running-head and folio bands are not judged.
    Limitation: the raster cannot tell a deliberately outset figure from
    overflowing text, so such a figure is refused too; the house caps
    figures at the line width."""

    for page, overrun in text_block_overruns(images, profile, start, geometry):
        if overrun > TEXT_BLOCK_SLACK:
            raise SystemExit(
                f"{profile} profile: page {page} runs {overrun} px past the text block"
            )
