"""Generate the table of authorities from the book's claim ledger.

Books that make claims of fact (historical, technical, numerical) keep
config/authorities.yaml: a list of entries mapping a short exact fragment
of the manuscript text to the source that warrants it. Each build verifies
every claimed fragment still exists in the text and regenerates the
"Sources and authorities" appendix; a claim that matches nothing fails the
run, because an orphaned attribution is a citation for a sentence the book
no longer says. Books without the file simply have no such appendix.

Entry shape:
  - claim: "industrialize verification"        # exact fragment, whitespace-normalized
    authority: "Moxon, Mechanick Exercises (1683)"
    note: "optional dry line on what the source establishes"
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

    orphans: list[str] = []
    located: list[tuple[str, str, dict]] = []
    for entry in entries:
        fragment = normalize(entry["claim"])
        hits = [(path.name, label) for path, label, text in sources if fragment in text]
        if not hits:
            orphans.append(entry["claim"])
            continue
        located.append((hits[0][0], hits[0][1], entry))

    if orphans:
        raise SystemExit(
            "gen_authorities: claims match nothing in the text: "
            + "; ".join(f'"{c}"' for c in orphans)
            + " (the text moved out from under its citations; update the ledger)"
        )

    letter = next_letter(taken_letters())
    lines = [
        f"# Appendix {letter.upper()}: sources and authorities {{-}}",
        "",
        "Where this book states a matter of fact about the printing trade or",
        "anything else it did not invent, the statement is listed here against",
        "the authority for it. Each claim is checked against the text on every",
        "build; a citation whose sentence has left the book fails the run.",
        "",
    ]
    located.sort(key=lambda item: item[0])
    current = None
    for filename, label, entry in located:
        if label != current:
            lines.append(f"**In {label}**")
            lines.append("")
            current = label
        note = f" {normalize(entry['note'])}" if entry.get("note") else ""
        lines.append(f'- "{normalize(entry["claim"])}": {normalize(entry["authority"])}.{note}')
    lines.append("")

    output = booklib.root() / "build" / "generated" / f"{letter}-sources-and-authorities.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    return output
