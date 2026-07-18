"""The registrations ledger: ISBN, ISSN, LCCN stated once in config.

Numbers are validated arithmetically, never trusted: a mistyped ISBN on
a printed cover is unrecoverable. The literal value "pending" is the
one honest placeholder; it renders as pending wherever the number would
appear, and it blocks a retail edition until the real number lands.
"""

from __future__ import annotations

import re

from . import barcode, booklib

PENDING = "pending"


def block() -> dict:
    return booklib.metadata().get("registrations") or {}


def raw_isbn(edition: str) -> str | None:
    """The ISBN exactly as config states it, hyphens and all."""

    value = (block().get("isbn") or {}).get(edition)
    return str(value).strip() if value else None


def isbn(edition: str) -> str | None:
    """The validated 13 digits for an edition (print, epub), None if
    unset or pending."""

    value = raw_isbn(edition)
    if not value or value.lower() == PENDING:
        return None
    try:
        return barcode.validate(value)
    except SystemExit as exc:
        raise SystemExit(
            f"registrations isbn {edition} in config/metadata.yaml: {exc}"
        ) from exc


def isbn_display(edition: str) -> str | None:
    """What the colophon prints: the author's typed form (the agency's
    hyphenation), validated first; [pending] while waiting; None if the
    edition is not registered at all."""

    value = raw_isbn(edition)
    if not value:
        return None
    if value.lower() == PENDING:
        return "[pending]"
    isbn(edition)
    return value


def lccn_display() -> str | None:
    value = block().get("lccn")
    if not value:
        return None
    return "[pending]" if str(value).strip().lower() == PENDING else str(value)


def issn_valid(value: str) -> bool:
    digits = [ch for ch in value.upper() if ch.isdigit() or ch == "X"]
    if len(digits) != 8 or "X" in digits[:7]:
        return False
    total = sum(int(d) * w for d, w in zip(digits[:7], range(8, 1, -1)))
    check = (11 - total % 11) % 11
    return digits[7] == ("X" if check == 10 else str(check))


def lccn_plausible(value: str) -> bool:
    """LCCNs have no check digit; hold the shape, not the arithmetic."""

    return bool(re.fullmatch(r"[a-z]{0,3}\d{8,12}", value.replace("-", "").replace(" ", "").lower()))


def failures() -> list[str]:
    """Every invalid registration, as check-style failure lines."""

    found: list[str] = []
    reg = block()
    for edition, value in (reg.get("isbn") or {}).items():
        text = str(value).strip()
        if text.lower() == PENDING:
            continue
        try:
            barcode.validate(text)
        except SystemExit as exc:
            found.append(f"registrations isbn {edition}: {exc}")
    issn = reg.get("issn")
    if issn and str(issn).strip().lower() != PENDING and not issn_valid(str(issn)):
        found.append(f"registrations issn fails its check digit: {issn}")
    lccn = reg.get("lccn")
    if lccn and str(lccn).strip().lower() != PENDING and not lccn_plausible(str(lccn)):
        found.append(f"registrations lccn does not look like an LCCN: {lccn}")

    if reg.get("retail"):
        isbns = reg.get("isbn") or {}
        pending = [
            f"isbn {edition} missing"
            for edition in ("print", "epub") if edition not in isbns
        ]
        pending += [
            f"isbn {edition}" for edition, value in isbns.items()
            if str(value).strip().lower() == PENDING
        ]
        pending += [
            name for name in ("issn", "lccn")
            if reg.get(name) and str(reg[name]).strip().lower() == PENDING
        ]
        if pending:
            found.append(
                "retail edition declared while registrations are absent "
                "or pending: " + ", ".join(pending)
            )
    return found
