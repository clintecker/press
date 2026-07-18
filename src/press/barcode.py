"""EAN-13 encoding for the cover wrap barcode.

The barcode is a generator, never an image pasted from a website: the
ISBN in config is the single stated fact, the check digit is validated
rather than trusted, and the bars are emitted as module runs for the
TeX layer to draw as rules (vector, printer-sharp at any size).
"""

from __future__ import annotations

L_CODES = ["0001101", "0011001", "0010011", "0111101", "0100011",
           "0110001", "0101111", "0111011", "0110111", "0001011"]
G_CODES = ["0100111", "0110011", "0011011", "0100001", "0011101",
           "0111001", "0000101", "0010001", "0001001", "0010111"]
R_CODES = [code.translate(str.maketrans("01", "10")) for code in L_CODES]
PARITY = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG",
          "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"]


def digits_of(isbn: str) -> list[int]:
    cleaned = [ch for ch in isbn if ch.isdigit()]
    if len(cleaned) != 13:
        raise SystemExit(f"an EAN-13 needs 13 digits; got {len(cleaned)} from {isbn!r}")
    return [int(ch) for ch in cleaned]


def check_digit(first_twelve: list[int]) -> int:
    total = sum(d * (1 if i % 2 == 0 else 3) for i, d in enumerate(first_twelve))
    return (10 - total % 10) % 10


def validate(isbn: str) -> str:
    """The 13 digits, or a refusal naming the bad check digit."""

    digits = digits_of(isbn)
    expected = check_digit(digits[:12])
    if digits[12] != expected:
        raise SystemExit(
            f"ISBN {isbn} fails its check digit (ends {digits[12]}, "
            f"arithmetic says {expected}); a mistyped ISBN on a cover is unrecoverable"
        )
    return "".join(str(d) for d in digits)


def modules(isbn: str) -> str:
    """The 95-module bar pattern: 1 is ink, 0 is space."""

    digits = digits_of(validate(isbn))
    parity = PARITY[digits[0]]
    left = "".join(
        (L_CODES if kind == "L" else G_CODES)[digit]
        for kind, digit in zip(parity, digits[1:7])
    )
    right = "".join(R_CODES[digit] for digit in digits[7:13])
    return "101" + left + "01010" + right + "101"


def runs(isbn: str) -> list[tuple[str, int]]:
    """The pattern as (ink|space, module_count) runs for rule drawing."""

    pattern = modules(isbn)
    out: list[tuple[str, int]] = []
    for module in pattern:
        kind = "ink" if module == "1" else "space"
        if out and out[-1][0] == kind:
            out[-1] = (kind, out[-1][1] + 1)
        else:
            out.append((kind, 1))
    return out
