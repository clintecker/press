"""The registrations ledger: ISBN, ISSN, LCCN stated once in config.

Numbers are validated arithmetically, never trusted: a mistyped ISBN on
a printed cover is unrecoverable. The literal value "pending" is the
one honest placeholder; it renders as pending wherever the number would
appear, and it blocks a retail edition until the real number lands.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from . import barcode, booklib

PENDING = "pending"


def block() -> dict:
    return booklib.metadata().get("registrations") or {}


# --------------------------------------------------------------------------
# ISBN block assignment.
#
# There is no API that issues an ISBN: you buy a registrant prefix and a
# bounded pool of publication slots from your agency (Bowker in the US), once,
# through their web checkout. After that, assigning a publication number to
# each edition and computing the check digit is pure arithmetic you do
# yourself -- no network call exists or is needed. This is that arithmetic:
# given the prefix you own and the block size, press mints the next unused
# ISBN-13. A "size" of 10/100/1000 leaves 1/2/3 digits for the publication
# element, so the owned prefix is 11/10/9 digits (978 + group + registrant).
# --------------------------------------------------------------------------

_VALID_SIZES = (10, 100, 1000, 10000, 100000, 1000000)


def isbn_block() -> dict | None:
    value = block().get("isbn-block")
    return value if isinstance(value, dict) else None


def _block_spec(conf: dict | None = None) -> tuple[str, int]:
    """(prefix digits, publication-element width) for the owned block,
    validated. Reads the book's block unless one is passed (so a proposed
    edit can be validated). Raises with a locatable message if malformed."""

    if conf is None:
        conf = isbn_block()
    if not conf:
        raise SystemExit(
            "no registrations.isbn-block configured; set the prefix and size "
            "your ISBN agency gave you (e.g. prefix: 978-1-960780, size: 100)"
        )
    prefix_digits = "".join(ch for ch in str(conf.get("prefix", "")) if ch.isdigit())
    size = conf.get("size")
    if size not in _VALID_SIZES:
        raise SystemExit(
            f"registrations.isbn-block.size must be a power of ten "
            f"(10, 100, 1000, ...); got {size!r}"
        )
    width = round(math.log10(int(size)))
    if not prefix_digits.startswith(("978", "979")):
        raise SystemExit("registrations.isbn-block.prefix must start with 978 or 979")
    if len(prefix_digits) != 12 - width:
        raise SystemExit(
            f"registrations.isbn-block.prefix has {len(prefix_digits)} digits; a block "
            f"of {size} needs {12 - width} (978 + group + registrant), leaving {width} "
            "for the publication element"
        )
    return prefix_digits, width


def compose_isbn(prefix_digits: str, publication: int, width: int) -> str:
    """The full 13-digit ISBN for a publication number under a prefix."""

    twelve = prefix_digits + str(publication).zfill(width)
    check = barcode.check_digit([int(ch) for ch in twelve])
    return twelve + str(check)


def hyphenate(isbn13: str) -> str:
    """Hyphenate an assigned ISBN using the block prefix's own hyphenation,
    then a hyphen before the publication element and the check digit."""

    conf = isbn_block() or {}
    prefix = str(conf.get("prefix", "")).strip().rstrip("-")
    prefix_digits, width = _block_spec()
    publication = isbn13[len(prefix_digits):12]
    check = isbn13[12]
    joiner = "-" if "-" in prefix else ""
    return f"{prefix}{joiner or '-'}{publication}-{check}" if prefix else isbn13


def _used_publications(prefix_digits: str, width: int) -> dict[int, str]:
    """Publication numbers already assigned in this book's isbn map that fall
    under the block prefix, mapped to the edition holding each."""

    used: dict[int, str] = {}
    for edition, value in isbn_map().items():
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        if len(digits) == 13 and digits.startswith(prefix_digits):
            used[int(digits[len(prefix_digits):12])] = edition
    return used


@dataclass(frozen=True)
class BlockStatus:
    prefix: str                # the hyphenated prefix as configured
    prefix_digits: str         # the same, digits only
    size: int
    width: int
    assigned: dict[int, str]   # publication number -> edition holding it

    @property
    def free(self) -> int:
        return self.size - len(self.assigned)

    def assignments(self) -> list[tuple[str, str]]:
        """(hyphenated ISBN, edition) for every assigned slot, in slot order."""

        return [
            (hyphenate(compose_isbn(self.prefix_digits, publication, self.width)), edition)
            for publication, edition in sorted(self.assigned.items())
        ]


def block_status() -> BlockStatus:
    prefix_digits, width = _block_spec()
    conf = isbn_block() or {}
    return BlockStatus(
        prefix=str(conf.get("prefix", prefix_digits)),
        prefix_digits=prefix_digits,
        size=int(conf["size"]),
        width=width,
        assigned=_used_publications(prefix_digits, width),
    )


def next_publication() -> int:
    """The lowest publication number in the block not yet assigned."""

    prefix_digits, width = _block_spec()
    used = _used_publications(prefix_digits, width)
    for publication in range(10 ** width):
        if publication not in used:
            return publication
    raise SystemExit(
        f"ISBN block exhausted: all {10 ** width} numbers under {prefix_digits} "
        "are assigned. Buy another prefix from your agency."
    )


def next_isbn() -> str:
    """The next unused ISBN-13 from the block, hyphenated for display."""

    prefix_digits, width = _block_spec()
    return hyphenate(compose_isbn(prefix_digits, next_publication(), width))


def lccn_normalize(value: str) -> str:
    """The Library of Congress canonical (normalized) LCCN: remove blanks,
    drop a forward slash and everything after it, and expand a hyphen by
    zero-filling the serial to six digits (loc.gov/marc/lccn-namespace.html)."""

    text = value.replace(" ", "")
    text = text.split("/", 1)[0]
    if "-" in text:
        head, serial = text.rsplit("-", 1)
        text = head + serial.rjust(6, "0")
    return text


def _isbn_map(reg: dict) -> dict:
    value = reg.get("isbn")
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SystemExit(
            "registrations isbn must be a mapping of editions "
            '(isbn: {print: "...", epub: "..."}), not a single value'
        )
    return value


def isbn_map() -> dict:
    return _isbn_map(block())


def raw_isbn(edition: str) -> str | None:
    """The ISBN exactly as config states it, hyphens and all."""

    value = isbn_map().get(edition)
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


def issn_check_digit(first_seven: str) -> str:
    """The ISSN check character for seven digits: mod-11, 'X' for a remainder
    of 10. The same arithmetic ``issn_valid`` verifies, exposed so a caller can
    compose an ISSN, not only check one."""

    digits = [ch for ch in first_seven if ch.isdigit()]
    if len(digits) != 7:
        raise SystemExit(f"an ISSN check digit needs seven digits; got {first_seven!r}")
    total = sum(int(d) * w for d, w in zip(digits, range(8, 1, -1)))
    check = (11 - total % 11) % 11
    return "X" if check == 10 else str(check)


def isbn10_check_digit(first_nine: str) -> str:
    """The ISBN-10 check character: mod-11 with weights 10..2, 'X' for 10."""

    digits = [ch for ch in first_nine if ch.isdigit()]
    if len(digits) != 9:
        raise SystemExit(f"an ISBN-10 check digit needs nine digits; got {first_nine!r}")
    total = sum(int(d) * w for d, w in zip(digits, range(10, 1, -1)))
    check = (11 - total % 11) % 11
    return "X" if check == 10 else str(check)


def isbn13_to_isbn10(isbn13: str) -> str | None:
    """The ISBN-10 for a 978-prefixed ISBN-13, or ``None`` for a 979 prefix
    (which has no ISBN-10). The middle nine digits are recheck-summed under
    mod-11, so this is a real conversion, not a reformat."""

    from . import barcode

    digits = barcode.validate(isbn13)  # 13 clean digits or a refusal
    if not digits.startswith("978"):
        return None
    core = digits[3:12]
    return core + isbn10_check_digit(core)


def isbn10_to_isbn13(isbn10: str) -> str:
    """The 978-prefixed ISBN-13 for an ISBN-10, with a fresh EAN-13 check
    digit. Accepts hyphens and a trailing 'X'."""

    from . import barcode

    core = [ch for ch in isbn10.upper() if ch.isdigit() or ch == "X"]
    if len(core) != 10:
        raise SystemExit(f"an ISBN-10 has ten characters; got {isbn10!r}")
    twelve = [int(ch) for ch in ("978" + "".join(core[:9]))]
    return "978" + "".join(core[:9]) + str(barcode.check_digit(twelve))


def failures(reg: dict | None = None) -> list[str]:
    """Every invalid registration, as check-style failure lines. Reads the
    book's registrations from disk unless a proposed block is passed (the
    `press config` writer validates its edit before it touches a byte)."""

    found: list[str] = []
    if reg is None:
        reg = block()
    try:
        editions = _isbn_map(reg)
    except SystemExit as exc:
        return [str(exc)]
    for edition, value in editions.items():
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

    conf = reg.get("isbn-block")
    if isinstance(conf, dict) and conf.get("prefix") and conf.get("size") is not None:
        # Validate only a complete block: setting the prefix and size one at a
        # time passes through transiently-incomplete states that are not errors.
        try:
            _block_spec(conf)
        except SystemExit as exc:
            found.append(str(exc))

    if reg.get("retail"):
        isbns = editions
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
