"""ISBN-10 <-> ISBN-13 conversion and the mod-11 check helpers."""

from __future__ import annotations

import pytest

from press import registrations


@pytest.mark.layer("unit")
def test_isbn13_to_isbn10_round_trips():
    # A known 978 pair: 978-0-306-40615-7 <-> 0-306-40615-2.
    assert registrations.isbn13_to_isbn10("9780306406157") == "0306406152"
    assert registrations.isbn10_to_isbn13("0306406152") == "9780306406157"


@pytest.mark.layer("unit")
def test_979_prefix_has_no_isbn10():
    # A valid 979 ISBN-13 has no ISBN-10 form.
    thirteen = registrations.isbn10_to_isbn13  # noqa: F841 (documenting intent)
    assert registrations.isbn13_to_isbn10("9791234567896") is None


@pytest.mark.layer("unit")
def test_isbn10_check_digit_can_be_x():
    # 0-8044-2957-X: the check digit is X.
    assert registrations.isbn10_check_digit("080442957") == "X"


@pytest.mark.layer("unit")
def test_issn_check_digit_matches_validation():
    # 0378-5955: check digit 5.
    assert registrations.issn_check_digit("0378595") == "5"
    assert registrations.issn_valid("0378-5955")


@pytest.mark.layer("unit")
def test_conversions_refuse_wrong_length():
    with pytest.raises(SystemExit):
        registrations.isbn10_check_digit("123")
    with pytest.raises(SystemExit):
        registrations.issn_check_digit("123")
    with pytest.raises(SystemExit):
        registrations.isbn10_to_isbn13("12345")
