"""The book's visual identity, merged from config: press aesthetic.

The house aesthetic (data/aesthetic-house.yaml) is the default; a
book's config/aesthetic.yaml replaces any top-level section it names.
`press aesthetic` prints the effective merge, which is what the
art-direction workflow reads, so the one command answers "what will
the art look like" for authors and agents alike.
"""

from __future__ import annotations

import yaml

from . import booklib

HOUSE = booklib.DATA / "aesthetic-house.yaml"


def effective() -> dict:
    with HOUSE.open(encoding="utf-8") as handle:
        merged = yaml.safe_load(handle)
    book_file = booklib.root() / "config" / "aesthetic.yaml"
    if book_file.is_file():
        with book_file.open(encoding="utf-8") as handle:
            overrides = yaml.safe_load(handle) or {}
        merged.update(overrides)
    return merged


HOUSE_WEB_FAMILY = '"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif'


DARK_SEAM = "@media (prefers-color-scheme: dark)"


def _substitute_tokens(text: str, palette: dict) -> str:
    import re

    for token, value in (palette or {}).items():
        text = re.sub(
            rf"(--{re.escape(str(token))}:\s*)[^;]+;",
            rf"\g<1>{value};",
            text,
        )
    return text


def substitute_web(text: str) -> str:
    """Apply the book's web palette and type to a web surface.

    Both site stylesheets declare the same CSS custom-property tokens.
    The light theme's declarations sit before the dark-mode media
    query and take `web-palette`; declarations after the seam take
    `web-palette-dark`, so a book restyles both themes or either. A
    book that configures nothing gets the house values, which are the
    same characters already in the file: a byte-level no-op.
    """

    merged = effective()
    light, seam, dark = text.partition(DARK_SEAM)
    light = _substitute_tokens(light, merged.get("web-palette") or {})
    if seam:
        dark = _substitute_tokens(dark, merged.get("web-palette-dark") or {})
    text = light + seam + dark
    family = (merged.get("typography") or {}).get("web-family")
    if family:
        text = text.replace(HOUSE_WEB_FAMILY, str(family))
    return text


def write_tex_overrides() -> None:
    """Generate build/aesthetic.tex when the book restates an ink or the
    body face; absent overrides, the file is removed and the packaged
    header's values stand."""

    root = booklib.root()
    out = root / "build" / "aesthetic.tex"
    book_file = root / "config" / "aesthetic.yaml"
    if not book_file.is_file():
        if out.exists():
            out.unlink()
        return
    with book_file.open(encoding="utf-8") as handle:
        overrides = yaml.safe_load(handle) or {}
    colors = overrides.get("book-colors") or {}
    family = (overrides.get("typography") or {}).get("pdf-family") or ""
    lines = ["% Generated from config/aesthetic.yaml; regenerated every build."]
    names = {"ink": "ink", "muted": "muted", "accent": "accent", "link": "linkgreen"}
    for key, tex_name in names.items():
        if colors.get(key):
            value = str(colors[key]).lstrip("#").upper()
            lines.append(f"\\definecolor{{{tex_name}}}{{HTML}}{{{value}}}")
    if family:
        lines.append(f"\\setmainfont{{{family}}}")
    if len(lines) == 1:
        if out.exists():
            out.unlink()
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def show() -> int:
    book_file = booklib.root() / "config" / "aesthetic.yaml"
    source = book_file if book_file.is_file() else HOUSE
    print(f"# effective aesthetic ({source})")
    print(yaml.safe_dump(effective(), sort_keys=False, allow_unicode=True))
    return 0
