"""Commission an in-book illustration -- a plate, map, diagram, or ornament.

An illustration is a cover style pointed inward: it prints in a single ink (the
interior print law), carries no lettering, and lands as a plate/figure. Its
subject is the ``art:`` description the author wrote beside the figure in the
manuscript -- never the caption, which is a reader-facing label, not art
direction (#225). Name the figure and the press reads that description; or pass
``--subject`` to direct one straight from the command line. Source material an
author supplies -- a photograph, a rough map, a sketch -- is redrawn into the
book's style with ``--from``::

    press illustrate compositor            # reads the manuscript's art: for it
    press illustrate harbour --style wood-engraving --from photos/harbour.jpg
    press illustrate cell --style line-diagram --subject "a plant cell, labelled"
    press illustrate --list

The name matches a declared figure on its image-file stem -- the same token
``press art accept ... --as plate:<name>`` records. A figure with no ``art:``
description is deliberately not drawn (the press must never fall back to the
caption's own words), and a ``chart``/``diagram`` is routed away from the image
model entirely: those render from a data file.

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

from . import adapters, aesthetic, art_commission, booklib, figures, yamlio

STYLES_DATA = booklib.DATA / "illustration-styles.yaml"

# Appended to every illustration: wordless and single-ink, always.
_GUARDRAIL = (
    "\n\nSingle ink only, no colour wash. No text, no words, no lettering, no "
    "caption, no page border, no watermark, no signature."
)

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


def find_figure(name: str) -> figures.Figure | None:
    """The manuscript figure whose image file is named ``<name>`` (matched on the
    filename stem, the same token ``--as plate:<name>`` records), or None when no
    figure by that name is declared. Its ``art:`` description -- never its caption
    -- is what press illustrate draws (#225)."""

    try:
        paths = booklib.chapter_files()
    except FileNotFoundError:
        return None
    for path in paths:
        for fig in figures.parse(path.read_text(encoding="utf-8")):
            if Path(fig.src).stem == name:
                return fig
    return None


def subject_from_figure(fig: figures.Figure | None, name: str) -> str:
    """The art-direction subject for a named figure: its ``art:`` description.
    Refuses -- never silently draws the caption (#225) -- when the figure is
    undeclared, is a chart/diagram that renders from data, or carries no ``art:``
    description at all."""

    if fig is None:
        raise SystemExit(
            f"press illustrate: no figure named {name!r} in the manuscript, and no "
            f"--subject given. Declare it (e.g. ![caption](assets/fig/{name}.jpg)"
            "{.plate}) with an <!-- art: … --> description, or pass --subject."
        )
    if fig.kind in figures.DATA_KINDS:
        raise SystemExit(
            f"press illustrate: figure {name!r} is a {fig.kind}; it renders from its "
            f"{fig.directive or 'data'} file, not an image model. It is not illustrated."
        )
    if not fig.generatable or not fig.description:
        raise SystemExit(
            f"press illustrate: figure {name!r} carries no <!-- art: … --> description. "
            "A caption is a label, not art direction (#225): add an art: comment after "
            "the image in the manuscript, or pass --subject."
        )
    return fig.description


class _Args:
    def __init__(self) -> None:
        self.name: str | None = None
        self.style: str | None = None
        self.subject = ""
        self.source: str | None = None
        self.print_only = False
        self.list = False


_TAKES = {"--style": "style", "--subject": "subject", "--from": "source"}


def _consume_token(args: _Args, token: str, rest: list[str]) -> None:
    """Fold one argv token into ``args``, consuming its value from ``rest`` when
    the token is a value-taking flag."""
    if token == "--list":
        args.list = True
    elif token == "--print":
        args.print_only = True
    elif token in _TAKES:
        setattr(args, _TAKES[token], rest.pop(0) if rest else "")
    elif not token.startswith("-") and args.name is None:
        args.name = token
    else:
        raise SystemExit(f"press illustrate: unexpected argument {token!r}")


def _parse(argv: list[str]) -> _Args:
    args = _Args()
    rest = list(argv)
    while rest:
        _consume_token(args, rest.pop(0), rest)
    return args


def _print_styles() -> int:
    """The ``--list`` output: every known style with its note and source hint."""
    for sid, style in sorted(load_styles(booklib.root()).items()):
        mark = " (needs --from)" if style.get("source") == "required" else ""
        print(f"  {sid:22} {style.get('note', '')}{mark}")
    return 0


def _subject_and_style(name: str, style_arg: str | None) -> tuple[str, str | None]:
    """Resolve the subject from the named figure's ``art:`` description when no
    ``--subject`` was given; the figure may also supply the style."""
    fig = find_figure(name)
    subject = subject_from_figure(fig, name)
    if style_arg is None and fig is not None:
        style_arg = fig.style
    return subject, style_arg


def _load_references(source: str) -> list[tuple[bytes, str]]:
    """The reference-image payload for ``--from <image>``, or a hard exit when the
    path is not a file."""
    path = Path(source)
    if not path.is_file():
        raise SystemExit(f"source image not found: {source}")
    return [_load_source(path)]


def _emit_prompt(style_id: str, source: str | None, prompt: str, print_only: bool) -> int:
    """Print the prompt for running elsewhere -- the offline path taken with
    ``--print`` or with no image-model key."""
    if not print_only:
        print("# no OPENAI_API_KEY set; emitting the prompt to run elsewhere.\n")
    print(
        f"# illustration style: {style_id}"
        + (f"  (with reference {source})" if source else "")
        + "\n"
    )
    print(prompt)
    return 0


def _commission(
    root: Path,
    name: str,
    style_id: str,
    prompt: str,
    references: list[tuple[bytes, str]] | None,
) -> int:
    """Run the image model, stage the plate under ``build/illustrations/``, and
    point at ``press art accept``."""
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


def main(argv: list[str]) -> int:
    args = _parse(argv)
    if args.list:
        return _print_styles()
    name, style_arg, subject = args.name, args.style, args.subject
    source, print_only = args.source, args.print_only
    if not name:
        raise SystemExit("press illustrate <name> [--style <id>] [--from <image>] | --list")

    root = booklib.root()
    styles = load_styles(root)
    aes = aesthetic.effective()

    # No --subject on the command line means the subject is the figure's own
    # art: description from the manuscript; the figure may also name the style.
    if not subject:
        subject, style_arg = _subject_and_style(name, style_arg)

    style_id = _resolve_style(styles, style_arg, aes)
    style = styles[style_id]
    if style.get("source") == "required" and not source:
        raise SystemExit(f"the {style_id} style needs source material: --from <image>")
    prompt = build_prompt(style, context(aes), subject)

    references = _load_references(source) if source else None

    if print_only or not _has_key():
        return _emit_prompt(style_id, source, prompt, print_only)

    return _commission(root, name, style_id, prompt, references)
