"""Generate the table of authorities from the book's claim ledger.

Books that make claims of fact (historical, technical, numerical) keep
config/authorities.yaml: a list of entries mapping a short exact fragment
of the manuscript text to the source that warrants it. Each build verifies
every claimed fragment still exists in the text and regenerates the
"Sources and authorities" appendix; a claim that matches nothing fails the
run, because an orphaned attribution is a citation for a sentence the book
no longer says. Books without the file simply have no such appendix.

Entry shape (the authorities-research workflow writes the same schema):
  - claim: "industrialize verification"        # exact fragment, whitespace-normalized
    file: "book/chapters/02-copy.md"           # optional but preferred; pins the claim
    authority: "Moxon, Mechanick Exercises (1683)"
    url: "https://archive.org/details/..."     # optional durable locator
    note: "optional dry line on what the source establishes"

Validation distinguishes its refusals: a malformed entry, a duplicate
claim, a claim missing from the whole book, a claim that moved out of
its declared file (with the file it moved to), and a claim matching
more than once (ambiguous: a citation should pin one sentence) each
say exactly what they are.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from . import booklib


def next_letter(taken: set[str]) -> str:
    for letter in "abcdefghijklmnopqrstuvwxy":
        if letter not in taken:
            return letter
    raise SystemExit("no appendix letters left")


def taken_letters() -> set[str]:
    letters = {p.name[0] for p in (booklib.root() / "book" / "appendices").glob("[a-z]-*.md")}
    generated = booklib.root() / "build" / "generated"
    if generated.is_dir():
        letters |= {p.name[0] for p in generated.glob("[a-z]-*.md")}
    return letters


def normalize(text: str) -> str:
    return " ".join(text.split())


def print_safe(text: str) -> str:
    """Make researched source text safe for the print fonts and for LaTeX.

    Web sources arrive with em/en dashes, curly quotes, and the occasional
    literal control sequence (a citation that mentions \\tracinglostchars).
    The house bans dashes and exotic glyphs in prose; generated appendices
    obey the same law, and a stray backslash must not reach the engine as a
    command.
    """

    replacements = {
        "\u2014": ", ", "\u2013": ", ", "\u2012": ", ", "\u2212": "-",
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2026": "...", "\u00a0": " ", "\\": " ",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return normalize(text)


def chapter_label(path: Path) -> str:
    name = path.name
    if name.startswith("00-"):
        return "the preface"
    if path.parent.name == "appendices":
        return f"appendix {name[0].upper()}"
    return f"chapter {int(name.split('-', 1)[0])}"


def generate() -> Path | None:
    ledger = booklib.root() / "config" / "authorities.yaml"
    if not ledger.is_file():
        return None
    with ledger.open(encoding="utf-8") as handle:
        entries = yaml.safe_load(handle) or []

    sources = [
        (path, chapter_label(path), normalize(path.read_text(encoding="utf-8")))
        for path in booklib.chapter_files()
    ]

    diagnostics: list[str] = []
    located: list[tuple[str, str, dict]] = []
    seen: dict[str, int] = {}
    if not isinstance(entries, list):
        raise SystemExit(
            "gen_authorities: config/authorities.yaml must be a list of entries"
        )
    by_relpath = {
        str(path.relative_to(booklib.root())): (path, label, text)
        for path, label, text in sources
    }
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            diagnostics.append(f"entry {index}: malformed (not a mapping)")
            continue
        claim = entry.get("claim")
        authority = entry.get("authority")
        structural = False
        if not isinstance(claim, str) or not claim.strip():
            diagnostics.append(f"entry {index}: malformed (claim missing or empty)")
            structural = True
        if not isinstance(authority, str) or not authority.strip():
            diagnostics.append(f"entry {index}: malformed (authority missing or empty)")
            structural = True
        if structural:
            continue
        fragment = normalize(claim)
        if fragment in seen:
            diagnostics.append(
                f'entry {index}: duplicate claim "{claim}" (first stated at '
                f"entry {seen[fragment]})"
            )
            continue
        seen[fragment] = index

        counts = [
            (path, label, text.count(fragment)) for path, label, text in sources
        ]
        hits = [(p, l, n) for p, l, n in counts if n]
        declared = entry.get("file")
        if declared:
            home = by_relpath.get(str(declared))
            if home is None:
                diagnostics.append(
                    f'entry {index}: declares unknown file "{declared}"'
                )
                continue
            count_here = home[2].count(fragment)
            if count_here == 1:
                located.append((home[0].name, home[1], entry))
            elif count_here > 1:
                diagnostics.append(
                    f'entry {index}: ambiguous, "{claim}" appears '
                    f"{count_here} times in {declared}; lengthen the fragment"
                )
            elif hits:
                where = ", ".join(str(p.relative_to(booklib.root())) for p, _, _ in hits)
                diagnostics.append(
                    f'entry {index}: moved, "{claim}" is no longer in '
                    f"{declared} but appears in {where}; update file:"
                )
            else:
                diagnostics.append(
                    f'entry {index}: missing, "{claim}" matches nothing in the '
                    "book (the text moved out from under its citation)"
                )
        else:
            total = sum(n for _, _, n in hits)
            if total == 1:
                located.append((hits[0][0].name, hits[0][1], entry))
            elif total == 0:
                diagnostics.append(
                    f'entry {index}: missing, "{claim}" matches nothing in the '
                    "book (the text moved out from under its citation)"
                )
            else:
                where = ", ".join(
                    f"{p.relative_to(booklib.root())} x{n}" for p, _, n in hits
                )
                diagnostics.append(
                    f'entry {index}: ambiguous, "{claim}" matches {total} '
                    f"times ({where}); lengthen the fragment or declare file:"
                )

    if diagnostics:
        raise SystemExit(
            "gen_authorities: the ledger does not hold:\n"
            + "\n".join(f"  - {d}" for d in diagnostics)
        )

    # The full table of authorities is published as its own document rather
    # than bloating the book; enforcement still runs above on every build.
    book = booklib.book()
    imprint = f", {book.publisher}" if book.publisher else ""
    dated = f", {book.date}" if book.date else ""
    lines = [
        f"# {book.title}: sources and authorities",
        "",
        f"*Companion to {book.title} by {', '.join(book.authors)}"
        f"{imprint}{dated}.*",
        "",
        "Where the book states a matter of fact it did not invent, the",
        "statement is listed here against the authority for it. Each claim is",
        "checked against the text of the book on every build, so a citation",
        "whose sentence has left the book fails the run and cannot rot here",
        "unnoticed.",
        "",
    ]
    located.sort(key=lambda item: item[0])
    current = None
    for filename, label, entry in located:
        if label != current:
            lines.append(f"## In {label}")
            lines.append("")
            current = label
        note = f" {print_safe(entry['note'])}" if entry.get("note") else ""
        locator = f" <{print_safe(entry['url'])}>" if entry.get("url") else ""
        lines.append(
            f'- "{print_safe(entry["claim"])}": '
            f'{print_safe(entry["authority"])}.{locator}{note}'
        )
        lines.append("")

    output = booklib.root() / "dist" / f"{booklib.slug()}-sources.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    # Not appended to the book: the bibliography is a separate document.
    return None
