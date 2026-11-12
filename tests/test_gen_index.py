"""The subject index's locators: a chapter by its number, an appendix by its
letter, and an unnumbered back-matter part that is not an appendix (a
colophon) by its own title, never by the letter its filename happens to sort
under (#288: a z-colophon.md once located as "Z", an appendix the Contents
does not have)."""

from __future__ import annotations

from pathlib import Path

import pytest

from press import gen_index
from tests import factories


def _part(tmp_path: Path, rel: str, body: str) -> Path:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("rel", "body", "label"),
    [
        ("book/chapters/00-preface.md", "# Preface {.unnumbered}\n", "Preface"),
        ("book/chapters/03-three.md", "# Three\n", "3"),
        ("book/appendices/a-ref.md", "# Appendix A: Reference {.unnumbered}\n", "A"),
        ("book/appendices/b-gloss.md", "# Glossary\n", "B"),
        ("book/appendices/z-colophon.md", "# Colophon {.unnumbered}\n", "Colophon"),
        ("book/appendices/y-about.md", "# About the author {-}\n\ntext\n", "About the author"),
        ("book/appendices/x-empty.md", "No heading at all.\n", "X"),
    ],
)
def test_locator_per_part(tmp_path, rel, body, label):
    assert gen_index.chapter_label(_part(tmp_path, rel, body)) == label


def test_colophon_locates_by_title_and_the_head_note_says_so(tmp_path):
    handle = (
        factories.BookFactory(slug="index-colophon")
        .with_chapter("01-one.md", "# One\n\nPillow resizes the plates.\n")
        .with_appendix("a-ref.md", "# Appendix A: Reference {.unnumbered}\n\nPillow again.\n")
        .with_appendix("z-colophon.md", "# Colophon {.unnumbered}\n\nSet with Pillow.\n")
        .with_index_terms([{"term": "Pillow", "match": ["pillow"]}])
        .build(tmp_path)
    )
    with handle.use():
        body = gen_index.generate().read_text(encoding="utf-8")
    assert "**Pillow** · 1, A, Colophon" in body
    assert ", Z" not in body
    assert "other back matter is named by its title" in body


def test_head_note_is_unchanged_when_no_part_locates_by_title(tmp_path):
    handle = (
        factories.BookFactory(slug="index-plain")
        .with_chapter("01-one.md", "# One\n\nPillow resizes the plates.\n")
        .with_index_terms([{"term": "Pillow", "match": ["pillow"]}])
        .build(tmp_path)
    )
    with handle.use():
        body = gen_index.generate().read_text(encoding="utf-8")
    assert "**Pillow** · 1" in body
    assert "by its title" not in body
