"""The site witness check compares source markdown to pandoc's smart output."""

import pytest

from press import verify_formats as vf
from tests import factories


def test_normalized_folds_smart_dashes_and_ellipsis():
    assert vf.normalized("x -- y") == vf.normalized("x – y")
    assert vf.normalized("x --- y") == vf.normalized("x — y")
    assert vf.normalized("wait...") == vf.normalized("wait…")


def _site_book(tmp_path, page_body):
    handle = (
        factories.BookFactory(slug="site-witness")
        .with_chapter(
            "01-one.md",
            "# One\n\nYou must manage the best way you can; -- but I must be kind...\n",
        )
        .build(tmp_path)
    )
    page = handle.root / "dist" / "site" / "1-one.html"
    page.parent.mkdir(parents=True)
    page.write_text(f"<html><body><p>{page_body}</p></body></html>", encoding="utf-8")
    return handle, page


def test_site_chapter_identity_accepts_a_smart_dashed_witness(tmp_path):
    handle, page = _site_book(
        tmp_path, "You must manage the best way you can; – but I must be kind…"
    )
    with handle.use():
        assert vf._verify_site_chapter_identity([page]) is None


def test_site_chapter_identity_still_refuses_a_missing_chapter(tmp_path):
    handle, page = _site_book(tmp_path, "Some other book entirely, nothing shared here.")
    with handle.use(), pytest.raises(SystemExit, match="is missing 01-one.md"):
        assert vf._verify_site_chapter_identity([page]) is None


def test_site_chapter_identity_accepts_a_drop_capped_opening_word(tmp_path):
    handle, page = _site_book(
        tmp_path,
        '<span class="drop-cap">Y</span><span class="opening-word-rest">ou</span> must '
        "manage the best way you can; – but I must be kind…",
    )
    with handle.use():
        assert vf._verify_site_chapter_identity([page]) is None


def test_witness_picker_skips_block_marker_lines(tmp_path):
    handle = (
        factories.BookFactory(slug="site-marker")
        .with_chapter(
            "01-one.md",
            "# One\n\nTerm\n\n: a deliberate reduction in level, stated in decibels and more\n\n"
            "A plain line that is long enough to be a witness here.\n",
        )
        .build(tmp_path)
    )
    with handle.use():
        witness = vf.chapter_witnesses()["01-one.md"]
    assert witness == "a plain line that is long enough to be a witness here."
