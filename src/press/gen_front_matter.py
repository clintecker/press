"""Generate the PDF front matter (title page, colophon, epigraph) from config.

The stacked Victorian title page is house design; the facts on it are the
book's. This generator renders data/tex/front-matter.tex from
config/metadata.yaml plus config/front-matter.yaml and writes
build/front-matter.tex, which the pdf defaults include when present.

Activation is the book's choice, stated by the existence of
config/front-matter.yaml: pinned books that predate the generator keep
their current rendered output (the contract forbids changing a valid
book's layout within a major), and tex/title-page.tex still overrides
the whole design when a book wants its own.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from . import booklib

ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape(text: str) -> str:
    return "".join(ESCAPES.get(ch, ch) for ch in str(text))


def roman(year: int) -> str:
    numerals = [
        (1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"),
        (90, "xc"), (50, "l"), (40, "xl"), (10, "x"), (9, "ix"),
        (5, "v"), (4, "iv"), (1, "i"),
    ]
    out = []
    for value, glyph in numerals:
        while year >= value:
            out.append(glyph)
            year -= value
    return "".join(out)


def subtitle_stack(subtitle: str) -> str:
    """The title page's OR stack: clauses split on the subtitle's OR seams.

    Every clause introduced by an OR seam gets its "or," line; a leading
    clause without one renders plain, so "Main; OR, Alternative" keeps its
    main subtitle unlabeled. A subtitle with no seams is one plain clause.
    """

    leading_or = bool(re.match(r"\s*or,", subtitle, re.IGNORECASE))
    clauses = [
        c.strip(" ;.")
        for c in re.split(r";?\s*\bor,\s*", subtitle, flags=re.IGNORECASE)
        if c.strip(" ;.")
    ]
    lines = []
    for index, clause in enumerate(clauses):
        if index > 0 or leading_or:
            lines.append("    {\\scshape or,\\par}\n    \\vspace{0.1in}")
        lines.append(f"    {{\\scshape {escape(clause.lower())}\\par}}\n    \\vspace{{0.14in}}")
    return "\n".join(lines)


def keep_block(text: str, name: str, keep: bool) -> str:
    pattern = re.compile(
        rf"%<<if {name}>>\n(.*?)%<<end {name}>>\n", re.DOTALL
    )
    return pattern.sub(lambda m: m.group(1) if keep else "", text)


def generate(include_cover: bool = True) -> Path | None:
    """Write build/front-matter.tex; None when the book does not opt in.

    The print interior drops the cover plate (the cover lives on the
    wrap); the reading PDF leads with it when the asset exists.
    """

    root = booklib.root()
    out = root / "build" / "front-matter.tex"
    if out.exists():
        # Never trust a leftover from a prior run; a crash below must not
        # leave a stale page for the next build to ship.
        out.unlink()
    config = root / "config" / "front-matter.yaml"
    if (root / "tex" / "title-page.tex").is_file() or not config.is_file():
        return None

    with config.open(encoding="utf-8") as handle:
        front = yaml.safe_load(handle) or {}
    meta = booklib.metadata()
    missing = [
        key for key in ("title", "author", "copyright", "publisher", "publisher-place")
        if not meta.get(key)
    ]
    if missing:
        raise SystemExit(
            "front matter needs these config/metadata.yaml keys: " + ", ".join(missing)
        )

    title = str(meta["title"]).upper()
    if not title.endswith((".", "!", "?")):
        title += "."
    authors = meta["author"]
    if isinstance(authors, str):
        authors = [authors]
    date = str(meta.get("date") or "")
    year_match = re.search(r"\b(1\d{3}|2\d{3})\b", date)
    year = roman(int(year_match.group(1))) if year_match else escape(date.lower())
    edition = escape((date.split(",")[0] if "," in date else date).lower())

    cover_on_page = include_cover and (root / "assets" / "cover.jpg").is_file()
    logo = root / "assets" / "press-logo.png"
    epigraph = front.get("epigraph") or {}

    text = (booklib.DATA / "tex" / "front-matter.tex").read_text(encoding="utf-8")
    for name, keep in [
        ("cover", cover_on_page),
        ("nocover", not cover_on_page),
        ("rights-notice", bool(front.get("rights-notice"))),
        ("contact", bool(front.get("contact"))),
        ("motto", bool(front.get("motto"))),
        ("logo", logo.is_file()),
        ("epigraph", bool(epigraph.get("quote"))),
    ]:
        text = keep_block(text, name, keep)

    values = {
        "{{TITLE}}": escape(title),
        "{{SUBTITLE_STACK}}": subtitle_stack(str(meta.get("subtitle") or "")),
        "{{AUTHOR}}": escape(", ".join(authors)),
        "{{PLACE}}": escape(str(meta["publisher-place"]).lower()),
        "{{YEAR}}": year,
        "{{EDITION}}": edition,
        "{{RIGHTS_NOTICE}}": escape(front.get("rights-notice", "")),
        "{{COPYRIGHT}}": escape(meta["copyright"]),
        "{{PUBLISHER}}": escape(meta["publisher"]),
        "{{PUBLISHER_PLACE}}": escape(meta["publisher-place"]),
        "{{CONTACT}}": escape(front.get("contact", "")),
        "{{MOTTO}}": escape(front.get("motto", "")),
        "{{EPIGRAPH}}": escape(epigraph.get("quote", "")),
        "{{EPIGRAPH_ATTRIBUTION}}": escape(epigraph.get("attribution", "")),
        "{{COVER_PATH}}": "assets/cover.jpg",
        "{{LOGO_PATH}}": "assets/press-logo.png",
    }
    for key, value in values.items():
        text = text.replace(key, value)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out
