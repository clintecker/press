"""Print-safe copies of a book's interior raster images.

Print-on-demand vendors (Lulu, KDP, IngramSpark) raise two warnings on a
press interior: transparency, and images over 600 PPI. Both come from the
images the interior embeds -- the logomark is stored as ink on
transparency, and a portrait or plate placed small can exceed 600 PPI.

For the ``print`` target this module writes flattened, downsampled copies
into ``build/print-assets/`` mirroring the ``assets/`` layout. The print
profile prepends that directory to ``\\graphicspath`` (see
``data/tex/print-header.tex``), so lualatex embeds the safe copies while
the author's originals -- and the reading PDF, which never prepends the
directory -- stay byte-for-byte untouched.

The pixel caps suit the 6x9 interior: a figure at the full 6.3in height
lands near 300 PPI, and the logomark, placed at 1.7in, gets a tighter cap
so it clears 600 PPI at that size. A figure placed much smaller than its
natural size in the manuscript can still exceed 600 PPI; the cap bounds
the common case, and the print verifier is the backstop.
"""

from __future__ import annotations

import shutil
from pathlib import Path

# Interiors print on white paper, so a flattened alpha composites to white.
_WHITE = (255, 255, 255)

# Long-edge pixel caps. The logomark is placed at 1.7in, so 1000px keeps it
# under 600 PPI there; a figure can run to the 6.3in image cap, where 1900px
# is ~300 PPI. Neither upscales a smaller source.
_LOGO_MAX_EDGE = 1000
_FIGURE_MAX_EDGE = 1900


def _targets(root: Path) -> list[tuple[Path, int]]:
    """Every interior raster paired with its long-edge pixel cap."""

    jobs: list[tuple[Path, int]] = []
    logo = root / "assets" / "press-logo.png"
    if logo.is_file():
        jobs.append((logo, _LOGO_MAX_EDGE))
    for jpg in sorted((root / "assets").glob("*.jpg")):
        jobs.append((jpg, _FIGURE_MAX_EDGE))
    woodcuts = root / "assets" / "woodcuts"
    if woodcuts.is_dir():
        for jpg in sorted(woodcuts.glob("*.jpg")):
            jobs.append((jpg, _FIGURE_MAX_EDGE))
    return jobs


def _has_alpha(image) -> bool:
    return image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    )


def sanitize(src: Path, dst: Path, max_edge: int) -> None:
    """Write ``src`` to ``dst`` with no transparency and its long edge at
    most ``max_edge`` pixels, preserving grayscale so a single-ink plate
    does not balloon into RGB."""

    from PIL import Image

    with Image.open(src) as opened:
        image = opened
        if _has_alpha(image):
            rgba = image.convert("RGBA")
            flat = Image.new("RGB", rgba.size, _WHITE)
            flat.paste(rgba, mask=rgba.split()[-1])
            image = flat
        elif image.mode not in ("L", "RGB"):
            image = image.convert("RGB")
        long_edge = max(image.size)
        if long_edge > max_edge:
            scale = max_edge / long_edge
            image = image.resize(
                (round(image.width * scale), round(image.height * scale)),
                Image.Resampling.LANCZOS,
            )
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.suffix.lower() in (".jpg", ".jpeg"):
            image.save(dst, format="JPEG", quality=88)
        else:
            image.save(dst, format="PNG")


def prepare(root: Path) -> Path | None:
    """Rebuild ``build/print-assets/`` from the book's interior rasters and
    return it (the directory the print profile adds to ``\\graphicspath``),
    or ``None`` when the book embeds no rasters. Rebuilt from scratch each
    call so a removed or edited source cannot persist across builds."""

    out = root / "build" / "print-assets"
    if out.exists():
        shutil.rmtree(out)
    jobs = _targets(root)
    if not jobs:
        return None
    for src, cap in jobs:
        sanitize(src, out / src.relative_to(root), cap)
    return out
