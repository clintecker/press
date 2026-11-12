"""Generate the subject index appendix from the chapter text.

The term list in config/index-terms.yaml is curated; the locations are not.
Each build rescans the chapters, so the index can never disagree with the
text it points into. References are chapter numbers, which are stable across
every edition, rather than page numbers, which are not. Books without a
curated term list simply have no generated index.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import yamlio

from . import booklib, gen_authorities


_HEADING = re.compile(r"^#\s+(?P<title>.*?)\s*(?:\{(?P<attrs>[^}]*)\})?\s*$")


def _unnumbered_title(path: Path) -> str | None:
    """The title of an unnumbered part that is not titled as an appendix (a
    colophon, an about-the-author page), or None. Its first level-1 heading
    must carry ``{.unnumbered}`` or ``{-}`` and not begin "Appendix"."""

    for line in path.read_text(encoding="utf-8").splitlines():
        match = _HEADING.match(line)
        if not match:
            continue
        attrs = (match["attrs"] or "").split()
        title = match["title"].strip()
        unnumbered = ".unnumbered" in attrs or "-" in attrs
        if unnumbered and title and not title.lower().startswith("appendix"):
            return title
        return None
    return None


def chapter_label(path: Path) -> str:
    """Human label for a manuscript file, derived from its filename. An
    unnumbered back-matter part that is not an appendix locates by its own
    title: its filename letter only orders it, and as a locator it read as an
    appendix the Contents does not have (#288)."""

    name = path.name
    if name.startswith("00-"):
        return "Preface"
    if path.parent.name == "appendices":
        return _unnumbered_title(path) or name[0].upper()
    return str(int(name.split("-", 1)[0]))


def strip_markup(text: str) -> str:
    """Remove code blocks, inline code, and image lines before scanning."""

    text = re.sub(r"(?ms)^```.*?^```", "", text)
    text = re.sub(r"`[^`\n]*`", "", text)
    text = re.sub(r"(?m)^!\[.*$", "", text)
    return text


def generate() -> Path | None:
    root = booklib.root()
    terms_path = root / "config" / "index-terms.yaml"
    if not terms_path.is_file():
        return None
    with terms_path.open(encoding="utf-8") as handle:
        entries = yamlio.loads(handle.read())

    # A file the typed model accepts but the sort lambda cannot dereference
    # (a terms: wrapper, bare strings, an entry missing match) once crashed
    # here with `string indices must be integers`; refuse it up front with a
    # diagnostic that names the file (#207). check_source runs the same guard,
    # but a direct `press pdf` reaches this generator with no check in front.
    from . import config_schema

    config_schema.enforce_file(root, config_schema.INDEX_TERMS, entries)

    # The index takes the first free appendix letter.
    from .gen_authorities import next_letter, taken_letters

    letter = next_letter(taken_letters())
    output = root / "build" / "generated" / f"{letter}-index-of-subjects.md"

    sources = [
        (chapter_label(path), strip_markup(path.read_text(encoding="utf-8")).lower())
        for path in booklib.chapter_files()
    ]

    # A book whose back matter locates by title says so in the head note; a
    # book with none keeps the note word for word.
    titled = any(
        len(label) > 1 and not label.isdigit() and label != "Preface" for label, _ in sources
    )
    opening = (
        "Numbers are chapters, letters are appendices, and other back matter is"
        " named by its title; all stay put across"
        if titled
        else "Numbers are chapters and letters are appendices; both stay put across"
    )
    lines = [
        f"# Appendix {letter.upper()}: Index of subjects {{-}}",
        "",
        opening,
        "editions, which page numbers do not. The locations below are found in",
        "the text on every build, so the index cannot drift from the book.",
        "",
    ]

    silent: list[str] = []
    for entry in sorted(entries, key=lambda item: item["term"].lower()):
        patterns = [
            re.compile(rf"(?<![\w-]){re.escape(alt.lower())}(?![\w-])") for alt in entry["match"]
        ]
        hits = [
            label for label, text in sources if any(pattern.search(text) for pattern in patterns)
        ]
        if hits:
            # print_safe strips backslashes: pandoc's markdown reader
            # passes raw TeX through, and a curated data file must not
            # be a \input path into the engine.
            lines.append(f"**{gen_authorities.print_safe(entry['term'])}** · {', '.join(hits)}")
            lines.append("")
        else:
            silent.append(entry["term"])

    if silent:
        raise SystemExit(
            "gen_index: curated terms match nothing in the text: "
            + ", ".join(silent)
            + " (fix the patterns or remove the terms; silence is not allowed)"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    return output
