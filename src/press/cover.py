"""Commission a book cover in a chosen style.

A cover *style* is an art-direction template -- a layout, a typographic idiom,
and imagery rules -- declared in ``data/cover-styles.yaml`` and fillable with
one book's title, author, palette, and subject. A book selects one in
``config/aesthetic.yaml``::

    cover:
      style: penguin-tri-band     # any id `press cover --list` prints
      subject: "a rocky intertidal shore at low tide, kelp, a shorebird"

and may define its own styles in ``config/cover-styles.yaml`` (merged over the
house library), so an author is never limited to the built-ins.

``press cover`` builds the prompt and, when ``OPENAI_API_KEY`` is set, asks an
image model for the art, stages it under ``build/cover/`` and points at
``press art accept`` -- the one intake that enforces the cover geometry and
writes ``assets/cover.jpg``. Without a key (or with ``--print``) it emits the
prompt instead, so the same styles drive a manual or agent-run commission and
the press stays offline by default. Image generation is non-deterministic, so
this is a one-time authoring step, never part of a build.
"""

from __future__ import annotations

from pathlib import Path

from . import adapters, aesthetic, art_commission, booklib, yamlio

STYLES_DATA = booklib.DATA / "cover-styles.yaml"

# Appended to every `baked` style so the model letters the copy correctly.
_GUARDRAIL = """

EXACT TEXT — render verbatim, correctly spelled, and put NO other words on the cover:
  "{title}"  (the title)
  "{author}"  (the author)
  "{imprint}"  (the publisher, where the layout names it)
Precise, legible typography. Flat printed look, faint paper texture.
Do NOT add: any other text, a price, a barcode, a watermark, or extra logos."""

_SKIP_WORDS = {"and", "the", "of", "for", "&", "a"}


def load_styles(book_dir: Path | None = None) -> dict[str, dict]:
    """The style library: the house set, with a book's own
    ``config/cover-styles.yaml`` merged over it when present."""
    styles = dict((yamlio.load(STYLES_DATA) or {}).get("styles", {}))
    if book_dir is not None:
        override = book_dir / "config" / "cover-styles.yaml"
        if override.is_file():
            styles.update((yamlio.load(override) or {}).get("styles", {}))
    return styles


def _initials(imprint: str) -> str:
    return "".join(w[0] for w in imprint.split()
                   if w[:1].isalpha() and w.lower() not in _SKIP_WORDS)[:3].upper()


def build_prompt(style: dict, ctx: dict[str, str]) -> str:
    """Fill a style's template with a book's context, adding the exact-text
    guardrail for `baked` styles (those whose type the model letters)."""
    prompt = style["prompt"].format(**ctx)
    if style.get("text", "baked") == "baked":
        prompt += _GUARDRAIL.format(**ctx)
    return prompt


def context(meta: dict, aes: dict, subject: str = "") -> dict[str, str]:
    """The fill context for one book, from its metadata and effective
    aesthetic. An explicit ``subject`` overrides the aesthetic's."""
    authors = meta.get("author") or []
    imprint = str(meta.get("publisher") or "")
    palette = aes.get("web-palette") or aes
    cover = aes.get("cover") or {}
    return {
        "title": str(meta.get("title") or ""),
        "author": str(authors[0] if authors else ""),
        "imprint": imprint,
        "initials": _initials(imprint),
        "subject": subject or str(cover.get("subject") or "the book's subject"),
        "accent": str(palette.get("accent") or "#7a2325"),
        "paper": str(palette.get("paper") or "#f4f1e6"),
    }


# The image spec a cover is drawn at: a 2:3 portrait, high quality, opaque.
_SPEC = ("gpt-image-2", "1024x1536", "high", False)


def _has_key() -> bool:
    return bool(adapters.environment.get("OPENAI_API_KEY"))


def _generate(prompt: str, dest: Path) -> None:
    """Ask the image model for one cover and write the PNG to ``dest``. The
    request goes through the same art-commission image layer as every other
    press commission (adapters, retries, key handling)."""
    images = art_commission.generate_openai(prompt, _SPEC, 1)
    if not images:
        raise SystemExit("the image model returned no cover")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(images[0])


def _resolve_style(styles: dict[str, dict], chosen: str | None,
                   aes: dict) -> str:
    style_id = chosen or (aes.get("cover") or {}).get("style") or "penguin-tri-band"
    if style_id not in styles:
        known = ", ".join(sorted(styles))
        raise SystemExit(f"unknown cover style {style_id!r}; try one of: {known}")
    return style_id


def main(argv: list[str]) -> int:
    style_arg: str | None = None
    subject = ""
    print_only = False
    rest = list(argv)
    while rest:
        token = rest.pop(0)
        if token == "--list":
            for name, style in sorted(load_styles(booklib.root()).items()):
                print(f"  {name:22} {style.get('note', '')}")
            return 0
        elif token == "--style":
            style_arg = rest.pop(0) if rest else None
        elif token == "--subject":
            subject = rest.pop(0) if rest else ""
        elif token == "--print":
            print_only = True
        else:
            raise SystemExit(f"press cover: unexpected argument {token!r}")

    root = booklib.root()
    styles = load_styles(root)
    aes = aesthetic.effective()
    style_id = _resolve_style(styles, style_arg, aes)
    ctx = context(booklib.metadata(), aes, subject)
    prompt = build_prompt(styles[style_id], ctx)

    if print_only or not _has_key():
        if not print_only:
            print("# no OPENAI_API_KEY set; emitting the prompt to run elsewhere.\n")
        print(f"# cover style: {style_id}\n")
        print(prompt)
        return 0

    dest = root / "build" / "cover" / "cover.png"
    print(f"commissioning a {style_id} cover for “{ctx['title']}” …")
    _generate(prompt, dest)
    print(f"wrote {dest.relative_to(root)}")
    print("check the lettering, then install it with:")
    print(f"  press art accept {dest.relative_to(root)} --as cover")
    return 0
