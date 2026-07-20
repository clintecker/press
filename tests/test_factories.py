"""The book factory is trustworthy: every preset builds, every fact is
inspectable, and two books cannot contaminate one another.

A test factory that lies is worse than no factory, so this suite proves
the factory before the rest of the suite leans on it.
"""

from __future__ import annotations

import pytest

from tests import factories


@pytest.mark.parametrize("name", sorted(factories.PRESETS))
def test_every_preset_builds(name, tmp_path):
    handle = factories.PRESETS[name]().build(tmp_path)
    assert handle.root.is_dir()
    assert (handle.root / "config" / "metadata.yaml").is_file()
    assert list((handle.root / "book" / "chapters").glob("*.md"))


def test_facts_are_inspectable(tmp_path):
    """A test reads what it declared from the handle, not a hidden
    default."""

    handle = (
        factories.BookFactory(slug="inspect-book", title="Inspect")
        .with_sentinels("a declared sentinel")
        .with_secret(".env")
        .build(tmp_path)
    )
    assert handle.slug == "inspect-book"
    assert handle.metadata["title"] == "Inspect"
    assert "a declared sentinel" in handle.sentinels
    assert ".env" in handle.secrets


def test_minimal_book_is_a_valid_book(tmp_path):
    handle = factories.minimal().build(tmp_path)
    with handle.use():
        from press import booklib, check_source

        assert booklib.slug() == handle.slug
        assert check_source.main() == 0


def test_hostile_metadata_is_refused_not_crashed(tmp_path):
    handle = factories.hostile_input().build(tmp_path)
    with handle.use():
        from press import booklib

        booklib.metadata.cache_clear()
        with pytest.raises(SystemExit):
            booklib.metadata()


def test_two_books_do_not_contaminate(tmp_path):
    """Build two books, enter each, and prove the press sees exactly the
    book it is pointed at, with no leak from the other through a cache
    or the working directory."""

    from press import booklib

    first = factories.BookFactory(slug="first-book", title="First").build(tmp_path / "a")
    second = factories.BookFactory(slug="second-book", title="Second").build(tmp_path / "b")

    with first.use():
        assert booklib.slug() == "first-book"
        assert booklib.book().title == "First"
    with second.use():
        assert booklib.slug() == "second-book"
        assert booklib.book().title == "Second"
    # Re-entering the first must still see the first, proving the second
    # left no memoized answer behind.
    with first.use():
        assert booklib.slug() == "first-book"
        assert booklib.book().title == "First"


def test_use_restores_cwd_and_book_root(tmp_path):
    import os
    from pathlib import Path

    before_cwd = Path.cwd()
    before_root = os.environ.get("BOOK_ROOT")
    handle = factories.minimal().build(tmp_path)
    with handle.use():
        assert Path.cwd() == handle.root
    assert Path.cwd() == before_cwd
    assert os.environ.get("BOOK_ROOT") == before_root


def test_override_book_carries_its_css(tmp_path):
    handle = factories.override().build(tmp_path)
    assert (handle.root / "assets" / "web" / "reader.css").is_file()
    assert (handle.root / "assets" / "web" / "extra.css").is_file()


def test_no_prebuilt_dist_is_smuggled(tmp_path):
    """The factory makes sources only; a dist directory must not appear
    until a test builds it explicitly."""

    handle = factories.full().build(tmp_path)
    assert not (handle.root / "dist").exists()
