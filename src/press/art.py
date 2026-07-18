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

from . import booklib

JPEG_QUALITY = 88
COVER_ASPECT_TOLERANCE = 0.03
RECORD_HEADING = "## Acceptance record"


def trim_aspect() -> float:
    trim = booklib.metadata().get("trim") or {}
    width, height = trim.get("width", 6), trim.get("height", 9)
    return height / width


def accept(source: Path, target: str) -> Path:
    from PIL import Image, ImageOps

    root = booklib.root()
    image = Image.open(source)
    # A rotated photo stores its true orientation in EXIF; measure and
    # save the pixels the reader will actually face.
    image = ImageOps.exif_transpose(image)

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
        image.convert("RGBA").save(destination, optimize=True)
    else:
        # Alpha flattens to paper white, never to the default black: line
        # art on transparency is the common shape of engraving output.
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
    parser = argparse.ArgumentParser(prog="press art")
    sub = parser.add_subparsers(dest="command", required=True)
    accept_cmd = sub.add_parser("accept", help="take a commissioned image into the book")
    accept_cmd.add_argument("file", type=Path)
    accept_cmd.add_argument(
        "--as", dest="target", required=True,
        help="cover | plate:<name> | logomark | portrait",
    )
    args = parser.parse_args(argv)
    if not args.file.is_file():
        raise SystemExit(f"no such file: {args.file}")
    accept(args.file, args.target)
    return 0
