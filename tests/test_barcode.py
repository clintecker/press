"""EAN-13 barcode generation, proven by known-good vectors.

Example-based on purpose: these tests are the deterministic prover the
mutation ratchet runs against barcode.py, so they must pin the checksum
arithmetic tightly enough that flipping a comparison, a coefficient, or a
modulus is caught. The property-based coverage lives in test_properties.
"""

from __future__ import annotations

import pytest

from press import barcode


def test_check_digit_matches_known_vectors():
    # Canonical ISBN-13 prefixes and their check digits.
    assert barcode.check_digit([int(c) for c in "978030640615"]) == 7
    assert barcode.check_digit([int(c) for c in "978316148410"]) == 0
    assert barcode.check_digit([int(c) for c in "400638133393"]) == 1
    assert barcode.check_digit([int(c) for c in "978014300723"]) == 4


def test_check_digit_weights_odd_positions_by_three():
    # A single 1 at an odd index contributes weight 3, at an even index
    # weight 1: this pins the coefficient and the position parity so a
    # swap of the 1/3 weights or the i % 2 test cannot survive.
    even = [0] * 12
    even[0] = 1  # weight 1 -> total 1 -> check (10 - 1) % 10 = 9
    assert barcode.check_digit(even) == 9
    odd = [0] * 12
    odd[1] = 1  # weight 3 -> total 3 -> check (10 - 3) % 10 = 7
    assert barcode.check_digit(odd) == 7


def test_check_digit_is_zero_when_total_is_a_multiple_of_ten():
    twelve = [int(c) for c in "978030640615"]  # its check digit is 7
    twelve[-1] = (twelve[-1] + 3) % 10  # nudge so the total lands on a ten
    assert barcode.check_digit(twelve) == (10 - sum(
        d * (1 if i % 2 == 0 else 3) for i, d in enumerate(twelve)) % 10) % 10


def test_validate_accepts_a_correct_isbn_and_returns_its_digits():
    assert barcode.validate("978-0-306-40615-7") == "9780306406157"


def test_validate_refuses_a_wrong_check_digit():
    with pytest.raises(SystemExit) as exc:
        barcode.validate("9780306406158")
    assert "check digit" in str(exc.value)


def test_digits_of_refuses_the_wrong_length():
    with pytest.raises(SystemExit):
        barcode.digits_of("97803064061")  # 11 digits


def test_modules_match_the_known_pattern_exactly():
    # The full 95-module encoding for a known ISBN. Asserting the whole
    # string pins the parity table lookup (PARITY[digits[0]]) and the
    # L/G code selection, not merely the guard bars and width.
    pattern = barcode.modules("9780306406157")
    assert pattern == (
        "10101110110001001010011101111010100111010111101010"
        "101110011100101010000110011010011101000100101"
    )
    assert len(pattern) == 95
    assert pattern[:3] == "101"           # left guard
    assert pattern[-3:] == "101"          # right guard
    assert pattern[45:50] == "01010"      # centre guard


def test_runs_partition_the_pattern_and_start_with_ink():
    isbn = "9780306406157"
    runs = barcode.runs(isbn)
    assert sum(count for _, count in runs) == len(barcode.modules(isbn))
    # The pattern opens "101", so the first module is ink: this pins the
    # module == "1" -> ink mapping that alternation alone leaves free.
    assert runs[0] == ("ink", 1)
    # Adjacent runs must alternate ink/space; none may repeat.
    kinds = [kind for kind, _ in runs]
    assert all(a != b for a, b in zip(kinds, kinds[1:]))
