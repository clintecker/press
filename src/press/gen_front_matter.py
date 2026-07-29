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

from . import yamlio

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
        (1000, "m"),
        (900, "cm"),
        (500, "d"),
        (400, "cd"),
        (100, "c"),
        (90, "xc"),
        (50, "l"),
        (40, "xl"),
        (10, "x"),
        (9, "ix"),
        (5, "v"),
        (4, "iv"),
        (1, "i"),
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
    pattern = re.compile(rf"%<<if {name}>>\n(.*?)%<<end {name}>>\n", re.DOTALL)
    return pattern.sub(lambda m: m.group(1) if keep else "", text)


def _fresh_output(root: Path) -> Path:
    """The build/front-matter.tex path, cleared of any leftover.

    Never trust a leftover from a prior run; a crash later must not leave a
    stale page for the next build to ship.
    """

    out = root / "build" / "front-matter.tex"
    if out.exists():
        out.unlink()
    return out


def _load_front_config(root: Path, config: Path) -> dict:
    """Load and shape-check config/front-matter.yaml (empty when absent)."""

    front = (yamlio.loads(config.read_text(encoding="utf-8")) or {}) if config.is_file() else {}

    # A front-matter.yaml the typed model accepts but this generator
    # dereferences as a mapping (or reads epigraph as a nested mapping)
    # once crashed here with a bare AttributeError; refuse a wrong shape up
    # front with a diagnostic that names the file (#207). check_source runs
    # the same guard, but a direct `press pdf` reaches here with no check.
    from . import config_schema

    config_schema.enforce_file(root, config_schema.FRONT_MATTER, front)
    return front


def _require_metadata(meta) -> None:
    """Fail loudly when metadata omits a key the front matter must print."""

    missing = [
        key
        for key in ("title", "author", "copyright", "publisher", "publisher-place")
        if not meta.get(key)
    ]
    if missing:
        raise SystemExit(
            "front matter needs these config/metadata.yaml keys: " + ", ".join(missing)
        )


def _registration_lines() -> list[str]:
    """The ISBN/LCCN lines the colophon prints, in order, skipping blanks."""

    from . import registrations

    lines = []
    for isbn_edition, label in (("print", "ISBN (print)"), ("epub", "ISBN (ebook)")):
        display = registrations.isbn_display(isbn_edition)
        if display:
            lines.append(f"{label} {display}")
    if registrations.lccn_display():
        lines.append(f"LCCN {registrations.lccn_display()}")
    return lines


def _masthead_year(numeric_year, date: str) -> str:
    """Roman numerals when a year is known, else the lowercased date."""

    return roman(int(numeric_year)) if numeric_year else escape(date.lower())


def _edition_note(front, date: str) -> str:
    """The edition line: an explicit note, else the date's year fragment."""

    return escape(
        str(front.get("edition-note") or "").lower()
        or (date.split(",")[0] if "," in date else date).lower()
    )


def _title_line(meta) -> str:
    """The uppercased title, terminated with a period when it lacks one."""

    title = str(meta["title"]).upper()
    if not title.endswith((".", "!", "?")):
        title += "."
    return title


def _apply_keep_blocks(text, *, meta, front, cover_on_page, registration_lines, logo, epigraph):
    """Resolve every %<<if NAME>> conditional block in the template."""

    for name, keep in [
        ("cover", cover_on_page),
        ("nocover", not cover_on_page),
        # The subtitle rides between two rules; with no subtitle the second rule
        # and its OR stack drop out, leaving a single rule under the title
        # rather than an empty bracket of two.
        ("subtitle", bool(meta.get("subtitle"))),
        ("rights-notice", bool(front.get("rights-notice"))),
        ("contact", bool(front.get("contact"))),
        ("motto", bool(front.get("motto"))),
        ("manufacture", bool(front.get("manufacture"))),
        ("colophon-note", bool(front.get("colophon-note"))),
        ("dedication", bool(front.get("dedication"))),
        ("acknowledgements", bool(front.get("acknowledgements"))),
        ("registrations", bool(registration_lines)),
        ("logo", logo.is_file()),
        ("epigraph", bool(epigraph.get("quote"))),
    ]:
        text = keep_block(text, name, keep)
    return text


