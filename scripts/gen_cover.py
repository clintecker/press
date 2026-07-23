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


class _Cover:
    """The drawing surface and everything a grammar needs, so each grammar is
    just a layout of a shared vocabulary (title, rules, colophon, imprint)."""

    def __init__(self, dest_size: tuple[int, int], paper: str, ink: str,
                 accent: str, font_file: str | None, title: str, subtitle: str,
                 author: str, imprint: str) -> None:
        self.W, self.H = dest_size
        self.pap, self.ic, self.ac = _hex(paper), _hex(ink), _hex(accent)
        # Text laid on the accent field is light or near-black by contrast.
        self.on_ac = (250, 250, 248) if _luminance(self.ac) < 0.62 else (24, 20, 16)
        self.font_file = font_file
        self.title, self.subtitle = title, subtitle
        self.author, self.imprint = author, imprint
        self.margin = 100
        self.inner = self.W - 2 * self.margin
        self.img = Image.new("RGB", (self.W, self.H), self.pap)
        self.d = ImageDraw.Draw(self.img)

    def title_block(self, top: int, colour: tuple[int, int, int], size: int,
                    region_h: int | None = None) -> int:
        f = _font(self.font_file, size)
        lines = _wrap(self.d, self.title, f, self.inner)
        a, de = f.getmetrics()
        line_h = int((a + de) * 1.08)
        y = top if region_h is None else top + (region_h - line_h * len(lines)) // 2
        return _centered_block(self.d, lines, f, self.W // 2, y, colour, leading=1.08)

    def text_block(self, top: int, text: str, size: int,
                   colour: tuple[int, int, int]) -> int:
        if not text:
            return top
        f = _font(self.font_file, size)
        return _centered_block(self.d, _wrap(self.d, text, f, self.inner), f,
                               self.W // 2, top, colour, leading=1.2)

    def rule(self, y: int, colour: tuple[int, int, int], width: int = 150,
             thick: int = 4) -> None:
        self.d.rectangle([(self.W - width) // 2, y, (self.W + width) // 2, y + thick],
                         fill=colour)

    def colophon(self, cy: int, colour: tuple[int, int, int]) -> None:
        skip = {"and", "the", "of", "for", "&", "a"}
        initials = "".join(
            w[0] for w in self.imprint.split()
            if w[:1].isalpha() and w.lower() not in skip
        )[:3].upper()
        if not initials:
            return
        r, cx = 46, self.W // 2
        self.d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=colour, width=4)
        f = _font(self.font_file, 36)
        bb = self.d.textbbox((0, 0), initials, font=f)
        self.d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]),
                    initials, font=f, fill=colour)

    def imprint_line(self, y: int, colour: tuple[int, int, int]) -> None:
        if not self.imprint:
            return
        f = _font(self.font_file, 34)
        w = self.d.textlength(self.imprint.upper(), font=f)
        self.d.text((self.W // 2 - w / 2, y), self.imprint.upper(), font=f, fill=colour)

    def frame(self, colour: tuple[int, int, int], inset: int = 30,
              width: int = 3) -> None:
        self.d.rectangle([inset, inset, self.W - inset, self.H - inset],
                         outline=colour, width=width)

    def colophon_stack(self, colour_mark: tuple[int, int, int],
                       colour_text: tuple[int, int, int]) -> None:
        """The recurring bottom stack: author, colophon mark, imprint."""
        if self.author:
            self.text_block(self.H - 390, self.author, 54, colour_text)
        self.colophon(self.H - 250, colour_mark)
        self.imprint_line(self.H - 140, colour_text)


def _g_band(cv: _Cover) -> None:
    """An accent field across the top carries the title; paper below."""
    band_h = int(cv.H * 0.46)
    cv.d.rectangle([0, 0, cv.W, band_h], fill=cv.ac)
    cv.d.rectangle([0, band_h, cv.W, band_h + 10], fill=cv.ic)
    cv.title_block(0, cv.on_ac, 116, region_h=band_h)
    cv.text_block(band_h + 90, cv.subtitle, 52, cv.ic)
    cv.rule(cv.H - 430, cv.ac)
    cv.colophon_stack(cv.ac, cv.ic)
    cv.frame(cv.ic)


def _g_full(cv: _Cover) -> None:
    """The whole cover is the accent colour; all type reversed out of it."""
    cv.d.rectangle([0, 0, cv.W, cv.H], fill=cv.ac)
    by = cv.title_block(int(cv.H * 0.22), cv.on_ac, 122)
    cv.rule(by + 44, cv.on_ac, width=120)
    cv.text_block(by + 90, cv.subtitle, 50, cv.on_ac)
    cv.colophon_stack(cv.on_ac, cv.on_ac)
    cv.frame(cv.on_ac, inset=34, width=2)


def _g_framed(cv: _Cover) -> None:
    """Paper field inside a broad accent border; title in ink."""
    cv.d.rectangle([0, 0, cv.W, cv.H], outline=cv.ac, width=48)
    by = cv.title_block(int(cv.H * 0.27), cv.ic, 108)
    cv.rule(by + 46, cv.ac)
    cv.text_block(by + 92, cv.subtitle, 50, cv.ic)
    cv.colophon_stack(cv.ac, cv.ic)


def _g_stack(cv: _Cover) -> None:
    """Austere: the title set between two heavy accent rules, much air."""
    top = int(cv.H * 0.29)
    cv.rule(top, cv.ac, width=cv.inner, thick=12)
    by = cv.title_block(top + 70, cv.ic, 100)
    cv.rule(by + 54, cv.ac, width=cv.inner, thick=12)
    cv.text_block(by + 120, cv.subtitle, 48, cv.ic)
    cv.colophon_stack(cv.ac, cv.ic)


def _g_panel(cv: _Cover) -> None:
    """An accent panel floats on the paper field and holds the title."""
    px0, py0, px1, py1 = cv.margin, int(cv.H * 0.15), cv.W - cv.margin, int(cv.H * 0.49)
    cv.d.rectangle([px0, py0, px1, py1], fill=cv.ac)
    cv.title_block(py0, cv.on_ac, 98, region_h=py1 - py0)
    cv.text_block(py1 + 80, cv.subtitle, 50, cv.ic)
    cv.colophon_stack(cv.ac, cv.ic)
    cv.frame(cv.ic)


_GRAMMARS = {
    "band": _g_band, "full": _g_full, "framed": _g_framed,
    "stack": _g_stack, "panel": _g_panel,
}


def make_cover(dest: Path, *, title: str, subtitle: str, author: str,
               imprint: str, paper: str, ink: str, accent: str,
               font_family: str = "", grammar: str = "band") -> None:
    """Draw a 2:3 typographic cover in the chosen grammar and write it as JPEG."""
    cv = _Cover((1200, 1800), paper, ink, accent, _find_font_file(font_family),
                title, subtitle, author, imprint)
    _GRAMMARS.get(grammar, _g_band)(cv)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cv.img.save(dest, "JPEG", quality=90)


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


# Each example gets a distinct cover grammar so the gallery does not read as
# one template recoloured. A book may name its own in aesthetic.yaml
# (`cover-grammar:`); otherwise it is assigned deterministically from the slug,
# and these known examples are pinned so adjacent cards never share a layout.
_GRAMMAR_BY_SLUG = {
    "field-days-almanac": "full",
    "hearthstone-cookbook": "band",
    "on-the-commons-monograph": "stack",
    "signal-and-noise-manual": "framed",
    "small-hours-chapbook": "panel",
    "the-long-field-essays": "stack",
    "the-tinsmith-novella": "band",
    "tidepool-field-notes": "framed",
}
_GRAMMAR_ORDER = ["band", "framed", "panel", "stack", "full"]


def _grammar_for(slug: str, declared: str) -> str:
    if declared in _GRAMMARS:
        return declared
    if slug in _GRAMMAR_BY_SLUG:
        return _GRAMMAR_BY_SLUG[slug]
    return _GRAMMAR_ORDER[sum(ord(c) for c in slug) % len(_GRAMMAR_ORDER)]


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
        grammar=_grammar_for(book.name, _read_indented(aesthetic, "cover-grammar")),
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
