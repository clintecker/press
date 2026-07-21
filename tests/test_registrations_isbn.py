"""ISBN block assignment: press mints the next unused ISBN-13 from a prefix
the publisher owns, offline. These tests pin the check-digit composition, the
block validation, the skip-used assignment, and LCCN normalization against the
Library of Congress's own worked examples.
"""

from __future__ import annotations

import pytest

from press import barcode, booklib, registrations


@pytest.mark.layer("unit")
def test_compose_isbn_appends_a_valid_check_digit():
    isbn = registrations.compose_isbn("9781960780", 4, 2)   # prefix + pub 04
    assert len(isbn) == 13
    assert isbn.startswith("978196078004")
    barcode.validate(isbn)   # raises if the check digit is wrong


@pytest.mark.layer("unit")
def test_block_spec_accepts_a_well_formed_block():
    assert registrations._block_spec({"prefix": "978-1-960780", "size": 100}) == ("9781960780", 2)
    # size 10 -> 1 publication digit -> 11-digit prefix.
    assert registrations._block_spec({"prefix": "978-1-9607801", "size": 10}) == ("9781960780" + "1", 1)


@pytest.mark.layer("unit")
@pytest.mark.parametrize("conf, message", [
    ({"prefix": "978-1-960780", "size": 50}, "power of ten"),
    ({"prefix": "978-1-96078", "size": 100}, "needs 10"),        # 9 digits, needs 10
    ({"prefix": "123-4-567890", "size": 100}, "978 or 979"),
])
def test_block_spec_refuses_a_malformed_block(conf, message):
    with pytest.raises(SystemExit, match=message):
        registrations._block_spec(conf)


@pytest.mark.layer("unit")
def test_next_isbn_skips_already_assigned_numbers(monkeypatch):
    # Publication 0 is taken by the print edition; the next mint is 1.
    taken = registrations.compose_isbn("9781960780", 0, 2)
    meta = {"registrations": {
        "isbn-block": {"prefix": "978-1-960780", "size": 100},
        "isbn": {"print": taken},
    }}
    monkeypatch.setattr(booklib, "metadata", lambda: meta)
    assert registrations.next_publication() == 1
    status = registrations.block_status()
    assert status.assigned == {0: "print"}
    assert status.free == 99


@pytest.mark.layer("unit")
def test_block_exhaustion_is_refused(monkeypatch):
    # A block of 10 with all ten numbers assigned mints nothing.
    isbns = {f"e{n}": registrations.compose_isbn("97819607801", n, 1) for n in range(10)}
    meta = {"registrations": {
        "isbn-block": {"prefix": "978-1-9607801", "size": 10},
        "isbn": isbns,
    }}
    monkeypatch.setattr(booklib, "metadata", lambda: meta)
    with pytest.raises(SystemExit, match="exhausted"):
        registrations.next_publication()


@pytest.mark.layer("unit")
def test_a_malformed_block_is_a_check_failure():
    problems = registrations.failures({"isbn-block": {"prefix": "978-1-96078", "size": 100}})
    assert any("isbn-block" in p and "needs 10" in p for p in problems)


@pytest.mark.layer("unit")
@pytest.mark.parametrize("raw, normal", [
    ("n78-890351", "n78890351"),         # LC example
    ("85-2 ", "85000002"),               # LC example (blanks + hyphen zero-fill)
    ("2001-000002", "2001000002"),       # LC example
    ("75-425165//r75", "75425165"),      # LC example (drop the slash suffix)
    ("  2026012345", "2026012345"),      # already normalized, blanks stripped
])
def test_lccn_normalize_matches_the_loc_examples(raw, normal):
    assert registrations.lccn_normalize(raw) == normal