def _build_values(*, meta, front, authors, date, epigraph, registration_lines, include_cover):
    """The {{PLACEHOLDER}} -> escaped-value map the template substitutes."""

    return {
        "{{TITLE}}": escape(_title_line(meta)),
        "{{SUBTITLE_STACK}}": subtitle_stack(str(meta.get("subtitle") or "")),
        "{{AUTHOR}}": escape(", ".join(authors)),
        "{{PLACE}}": escape(str(meta["publisher-place"]).lower()),
        "{{YEAR}}": _masthead_year(booklib.year(), date),
        "{{EDITION}}": _edition_note(front, date),
        "{{RIGHTS_NOTICE}}": escape(front.get("rights-notice", "")),
        "{{COPYRIGHT}}": escape(meta["copyright"]),
        "{{PUBLISHER}}": escape(meta["publisher"]),
        "{{PUBLISHER_PLACE}}": escape(meta["publisher-place"]),
        "{{CONTACT}}": escape(front.get("contact", "")),
        "{{REGISTRATION_LINES}}": "\\\\ ".join(escape(line) for line in registration_lines),
        "{{MOTTO}}": escape(front.get("motto", "")),
        "{{MANUFACTURE}}": escape(front.get("manufacture", "")),
        "{{COLOPHON_NOTE}}": escape(front.get("colophon-note", "")),
        "{{DEDICATION}}": escape(front.get("dedication", "")),
        "{{ACKNOWLEDGEMENTS}}": escape(front.get("acknowledgements", "")),
        "{{EPIGRAPH}}": escape(epigraph.get("quote", "")),
        "{{EPIGRAPH_ATTRIBUTION}}": escape(epigraph.get("attribution", "")),
        "{{COVER_PATH}}": "assets/cover.jpg",
        # The print interior (include_cover False) embeds the flattened,
        # resolution-capped logo press.print_safe wrote under build/print-assets;
        # the reading front matter keeps the original. A book with a
        # hand-authored title page points its own logo at build/print-assets.
        "{{LOGO_PATH}}": (
            "assets/press-logo.png" if include_cover else "build/print-assets/assets/press-logo.png"
        ),
    }


def generate(include_cover: bool = True) -> Path | None:
    """Write build/front-matter.tex; None when the book does not opt in.

    The print interior drops the cover plate (the cover lives on the
    wrap); the reading PDF leads with it when the asset exists.
    """

    root = booklib.root()
    out = _fresh_output(root)
    config = root / "config" / "front-matter.yaml"
    cover_on_page = include_cover and (root / "assets" / "cover.jpg").is_file()

    # A book opts into generated front matter with a config/front-matter.yaml,
    # and also whenever it has a cover for the reading PDF to lead with -- even
    # with no other front matter, so the cover is never dropped for want of a
    # dedication. A hand-authored tex/title-page.tex overrides both.
    if (root / "tex" / "title-page.tex").is_file():
        return None
    if not config.is_file() and not cover_on_page:
        return None

    front = _load_front_config(root, config)
    meta = booklib.metadata()
    _require_metadata(meta)

    authors = list(booklib.book().authors)
    date = str(meta.get("date") or "")
    epigraph = front.get("epigraph") or {}
    logo = root / "assets" / "press-logo.png"
    registration_lines = _registration_lines()

    text = (booklib.DATA / "tex" / "front-matter.tex").read_text(encoding="utf-8")
    text = _apply_keep_blocks(
        text,
        meta=meta,
        front=front,
        cover_on_page=cover_on_page,
        registration_lines=registration_lines,
        logo=logo,
        epigraph=epigraph,
    )

    values = _build_values(
        meta=meta,
        front=front,
        authors=authors,
        date=date,
        epigraph=epigraph,
        registration_lines=registration_lines,
        include_cover=include_cover,
    )
    for key, value in values.items():
        text = text.replace(key, value)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out
