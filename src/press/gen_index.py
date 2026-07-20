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


def chapter_label(path: Path) -> str:
    """Human label for a manuscript file, derived from its filename."""

    name = path.name
    if name.startswith("00-"):
        return "Preface"
    if path.parent.name == "appendices":
        return name[0].upper()
    return str(int(name.split("-", 1)[0]))


def strip_markup(text: str) -> str:
    """Remove code blocks, inline code, and image lines before scanning."""

    text = re.sub(r"(?ms)^```.*?^```", "", text)
    text = re.sub(r"`[^`\n]*`", "", text)
    text = re.sub(r"(?m)^!\[.*$", "", text)
    return text


def generate() -> Path | None:
    terms_path = booklib.root() / "config" / "index-terms.yaml"
    if not terms_path.is_file():
        return None
    with terms_path.open(encoding="utf-8") as handle:
        entries = yamlio.loads(handle.read())

    # The index takes the first free appendix letter.
    from .gen_authorities import next_letter, taken_letters
    letter = next_letter(taken_letters())
    output = booklib.root() / "build" / "generated" / f"{letter}-index-of-subjects.md"

    sources = [
        (chapter_label(path), strip_markup(path.read_text(encoding="utf-8")).lower())
        for path in booklib.chapter_files()
    ]

    lines = [
        f"# Appendix {letter.upper()}: Index of subjects {{-}}",
        "",
        "Numbers are chapters and letters are appendices; both stay put across",
        "editions, which page numbers do not. The locations below are found in",
        "the text on every build, so the index cannot drift from the book.",
        "",
    ]

    silent: list[str] = []
    for entry in sorted(entries, key=lambda item: item["term"].lower()):
        patterns = [
            re.compile(rf"(?<![\w-]){re.escape(alt.lower())}(?![\w-])")
            for alt in entry["match"]
        ]
        hits = [
            label
            for label, text in sources
            if any(pattern.search(text) for pattern in patterns)
        ]
        if hits:
            # print_safe strips backslashes: pandoc's markdown reader
            # passes raw TeX through, and a curated data file must not
            # be a \input path into the engine.
            lines.append(
                f"**{gen_authorities.print_safe(entry['term'])}** · {', '.join(hits)}"
            )
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
