"""The chunked reader's index is a real start-reading page, not an empty
shell (#160): its <main id="content"> (the skip-link target) carries an
orienting line, one primary "Start reading" action pointing at the first
part by the same manifest the pager uses, and the chapter contents. A
chapter page keeps its own body in main and gets no start-reading block.
"""

from __future__ import annotations

import re
import shutil

import pytest

pytestmark = [
    pytest.mark.layer("integration"),
    pytest.mark.skipif(shutil.which("pandoc") is None,
                       reason="requires capability: pandoc"),
]


def _main(html: str) -> str:
    m = re.search(r'<main id="content">(.*?)</main>', html, re.S)
    return m.group(1) if m else ""


def test_reader_index_starts_the_reader(scaffolded_book):
    chapters = scaffolded_book / "book" / "chapters"
    (chapters / "01-first.md").write_text(
        "# First part {.unnumbered}\n\nProse of the first part.\n", encoding="utf-8")
    (chapters / "02-second.md").write_text(
        "# Second part {.unnumbered}\n\nProse of the second part.\n", encoding="utf-8")

    from press import build
    build.build_target("site")
    site = scaffolded_book / "dist" / "site"

    index = (site / "index.html").read_text(encoding="utf-8")
    index_main = _main(index)
    # The skip target has meaningful content, not an empty region.
    assert index_main.strip(), "reader index <main> is empty (dead skip target)"
    # One primary start action, pointing at the first part via rel=next.
    starts = re.findall(r'class="start-reading" href="([^"]+)" rel="next"', index_main)
    assert len(starts) == 1, f"expected one start-reading action, got {starts}"
    assert (site / starts[0]).is_file(), "start-reading target is not a real page"
    # The chapter contents live inside the reading region, and there is one H1.
    assert 'role="doc-toc"' in index_main
    assert index.count("<h1") == 1

    # A chapter page keeps its own body and gets no start-reading block.
    chapter = next(p for p in site.glob("*.html")
                   if p.name != "index.html" and "start-reading" not in _main(
                       p.read_text(encoding="utf-8")))
    assert chapter, "no chapter page without a start-reading block"


def test_a_single_part_book_still_starts_cleanly(scaffolded_book):
    # Only the scaffolded preface: the index still orients and offers a start.
    from press import build
    build.build_target("site")
    index_main = _main((scaffolded_book / "dist" / "site" / "index.html")
                       .read_text(encoding="utf-8"))
    assert "reader-lede" in index_main
    assert 'class="start-reading"' in index_main
