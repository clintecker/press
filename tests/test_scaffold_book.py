"""A scaffolded book is a working book: the factory fixture proves it.

These tests exercise the shared scaffolded_book fixture so the rest of
the suite can trust it, and prove the properties a fresh book must
have before an author writes a word.
"""

from __future__ import annotations


def test_scaffold_is_a_book(scaffolded_book):
    from press import booklib

    assert (scaffolded_book / "config" / "metadata.yaml").is_file()
    assert booklib.slug()
    assert booklib.book().title


def test_scaffold_passes_editorial_check(scaffolded_book):
    from press import check_source

    assert check_source.main() == 0


def test_scaffold_carries_no_original_identity(scaffolded_book):
    """The neutral-scaffold law: a fresh book names no prior book, no
    person, and no imprint the author did not choose."""

    for path in scaffolded_book.rglob("*"):
        if not path.is_file() or path.suffix in {".jpg", ".png", ".pdf"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        assert "make-ready" not in text
        assert "2389" not in text
