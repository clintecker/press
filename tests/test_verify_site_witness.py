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


def _definition_list_book(tmp_path, slug):
    return (
        factories.BookFactory(slug=slug)
        .with_chapter(
            "01-one.md",
            "# One\n\nTerm\n\n: a deliberate reduction in level, stated in decibels and more\n\n"
            "A plain line that is long enough to be a witness here.\n",
        )
        .build(tmp_path)
    )


def test_manuscript_witness_skips_block_marker_lines(tmp_path):
    handle = _definition_list_book(tmp_path, "manuscript-marker")
    with handle.use():
        witness = vf._manuscript_witness()
    assert witness == "a plain line that is long enough to be a witness here."


_CROSSREF_CHAPTER = (
    "# One\n\n"
    "The first eight files in @fig:dist-after-all are the edition the reader holds.\n\n"
    "A plain line long enough to stand as the witness.\n"
)


def _crossref_book(tmp_path, slug):
    return (
        factories.BookFactory(slug=slug)
        .with_chapter("01-one.md", _CROSSREF_CHAPTER)
        .build(tmp_path)
    )


def test_chapter_witnesses_skip_crossref_lines(tmp_path):
    handle = _crossref_book(tmp_path, "chapter-crossref")
    with handle.use():
        witness = vf.chapter_witnesses()["01-one.md"]
    assert witness == "a plain line long enough to stand as the witness."


def test_manuscript_witness_skips_crossref_lines(tmp_path):
    handle = _crossref_book(tmp_path, "manuscript-crossref")
    with handle.use():
        witness = vf._manuscript_witness()
    assert witness == "a plain line long enough to stand as the witness."


@pytest.mark.parametrize(
    "line",
    [
        "the first eight files in @fig:dist-after-all are the edition the reader holds",
        "as the table in @tbl:sizes shows, the plates are small enough to ship",
        "the reasoning is laid out at length in @sec:shape and need not repeat",
        "substituting into @eq:spine gives the width in points for the wrap",
        "as the standard committee argued at length [@iso-9001-2015, p. 12]",
        ": a deliberate reduction in level, stated in decibels and more",
        "a line that is too short to count",
    ],
)
def test_witness_candidate_refuses_unrenderable_lines(line):
    assert vf._witness_candidate(line) is False


@pytest.mark.parametrize(
    "line",
    [
        "a plain line that is long enough to be a witness here.",
        "write to editor@example.com: the address is plain text, not a reference",
    ],
)
def test_witness_candidate_accepts_plain_prose(line):
    assert vf._witness_candidate(line) is True
