"""Intake for commissioned art: press art accept <file> --as <target>.

The art department's contract: the press holds the prompts (the
art-direction workflow writes art/commissions.md), the book holds only
accepted images. Acceptance converts to house format (the format law
lives in CLAUDE.md's scars), enforces the cover's trim aspect, places
the file, and records the acceptance next to its commission prompt so
a lost original can be recommissioned. The text-block height cap is
enforced at typeset time by the TeX header, not here.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import TYPE_CHECKING, cast

from . import adapters, booklib

if TYPE_CHECKING:
    from PIL import Image as _Image

JPEG_QUALITY = 88
COVER_ASPECT_TOLERANCE = 0.03
RECORD_HEADING = "## Acceptance record"

# The house imprint ink: a near-black that reads as ink on paper and on a
# dark ground both. Shared by the logomark extraction and the coloured-cloth
# composite in print_safe.
_INK = (23, 23, 23)


def _is_opaque(rgba: _Image.Image) -> bool:
    """True when an RGBA image's alpha is essentially solid everywhere -- a
    baked delivery to segment, not a mask to keep."""

    low, _ = cast("tuple[int, int]", rgba.getchannel("A").getextrema())
    return low >= 250


def _single_ink_plates() -> bool:
    from . import aesthetic, profiles

    # The design profile's ink is the authority (#214): a colour interior keeps
    # its plates in colour even when the aesthetic names a single-ink medium.
    if profiles.active().ink == "color":
        return False
    medium = str((aesthetic.effective().get("plates") or {}).get("medium", "")).lower()
    return "single" in medium and "ink" in medium


# Luminance cut-offs for the line-art key. A tone at or above _KEY_WHITE is
# ground (keyed fully transparent); at or below _KEY_BLACK is ink (fully
# opaque). _KEY_WHITE sits below a generated plate's light-grey ground (~241)
# so the ground vanishes rather than leaving a faint box; the window between
# keeps the ink's anti-aliased edges smooth.
_KEY_WHITE = 225
_KEY_BLACK = 45


def _segment_line_art(image: _Image.Image) -> _Image.Image:
    """Key ink-on-light line art to alpha with a luminance key: the light ground
    turns transparent and the ink's tone moves into the alpha, so one master
    composites onto white paper, coloured cloth, or a transparent web panel.

    The key has a white cut-off, not a bare ``255 - luminance``. A generated
    plate's ground is rarely pure white -- gpt-image lays it on a light grey
    near ``#f1f2f3`` -- and a bare inversion leaves that ground at alpha ~14,
    a five-percent box that is glaring on cream paper. Here any tone at or above
    ``_KEY_WHITE`` goes fully transparent and any tone at or below ``_KEY_BLACK``
    goes fully opaque, with the ink's anti-aliased edges ramping smoothly
    between -- so the ground vanishes cleanly and the line stays crisp.
    Compositing the result back onto white still reproduces the line art."""

    from PIL import Image

    span = _KEY_WHITE - _KEY_BLACK

    def key(v: int) -> int:
        if v >= _KEY_WHITE:
            return 0
        if v <= _KEY_BLACK:
            return 255
        return round(255 * (_KEY_WHITE - v) / span)

    rgb = image.convert("RGB")
    alpha = rgb.convert("L").point(key)
    master = Image.new("RGBA", rgb.size, (0, 0, 0, 0))
    master.putalpha(alpha)
    return master


def _require_flat_ground(image: _Image.Image) -> None:
    """Refuse an opaque line-art delivery whose ground is not a flat light
    colour. The luminance key reads every dark pixel as ink, so a gradient or a
    textured ground survives as a ghost on the page (the darker end keys only
    part-way to transparent). Better to refuse it at intake than ship the smudge.
    The border band is where the ground shows, so judge flatness there: it must
    be light (a high mean), even (a low spread), and free of a top-to-bottom
    gradient."""

    from PIL import ImageStat

    grey = image.convert("L")
    w, h = grey.size
    band = max(3, min(w, h) // 25)
    top = grey.crop((0, 0, w, band))
    bottom = grey.crop((0, h - band, w, h))
    left = grey.crop((0, 0, band, h))
    right = grey.crop((w - band, 0, w, h))
    # The fraction of border pixels that are light. A flat light ground is
    # almost all light; ink strokes that reach the edge are sparse, so they
    # barely move this -- but a dark, tonal, or textured ground pushes it down.
    # tobytes() on an L-mode image is one byte per pixel in row order, the same
    # sequence getdata() returned (getdata is deprecated in Pillow 14).
    border = (
        list(top.tobytes()) + list(bottom.tobytes()) + list(left.tobytes()) + list(right.tobytes())
    )
    light = sum(1 for v in border if v >= 200) / len(border)
    # A smooth gradient shows as a top-to-bottom or side-to-side drift in the
    # border means (sparse edge ink does not drift one side against the other).
    means = [ImageStat.Stat(e).mean[0] for e in (top, bottom, left, right)]
    gradient = max(abs(means[0] - means[1]), abs(means[2] - means[3]))
    if light < 0.82 or gradient > 45:
        raise SystemExit(
            "art accept: the plate's ground is not a flat light colour "
            f"(only {light:.0%} of the border is light, drift {gradient:.0f}); "
            "the luminance key would leave a ghost on the page. Commission the "
            "line art on a plain, near-white ground, or -- for tonal or "
            "photographic art -- set a colour interior so the plate keeps its "
            "exact pixels."
        )


def _plate_master(image: _Image.Image, *, single_ink: bool) -> _Image.Image:
    """A plate's surface-agnostic master.

    A single-ink plate (the house default) is high-contrast line art: a
    baked-white delivery is keyed to alpha by luminance so its ground is
    transparent -- never shipped as an opaque box -- and a delivery that
    already carries alpha keeps its mask, its ink greyed. print_safe then
    composites the alpha master onto the interior white or the cover field at
    use time, and the web edition serves it transparent.

    A colour interior (#214) is not line art; the right separator for
    photographic/colour art is a matting model (BiRefNet/rembg), not a
    luminance key that would shift its hues. Until that lands a colour plate
    keeps exact colour: its delivered mask if it has one, else an opaque
    flatten onto white, unchanged from the baked delivery."""

    from PIL import Image

    rgba = image.convert("RGBA")
    delivered_alpha = not _is_opaque(rgba)
    if single_ink:
        if delivered_alpha:
            greyed = rgba.convert("L").convert("RGBA")
            greyed.putalpha(rgba.getchannel("A"))
            return greyed
        _require_flat_ground(image)
        return _segment_line_art(image)
    if delivered_alpha:
        return rgba
    flat = Image.new("RGB", rgba.size, (255, 255, 255))
    flat.paste(rgba, mask=rgba.getchannel("A"))
    return flat


def _logomark_master(image: _Image.Image) -> _Image.Image:
    """The imprint device as ink on transparency. An opaque delivery gets its
    ink extracted with a hard luminance threshold (a device is solid, not
    tonal); a delivery already on transparency is kept as-is."""

    from PIL import Image

    rgba = image.convert("RGBA")
    if _is_opaque(rgba):
        # An imprint device sits on paper and dark grounds both; an opaque
        # delivery gets its ink extracted onto transparency, the house format
        # the intake exists to enforce.
        mask = image.convert("L").point(lambda v: 255 if v < 96 else 0)
        extracted = Image.new("RGBA", image.size, (0, 0, 0, 0))
        extracted.paste(Image.new("RGBA", image.size, (*_INK, 255)), mask=mask)
        print("logomark arrived opaque; ink extracted to transparency")
        return extracted
    return rgba


def trim_aspect() -> float:
    trim = booklib.metadata().get("trim") or {}
    width, height = trim.get("width", 6), trim.get("height", 9)
    return height / width


def accept(source: Path, target: str) -> Path:
    from PIL import Image, ImageOps

    root = booklib.root()
    image: Image.Image = Image.open(source)
    # A rotated photo stores its true orientation in EXIF; measure and
    # save the pixels the reader will actually face.
    transposed = ImageOps.exif_transpose(image)
    if transposed is not None:
        image = transposed

    if target == "cover":
        aspect = image.height / image.width
        wanted = trim_aspect()
        if abs(aspect - wanted) / wanted > COVER_ASPECT_TOLERANCE:
            raise SystemExit(
                f"cover aspect {aspect:.3f} (h/w) does not match the "
                f"{wanted:.3f} trim; crop the source, do not stretch it"
            )
        destination = root / "assets" / "cover.jpg"
    elif target.startswith("plate:"):
        name = target[len("plate:") :].strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
            raise SystemExit(
                "plate names are kebab-case ([a-z0-9-]): --as plate:<name>; "
                "the filename is the reference chapters use"
            )
        destination = root / "assets" / "woodcuts" / f"{name}.png"
    elif target == "logomark":
        destination = root / "assets" / "press-logo.png"
    elif target == "portrait":
        destination = root / "assets" / "author.jpg"
    else:
        raise SystemExit(f"unknown target {target!r}: cover, plate:<name>, logomark, portrait")

    destination.parent.mkdir(parents=True, exist_ok=True)
    if target == "logomark":
        _logomark_master(image).save(destination, optimize=True)
    elif target.startswith("plate:"):
        # A plate is kept as an alpha master, not a baked-white JPEG, so one
        # graphic composites onto any surface. Single ink greys the ink here;
        # the print verifier proves the interior is one ink from the pages.
        _plate_master(image, single_ink=_single_ink_plates()).save(destination, optimize=True)
    else:
        # Cover and portrait are opaque rasters: alpha flattens to paper
        # white, never to the default black.
        flat = Image.new("RGB", image.size, (255, 255, 255))
        rgba = image.convert("RGBA")
        flat.paste(rgba, mask=rgba.getchannel("A"))
        flat.save(destination, quality=JPEG_QUALITY, optimize=True)

    record_acceptance(root, target, source, image, destination)
    print(f"accepted {target}: {destination.relative_to(root)} ({image.width}x{image.height})")
    return destination


def record_acceptance(root: Path, target: str, source: Path, image, destination: Path) -> None:
    """One acceptance line per target under the record heading, replaced on
    re-accept, so the file the art-direction workflow rewrites stays sane."""

    record = root / "art" / "commissions.md"
    record.parent.mkdir(parents=True, exist_ok=True)
    line = (
        f"- Accepted {adapters.clock.today().isoformat()}: `{target}` <- {source.name}, "
        f"{image.width}x{image.height}px, placed at {destination.relative_to(root)}"
    )
    if record.is_file():
        text = record.read_text(encoding="utf-8")
    else:
        text = (
            "# Commissions\n\nRun the `art-direction` workflow to generate the "
            "commission prompts this record should sit beside.\n"
        )
    if RECORD_HEADING not in text:
        text = text.rstrip("\n") + f"\n\n{RECORD_HEADING}\n"
    lines = [
        kept
        for kept in text.splitlines()
        if not (kept.startswith("- Accepted ") and f"`{target}`" in kept)
    ]
    heading_at = lines.index(RECORD_HEADING)
    # A blank line must separate the heading from the list beneath it, or the
    # generated record fails a markdown linter (MD022/MD032).
    if heading_at + 1 >= len(lines) or lines[heading_at + 1].strip():
        lines.insert(heading_at + 1, "")
    tail = heading_at + 1
    while tail < len(lines) and (lines[tail].startswith("- Accepted ") or not lines[tail].strip()):
        tail += 1
    lines.insert(tail, line)
    record.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if argv and argv[0] == "commission":
        from . import art_commission

        return art_commission.main(argv[1:])
    parser = argparse.ArgumentParser(prog="press art")
    sub = parser.add_subparsers(dest="command", required=True)
    accept_cmd = sub.add_parser("accept", help="take a commissioned image into the book")
    sub.add_parser("commission", help="submit commissions.md prompts to image models")
    accept_cmd.add_argument("file", type=Path)
    accept_cmd.add_argument(
        "--as",
        dest="target",
        required=True,
        help="cover | plate:<name> | logomark | portrait",
    )
    enhance_cmd = sub.add_parser(
        "enhance", help="upscale, quantize, and losslessly compress plate art"
    )
    enhance_cmd.add_argument(
        "file",
        type=Path,
        nargs="?",
        help="one image to finish; omit to finish every committed plate",
    )
    enhance_cmd.add_argument(
        "--colors", type=int, default=None, help="palette size (default from the aesthetic medium)"
    )
    enhance_cmd.add_argument(
        "--max-edge",
        type=int,
        default=None,
        help="target long edge in px (default 2400, print-grade)",
    )
    args = parser.parse_args(argv)
    if args.command == "enhance":
        return _enhance(args)
    if not args.file.is_file():
        raise SystemExit(f"no such file: {args.file}")
    accept(args.file, args.target)
    return 0


def _enhance(args) -> int:
    """Finish plate art: one file, or every committed plate when none is named.
    The book's plate medium (config/aesthetic.yaml) picks the upscale model and
    the palette, so an engraving finishes in engraving grain."""

    from . import aesthetic, art_enhance, booklib, profiles

    plates = aesthetic.effective().get("plates") or {}
    medium = str(plates.get("medium", "") if isinstance(plates, dict) else "")
    default_model, default_colors = art_enhance.profile_for(medium)
    colors = args.colors if args.colors is not None else default_colors
    max_edge = args.max_edge if args.max_edge is not None else art_enhance._DEFAULT_MAX_EDGE
    # A colour design profile keeps the plate in colour; single-ink (the
    # default) finishes to grayscale, the honest space for an engraving (#214).
    grayscale = profiles.active().ink != "color"

    if art_enhance.find_upscaler() is None:
        print(
            "no Real-ESRGAN upscaler found (Upscayl or realesrgan-ncnn-vulkan); "
            "quantizing and compressing without an AI upscale"
        )

    if args.file is not None:
        targets = [args.file]
    else:
        woodcuts = booklib.root() / "assets" / "woodcuts"
        targets = sorted(woodcuts.glob("*.jpg")) + sorted(woodcuts.glob("*.png"))
        if not targets:
            raise SystemExit("no plates under assets/woodcuts/ to enhance")

    for src in targets:
        if not src.is_file():
            raise SystemExit(f"no such file: {src}")
        dst = src.with_suffix(".png")
        result = art_enhance.enhance(
            src, dst, model=default_model, colors=colors, max_edge=max_edge, grayscale=grayscale
        )
        how = "upscaled" if result.upscaled else "resampled"
        tone = "grays" if grayscale else "colors"
        print(
            f"enhanced {src.name} -> {dst.name}: {result.width}x{result.height}, "
            f"{result.colors} {tone}, {how}"
        )
    return 0
