"""PCN prep: the PrePub Book Link field values from config, with gaps visible."""

from __future__ import annotations

import pytest

from press import pcn
from press.bookmodel import Book


def _book(**over) -> Book:
    base = dict(
        root=None, title="The Analytical Engine", subtitle="Notes",
        authors=("Ada Lovelace", "Charles Babbage"), date="2026", year="2026",
        copyright="2026", publisher="LGTM Publishing", publisher_place="London",
        description="A book.", keywords=(), slug="x", repository=None,
        site_url=None, trim_width=6.0, trim_height=9.0, sentinels=(), min_pages=1,
        print_config={}, registrations={},
    )
    base.update(over)
    return Book(**base)


@pytest.mark.layer("unit")
def test_fields_include_all_authors_and_the_title():
    rows = dict(pcn.fields(_book(), lang="en-US", print_isbn="9781234567897"))
    assert rows["Title"] == "The Analytical Engine"
    assert rows["Author(s)"] == "Ada Lovelace; Charles Babbage"
    assert rows["Print ISBN"] == "9781234567897"


@pytest.mark.layer("unit")
def test_missing_publisher_is_flagged_not_blank():
    rows = dict(pcn.fields(_book(publisher=None), lang="en", print_isbn="9781234567897"))
    assert "needed on the form" in rows["Place of publication"] or \
        "needed on the form" in rows["Publisher name"]


@pytest.mark.layer("unit")
def test_no_isbn_points_at_the_assign_command():
    rows = dict(pcn.fields(_book(), lang="en", print_isbn=None))
    assert "press isbn assign" in rows["Print ISBN"]


@pytest.mark.layer("unit")
def test_render_names_the_deposit_obligation_and_lccn_state():
    book = _book()
    rows = pcn.fields(book, lang="en", print_isbn="9781234567897")
    without = pcn.render(book, rows, None)
    assert "deposit" in without.lower()
    assert "No LCCN recorded" in without
    withlccn = pcn.render(book, rows, "2026012345")
    assert "2026012345" in withlccn
