"""Commission an in-book illustration -- a plate, map, diagram, or ornament.

An illustration is a cover style pointed inward: it prints in a single ink (the
interior print law), carries no lettering, and lands as a plate/figure. It is
drawn from a subject, and optionally from SOURCE MATERIAL an author supplies --
a photograph, a rough map, a sketch -- redrawn into the book's style::

    press illustrate harbour --style wood-engraving --from photos/harbour.jpg
    press illustrate coast-map --style engraved-map --from maps/rough.png
    press illustrate cell --style line-diagram --subject "a plant cell, labelled"
    press illustrate --list

Styles come from ``data/illustration-styles.yaml``; a book adds its own in
``config/illustration-styles.yaml``, merged over the house set. The request goes
through the same art-commission image layer as every other press commission, so
``press illustrate`` stages the art under ``build/illustrations/`` and points at
``press art accept ... --as plate:<name>`` -- the one intake that greys a plate
to single ink and records it. Without an image-model key (or with ``--print``)
it emits the prompt, so the press stays offline by default.

Data figures -- bar and line charts -- do NOT belong here: an image model would
invent the numbers. Those render deterministically from a data file; this
command is for illustrative art.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from . import adapters, aesthetic, art_commission, booklib, yamlio

STYLES_DATA = booklib.DATA / "illustration-styles.yaml"

# Appended to every illustration: wordless and single-ink, always.
_GUARDRAIL = (
    "\n\nSingle ink only, no colour wash. No text, no words, no lettering, no "
    "caption, no page border, no watermark, no signature.")

# An interior plate: a versatile square at high quality, opaque on paper.
_SPEC = ("gpt-image-2", "1024x1024", "high", False)


def load_styles(book_dir: Path | None = None) -> dict[str, dict]:
    """The illustration-style library: the house set, with a book's own
    ``config/illustration-styles.yaml`` merged over it when present."""
    styles = dict((yamlio.load(STYLES_DATA) or {}).get("styles", {}))
    if book_dir is not None:
        override = book_dir / "config" / "illustration-styles.yaml"
        if override.is_file():
            styles.update((yamlio.load(override) or {}).get("styles", {}))
    return styles


def context(aes: dict) -> dict[str, str]:
    """The fill context for interior art: the book's single ink and its paper.
    The plate intake greys colour away for a single-ink book, so the ink here
    sets the drawing's tone, not the final printed colour."""
    colours = aes.get("book-colors") or {}
    palette = aes.get("web-palette") or aes
    return {
        "ink": str(colours.get("ink") or palette.get("ink") or "#1b1b1b"),
        "paper": str(palette.get("paper") or "#f4f1e6"),
    }


def build_prompt(style: dict, ctx: dict[str, str], subject: str) -> str:
    """Fill a style's template with the subject and the book's ink, adding the
    wordless single-ink guardrail."""
    return style["prompt"].format(subject=subject, **ctx) + _GUARDRAIL


def _load_source(path: Path) -> tuple[bytes, str]:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return path.read_bytes(), mime


def _has_key() -> bool:
    return bool(adapters.environment.get("OPENAI_API_KEY"))


def _resolve_style(styles: dict[str, dict], chosen: str | None, aes: dict) -> str:
    style_id = chosen or (aes.get("plates") or {}).get("style") or "wood-engraving"
    if style_id not in styles:
        known = ", ".join(sorted(styles))
        raise SystemExit(f"unknown illustration style {style_id!r}; try one of: {known}")
    return style_id


class _Args:
    def __init__(self) -> None:
        self.name: str | None = None
        self.style: str | None = None
        self.subject = ""
        self.source: str | None = None
        self.print_only = False
        self.list = False


def _parse(argv: list[str]) -> _Args:
    args = _Args()
    takes = {"--style": "style", "--subject": "subject", "--from": "source"}
    rest = list(argv)
    while rest:
        token = rest.pop(0)
        if token == "--list":
            args.list = True
        elif token == "--print":
            args.print_only = True
        elif token in takes:
            setattr(args, takes[token], rest.pop(0) if rest else "")
        elif not token.startswith("-") and args.name is None:
            args.name = token
        else:
            raise SystemExit(f"press illustrate: unexpected argument {token!r}")
    return args


def main(argv: list[str]) -> int:
    args = _parse(argv)
    if args.list:
        for sid, style in sorted(load_styles(booklib.root()).items()):
            mark = " (needs --from)" if style.get("source") == "required" else ""
            print(f"  {sid:22} {style.get('note', '')}{mark}")
        return 0
    name, style_arg, subject = args.name, args.style, args.subject
    source, print_only = args.source, args.print_only
    if not name:
        raise SystemExit("press illustrate <name> [--style <id>] [--from <image>] | --list")

    root = booklib.root()
    styles = load_styles(root)
    aes = aesthetic.effective()
    style_id = _resolve_style(styles, style_arg, aes)
    style = styles[style_id]
    if style.get("source") == "required" and not source:
        raise SystemExit(f"the {style_id} style needs source material: --from <image>")
    prompt = build_prompt(style, context(aes), subject or "the figure described in the caption")

    references = None
    if source:
        path = Path(source)
        if not path.is_file():
            raise SystemExit(f"source image not found: {source}")
        references = [_load_source(path)]

    if print_only or not _has_key():
        if not print_only:
            print("# no OPENAI_API_KEY set; emitting the prompt to run elsewhere.\n")
        print(f"# illustration style: {style_id}"
              + (f"  (with reference {source})" if source else "") + "\n")
        print(prompt)
        return 0

    dest = root / "build" / "illustrations" / f"{name}.png"
    print(f"commissioning a {style_id} illustration “{name}” …")
    images = art_commission.generate_openai(prompt, _SPEC, 1, references)
    if not images:
        raise SystemExit("the image model returned no illustration")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(images[0])
    print(f"wrote {dest.relative_to(root)}")
    print("check it, then install it as a plate with:")
    print(f"  press art accept {dest.relative_to(root)} --as plate:{name}")
    return 0
