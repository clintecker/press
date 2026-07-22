"""PCN application prep: the PrePub Book Link field values, assembled.

A Library of Congress Control Number is free through the Preassigned Control
Number program, but the only way in is the PrePub Book Link *web form* -- no
apply-by-API. So the automatable work is assembling the field values a
self-publisher types into that form, from config the book already holds, and
flagging what the form needs that the book does not have. The returned LCCN
is stored back with ``registrations.lccn`` and normalized with
``registrations.lccn_normalize``.

This is a report, not a submission: it never contacts the LC, because the LC
does not accept one from a program.
"""

from __future__ import annotations

from .bookmodel import Book


def fields(book: Book, *, lang: str | None, print_isbn: str | None) -> list[tuple[str, str]]:
    """The PrePub Book Link field values from config, in form order. A value
    the book does not carry is an explicit ``(needed on the form)`` so the
    gap is visible rather than silently blank."""

    missing = "(needed on the form)"
    authors = "; ".join(book.authors) if book.authors else missing
    return [
        ("Title", book.title or missing),
        ("Subtitle", book.subtitle or ""),
        ("Author(s)", authors),
        ("Publisher name", book.publisher or missing),
        ("Place of publication", book.publisher_place or missing),
        ("Projected year of publication", book.year or missing),
        ("Print ISBN", print_isbn or "(assign one first: press isbn assign print)"),
        ("Language", lang or "en-US"),
        ("Medium", "print (monograph)"),
    ]


def render(book: Book, rows: list[tuple[str, str]], lccn: str | None) -> str:
    """A labelled report of the field values, plus the two obligations the
    program attaches: eligibility and the deposit copy."""

    width = max(len(label) for label, _ in rows)
    lines = [
        "Library of Congress PCN -- PrePub Book Link field values",
        "https://www.loc.gov/publish/pcn/  (self-publishers use PCN, not CIP)",
        "",
    ]
    for label, value in rows:
        if value:
            lines.append(f"  {label.ljust(width)}  {value}")
    lines.append("")
    if lccn:
        lines.append(f"An LCCN is already recorded for this book: {lccn}")
    else:
        lines.append(
            "No LCCN recorded yet. Submit the fields above through PrePub Book "
            "Link; when the LCCN comes back, store it with "
            "`press config set registrations.lccn <number>`."
        )
    lines.append(
        "Obligations: a self-publisher is eligible for a PCN (not CIP), and a "
        "copy of the published book must be deposited with the Library of "
        "Congress within three months of publication."
    )
    return "\n".join(lines) + "\n"
