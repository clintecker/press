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
from datetime import date
from pathlib import Path
from typing import cast

from . import booklib

JPEG_QUALITY = 88
COVER_ASPECT_TOLERANCE = 0.03
RECORD_HEADING = "## Acceptance record"


def _single_ink_plates() -> bool:
    from . import aesthetic, profiles

    # The design profile's ink is the authority (#214): a colour interior keeps
    # its plates in colour even when the aesthetic names a single-ink medium.
    if profiles.active().ink == "color":
        return False
    medium = str((aesthetic.effective().get("plates") or {}).get("medium", "")).lower()
    return "single" in medium and "ink" in medium


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
        name = target[len("plate:"):].strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
            raise SystemExit(
                "plate names are kebab-case ([a-z0-9-]): --as plate:<name>; "
                "the filename is the reference chapters use"
            )
        destination = root / "assets" / "woodcuts" / f"{name}.jpg"
    elif target == "logomark":
        destination = root / "assets" / "press-logo.png"
    elif target == "portrait":
        destination = root / "assets" / "author.jpg"
    else:
        raise SystemExit(
            f"unknown target {target!r}: cover, plate:<name>, logomark, portrait"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.suffix == ".png":
        rgba = image.convert("RGBA")
        alpha_extrema = cast("tuple[int, int]", rgba.getchannel("A").getextrema())
        if target == "logomark" and alpha_extrema[0] >= 250:
            # An imprint device sits on paper and dark grounds both; an
            # opaque delivery gets its ink extracted onto transparency,
            # which is the house format the intake exists to enforce.
            mask = image.convert("L").point(lambda v: 255 if v < 96 else 0)
            extracted = Image.new("RGBA", image.size, (0, 0, 0, 0))
            extracted.paste(Image.new("RGBA", image.size, (23, 23, 23, 255)), mask=mask)
            rgba = extracted
            print("logomark arrived opaque; ink extracted to transparency")
        rgba.save(destination, optimize=True)
    else:
        # Alpha flattens to paper white, never to the default black: line
        # art on transparency is the common shape of engraving output.
        flat = Image.new("RGB", image.size, (255, 255, 255))
        rgba = image.convert("RGBA")
        flat.paste(rgba, mask=rgba.getchannel("A"))
        if target.startswith("plate:") and _single_ink_plates():
            # The print interior is black ink only and the verifier
            # proves it from the rendered pages; a tinted delivery is
            # grayed at intake when the aesthetic states single ink.
            flat = flat.convert("L")
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
        f"- Accepted {date.today().isoformat()}: `{target}` <- {source.name}, "
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
        kept for kept in text.splitlines()
        if not (kept.startswith("- Accepted ") and f"`{target}`" in kept)
    ]
    heading_at = lines.index(RECORD_HEADING)
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
        "--as", dest="target", required=True,
        help="cover | plate:<name> | logomark | portrait",
    )
    enhance_cmd = sub.add_parser(
        "enhance", help="upscale, quantize, and losslessly compress plate art")
    enhance_cmd.add_argument(
        "file", type=Path, nargs="?",
        help="one image to finish; omit to finish every committed plate")
    enhance_cmd.add_argument("--colors", type=int, default=None,
                             help="palette size (default from the aesthetic medium)")
    enhance_cmd.add_argument("--max-edge", type=int, default=None,
                             help="target long edge in px (default 2400, print-grade)")
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
        print("no Real-ESRGAN upscaler found (Upscayl or realesrgan-ncnn-vulkan); "
              "quantizing and compressing without an AI upscale")

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
        result = art_enhance.enhance(src, dst, model=default_model, colors=colors,
                                     max_edge=max_edge, grayscale=grayscale)
        how = "upscaled" if result.upscaled else "resampled"
        tone = "grays" if grayscale else "colors"
        print(f"enhanced {src.name} -> {dst.name}: {result.width}x{result.height}, "
              f"{result.colors} {tone}, {how}")
    return 0
