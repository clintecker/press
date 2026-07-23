#!/usr/bin/env python3
"""Generate a typographic cover for an example book, in the book's palette.

An interior prints in a single ink, so the example gallery's page previews are
one colour on paper -- honest, but the accent each book defines never shows.
A cover is different: it is allowed full colour. This draws a plain, editorial
cover from the book's own palette -- an accent field carrying the title, the
paper and ink below it -- so the colours the gallery names are the colours you
see on the shelf, and each example reads as a real book rather than a naked
text block.

No imagery, only type and colour: nothing here needs an image model, so the
cover regenerates from config on every build and cannot drift. It writes
``assets/cover.jpg``; the press picks it up as the cover plate.

    python3 scripts/gen_cover.py <example-dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Where to look for a usable serif face, by the book's pdf-family first and
# then a dependable fallback. Covers both the toolchain image (texlive/system
# fonts) and a local macOS run, so a cover renders in either place.
_FONT_DIRS = [
    "/usr/share/texlive/texmf-dist/fonts/opentype",
    "/usr/share/texmf/fonts/opentype",
    "/usr/share/fonts",
    "/Library/Fonts",
    "/System/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
    str(Path.home() / "Library" / "texmf" / "fonts" / "opentype"),
]
# pdf-family -> file stems to look for, then the always-present fallbacks.
_FAMILY_FILES = {
    "Libertinus Serif": ["LibertinusSerif-Regular"],
    "EB Garamond": ["EBGaramond-Regular"],
    "Erewhon": ["Erewhon-Regular"],
    "Latin Modern Roman": ["lmroman10-regular"],
}
_FALLBACK_STEMS = ["LibertinusSerif-Regular", "Georgia", "Times New Roman", "DejaVuSerif"]


def _find_font_file(family: str) -> str | None:
    stems = _FAMILY_FILES.get(family, []) + _FALLBACK_STEMS
    for stem in stems:
        for root in _FONT_DIRS:
            base = Path(root)
            if not base.is_dir():
                continue
            for ext in (".otf", ".ttf", ".ttc"):
                hit = next(base.rglob(f"{stem}{ext}"), None)
                if hit:
                    return str(hit)
    return None


def _font(path: str | None, size: int) -> ImageFont.FreeTypeFont:
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    # Pillow's stub types load_default as a union; at runtime (Pillow 10+) it
    # returns a sized FreeTypeFont, which is all the caller uses.
    return ImageFont.load_default(size)  # type: ignore[return-value]


def _hex(colour: str) -> tuple[int, int, int]:
    c = colour.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (v / 255 for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
          max_w: int) -> list[str]:
    words, lines, line = text.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _centered_block(draw: ImageDraw.ImageDraw, lines: list[str],
                    font: ImageFont.FreeTypeFont, cx: int, top: int,
                    fill: tuple[int, int, int], leading: float = 1.16) -> int:
    ascent, descent = font.getmetrics()
    line_h = int((ascent + descent) * leading)
    y = top
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text((cx - w / 2, y), line, font=font, fill=fill)
        y += line_h
    return y


def make_cover(dest: Path, *, title: str, subtitle: str, author: str,
               imprint: str, paper: str, ink: str, accent: str,
               font_family: str = "") -> None:
    """Draw a 2:3 typographic cover and write it as JPEG to ``dest``."""
    W, H = 1200, 1800
    pap, ic, ac = _hex(paper), _hex(ink), _hex(accent)
    # Text on the accent field is white or near-black by contrast, so a light
    # accent still reads.
    on_accent = (250, 250, 248) if _luminance(ac) < 0.6 else (26, 22, 18)

    img = Image.new("RGB", (W, H), pap)
    d = ImageDraw.Draw(img)

    # The book's own face where it can be found, a serif fallback otherwise.
    font_file = _find_font_file(font_family)
    title_f = _font(font_file, 118)
    sub_f = _font(font_file, 52)
    author_f = _font(font_file, 54)
    imprint_f = _font(font_file, 34)

    margin = 96
    inner = W - 2 * margin

    # The accent field: the top of the cover, carrying the title. This is where
    # the book's accent colour does its work.
    band_h = int(H * 0.46)
    d.rectangle([0, 0, W, band_h], fill=ac)
    # A thin rule of the ink under the band ties the two colours together.
    d.rectangle([0, band_h, W, band_h + 10], fill=ic)

    title_lines = _wrap(d, title, title_f, inner)
    ta, td = title_f.getmetrics()
    t_line_h = int((ta + td) * 1.1)
    t_block_h = t_line_h * len(title_lines)
    _centered_block(d, title_lines, title_f, W // 2,
                    (band_h - t_block_h) // 2 - 10, on_accent, leading=1.1)

    # Below the band, on the book's paper: subtitle, then author and imprint.
    y = band_h + 90
    if subtitle:
        sub_lines = _wrap(d, subtitle, sub_f, inner)
        y = _centered_block(d, sub_lines, sub_f, W // 2, y, ic, leading=1.2)

    # A short accent rule as a divider above the author.
    rule_w = 150
    d.rectangle([(W - rule_w) // 2, H - 360, (W + rule_w) // 2, H - 356], fill=ac)

    if author:
        _centered_block(d, _wrap(d, author, author_f, inner), author_f,
                        W // 2, H - 320, ic)
    if imprint:
        w = d.textlength(imprint.upper(), font=imprint_f)
        d.text((W // 2 - w / 2, H - 150), imprint.upper(), font=imprint_f,
               fill=ic, features=None)

    # A hairline frame in the ink, for a finished edge.
    d.rectangle([30, 30, W - 30, H - 30], outline=ic, width=3)

    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, "JPEG", quality=90)


def _read(meta: str, key: str) -> str:
    import re
    m = re.search(rf'^{key}:[ \t]*(.+)$', meta, re.M)
    if not m:
        return ""
    v = m.group(1).strip()
    return v.strip('"').strip("'") if v not in (">-", "|", ">") else ""


def _read_indented(text: str, key: str) -> str:
    import re
    m = re.search(rf'^[ \t]+{key}:[ \t]*"?(#?[^"\n]+)"?[ \t]*$', text, re.M)
    return m.group(1).strip().strip('"') if m else ""


def _first_author(meta: str) -> str:
    import re
    m = re.search(r'^author:[ \t]*\n[ \t]+-[ \t]*(.+)$', meta, re.M)
    return m.group(1).strip().strip('"') if m else ""


def cover_for(book: Path, dest: Path) -> str:
    """Read one example's identity and palette and draw its cover to ``dest``.
    Returns the accent colour used, for logging."""
    meta = (book / "config" / "metadata.yaml").read_text(encoding="utf-8")
    aesthetic_file = book / "config" / "aesthetic.yaml"
    aesthetic = aesthetic_file.read_text(encoding="utf-8") if aesthetic_file.exists() else ""
    accent = _read_indented(aesthetic, "accent") or "#8a2b1f"
    make_cover(
        dest,
        title=_read(meta, "title"),
        subtitle=_read(meta, "subtitle"),
        author=_first_author(meta),
        imprint=_read(meta, "publisher"),
        paper=_read_indented(aesthetic, "paper") or "#f4f4f1",
        ink=_read_indented(aesthetic, "ink") or "#1b1b1b",
        accent=accent,
        font_family=_read_indented(aesthetic, "pdf-family"),
    )
    return accent


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: gen_cover.py <example-dir> [dest.jpg]")
        return 1
    book = Path(argv[0])
    dest = Path(argv[1]) if len(argv) > 1 else book / "assets" / "cover.jpg"
    accent = cover_for(book, dest)
    print(f"wrote {dest}  ({accent} accent field)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
