"""Verify the cover wrap as the retail object it is.

The interior has rendered-page, font, ink, and geometry verification;
the wrap had only a size check, so a TeX regression could ship a
right-sized but unusable retail artifact. This verifier proves the
wrap the way a printer would inspect it: one page at the exact
computed trim-plus-bleed-plus-spine size (recomputed from the same
functions the generator used, never restated), embedded fonts,
rendered ink, cover art actually on the front panel, the title
surviving as text, and a barcode (or its honest placeholder) present
on a white card with a real quiet zone, with the bars structurally
readable when an ISBN is declared.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageStat

from . import booklib, gen_coverwrap
from .verify_pdf import looks_blank, verify_fonts


def render(wrap: Path, out_dir: Path) -> Image.Image:
    subprocess.run(
        ["pdftoppm", "-png", "-r", "150", str(wrap), str(out_dir / "wrap")],
        check=True, capture_output=True,
    )
    rendered = sorted(out_dir.glob("wrap*.png"))
    if len(rendered) != 1:
        raise SystemExit(f"coverwrap rendered {len(rendered)} pages; a wrap is one")
    return Image.open(rendered[0])


def check_front_panel(image: Image.Image, front_x_in: float,
                      wrap_w: float) -> None:
    dpi = image.width / wrap_w
    front_x = int(front_x_in * dpi)
    front = image.crop((front_x, 0, image.width, image.height))
    if looks_blank(front):
        raise SystemExit("coverwrap front panel rendered blank; cover art missing")
    spread = ImageStat.Stat(front.convert("L")).stddev[0]
    if spread < 8:
        raise SystemExit(
            f"coverwrap front panel is flat (stddev {spread:.1f}); "
            "the cover art did not survive"
        )


def scanline(image: Image.Image, trim_w: float, wrap_w: float,
             isbn: str | None) -> None:
    """The barcode panel, inspected structurally: a white card with
    dark marks, and readable bar transitions plus quiet zones when an
    ISBN is declared."""

    dpi = image.width / wrap_w
    bleed = gen_coverwrap.BLEED_IN
    anchor_x = bleed + trim_w - 0.5
    anchor_y = bleed + 0.5
    x0 = max(0, int((anchor_x - 2.4) * dpi))
    x1 = int((anchor_x + 0.05) * dpi)
    y0 = image.height - int((anchor_y + 1.4) * dpi)
    y1 = image.height - int((anchor_y - 0.1) * dpi)
    region = image.crop((x0, y0, x1, y1)).convert("L")
    # tobytes() on an L-mode image is one byte per pixel in row order, the
    # same sequence getdata() returned (getdata is deprecated in Pillow 14).
    pixels = list(region.tobytes())
    if not any(value > 245 for value in pixels):
        raise SystemExit("coverwrap barcode panel has no white card")
    if not any(value < 70 for value in pixels):
        raise SystemExit("coverwrap barcode panel carries no marks at all")
    if isbn is None:
        return
    # Bars occupy local 0..0.9in above a card whose south edge sits
    # 0.32in below the anchor; sample mid-bar height.
    row_y = image.height - int((anchor_y + 0.32 + 0.45) * dpi) - y0
    band = region.crop((0, row_y, region.width, row_y + 1))
    row = [value < 128 for value in band.tobytes()]
    # The quiet zones are judged against where the symbol is SUPPOSED
    # to be (95 modules ending 0.15in inside the card's east edge, the
    # same numbers the generator laid down), never against observed
    # ink: a mark inside the zone must read as a violation, not as
    # more symbol.
    module = 0.0130
    symbol_right = int((2.4 - 0.15) * dpi)
    symbol_left = symbol_right - int(95 * module * dpi)
    window = row[max(0, symbol_left - 2):symbol_right + 2]
    transitions = sum(1 for a, b in zip(window, window[1:]) if a != b)
    if transitions < 25:
        raise SystemExit(
            f"coverwrap barcode is not structurally readable "
            f"({transitions} bar transitions on the scanline; EAN-13 has 59)"
        )
    left_zone = row[symbol_left - int(0.14 * dpi):symbol_left - int(0.02 * dpi)]
    right_zone = row[symbol_right + int(0.02 * dpi):symbol_right + int(0.14 * dpi)]
    for zone, side in ((left_zone, "left"), (right_zone, "right")):
        if any(zone):
            raise SystemExit(f"coverwrap barcode {side} quiet zone carries ink")


def main() -> int:
    root = booklib.root()
    slug = booklib.slug()
    wrap = root / "dist" / f"{slug}-coverwrap.pdf"
    interior = root / "dist" / f"{slug}-interior.pdf"
    if not wrap.is_file() or not interior.is_file():
        raise SystemExit("coverwrap or interior missing; build the print pack first")

    from pypdf import PdfReader

    reader = PdfReader(str(wrap))
    if len(reader.pages) != 1:
        raise SystemExit(f"coverwrap has {len(reader.pages)} pages; a wrap is one")

    meta = booklib.metadata()
    trim = meta.get("trim") or {}
    trim_w = float(trim.get("width", 6))
    pages = gen_coverwrap.interior_page_count(interior)
    # The generator's own geometry, so the verifier cannot disagree with it.
    lay = gen_coverwrap.layout(pages)
    wrap_w, wrap_h = lay.wrap_w, lay.wrap_h
    page = reader.pages[0]
    got_w = float(page.mediabox.width) / 72
    got_h = float(page.mediabox.height) / 72
    if abs(got_w - wrap_w) > 0.01 or abs(got_h - wrap_h) > 0.01:
        raise SystemExit(
            f"coverwrap is {got_w:.3f} x {got_h:.3f} in; the interior's "
            f"{pages} pages compute {wrap_w:.3f} x {wrap_h:.3f}"
        )

    verify_fonts(wrap)

    from .verify_formats import normalized

    text = normalized(" ".join(p.extract_text() or "" for p in reader.pages))
    title = normalized(str(meta["title"]))
    if title not in text:
        raise SystemExit(f"coverwrap lost the title text: {meta['title']}")

    with tempfile.TemporaryDirectory() as tmp:
        image = render(wrap, Path(tmp))
        if looks_blank(image):
            raise SystemExit("coverwrap rendered blank")
        check_front_panel(image, lay.front_x, wrap_w)
        scanline(image, trim_w, wrap_w, gen_coverwrap.isbn_for_print())

    isbn = gen_coverwrap.isbn_for_print()
    barcode_note = "EAN-13 readable with quiet zones" if isbn else "honest placeholder present"
    print(
        f"Verified {wrap.name}: one page, {wrap_w:.3f} x {wrap_h:.3f} in "
        f"({pages}-page spine), embedded fonts, front art present, title "
        f"survives, barcode: {barcode_note}"
    )
    return 0
