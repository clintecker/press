"""Known-bad fixtures for the print-profile interior checks.

The print profile is what ships to KDP/IngramSpark, so its two interior
guards -- mirrored binding margins and black-ink-only -- must redden when the
interior is wrong. Before these fixtures both checkers could be broken (the
gutter comparison inverted, the colored-ink threshold slackened) while the
whole suite stayed green and a bad print interior shipped. Each guard here has
a passing baseline that catches an inverted/slackened comparison and a
known-bad fixture that catches a checker that never fires.

Both verify_mirrored_margins and verify_black_ink operate directly on a list of
rendered page PNGs, so the fixtures are synthetic pages built pixel by pixel --
no PDF, no renderer, no monkeypatching.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from press import verify_pdf

# The mirrored-margin check ignores the first 20% of pages (front matter), so
# ten body pages leave a comfortable spread of recto/verso witnesses.
_PAGE_COUNT = 10
_W, _H = 240, 360


def _write(
    tmp_path: Path, index: int, left: int, right: int, *, fill: tuple[int, int, int] = (10, 10, 10)
) -> Path:
    """A page whose only ink is one filled block between x=left and x=right."""

    img = Image.new("RGB", (_W, _H), (255, 255, 255))
    ImageDraw.Draw(img).rectangle([left, 40, right, _H - 40], fill=fill)
    dest = tmp_path / f"page-{index:02d}.png"
    img.save(dest)
    return dest


def _mirrored_pages(tmp_path: Path, *, recto_left: int, verso_left: int) -> list[Path]:
    """Ten pages: odd (recto) blocks start at recto_left, even (verso) at
    verso_left. A real print interior pushes the recto's left edge inward
    (the gutter) so recto_left > verso_left."""

    pages: list[Path] = []
    for index in range(1, _PAGE_COUNT + 1):
        left = recto_left if index % 2 == 1 else verso_left
        pages.append(_write(tmp_path, index, left, left + 100))
    return pages


# --- verify_mirrored_margins -------------------------------------------------


@pytest.mark.layer("unit")
def test_a_correctly_mirrored_interior_passes(tmp_path):
    # Recto's inner (left) margin is wider than the verso's: the gutter swaps
    # sides as a bound book demands. Passing here is what catches an inverted
    # comparison -- flip line ~172 and this baseline starts raising.
    pages = _mirrored_pages(tmp_path, recto_left=70, verso_left=20)
    assert verify_pdf.verify_mirrored_margins(pages) is None


@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_missing_gutter_is_rejected(tmp_path):
    # Both recto and verso start at the same left edge: no binding offset at
    # all. The interior would bind into the gutter.
    pages = _mirrored_pages(tmp_path, recto_left=40, verso_left=40)
    with pytest.raises(SystemExit, match="gutter is missing"):
        verify_pdf.verify_mirrored_margins(pages)


@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_gutter_on_the_wrong_side_is_rejected(tmp_path):
    # The offset exists but swings the wrong way: the verso carries the wide
    # inner margin, so every leaf binds backwards.
    pages = _mirrored_pages(tmp_path, recto_left=20, verso_left=70)
    with pytest.raises(SystemExit, match="gutter is missing"):
        verify_pdf.verify_mirrored_margins(pages)


# --- verify_black_ink --------------------------------------------------------


@pytest.mark.layer("unit")
def test_a_black_interior_passes(tmp_path):
    # Grayscale ink only (r == g == b everywhere): the print interior is clean.
    pages = [
        _write(tmp_path, i, 40, 200, fill=(v, v, v)) for i, v in enumerate((0, 30, 90), start=1)
    ]
    assert verify_pdf.verify_black_ink(pages) is None


@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_colored_region_is_rejected(tmp_path):
    # One page carries a saturated colored block -- a color cover plate left in
    # the print interior. Slacken the threshold at line ~192 and this fixture
    # stops firing.
    clean = _write(tmp_path, 1, 40, 200, fill=(20, 20, 20))
    colored = Image.new("RGB", (_W, _H), (255, 255, 255))
    ImageDraw.Draw(colored).rectangle([40, 40, 200, _H - 40], fill=(200, 20, 20))
    tinted = tmp_path / "page-02.png"
    colored.save(tinted)
    with pytest.raises(SystemExit, match="colored ink"):
        verify_pdf.verify_black_ink([clean, tinted])


@pytest.mark.layer("unit")
def test_a_colored_region_passes_under_a_color_profile(tmp_path):
    # The very block a single-ink interior refuses is allowed once the design
    # profile declares ink: color -- a colour interior prints in colour by
    # design (#212). The single-ink prohibition is unchanged (the negative
    # above still fires); this only lifts it for a colour profile.
    clean = _write(tmp_path, 1, 40, 200, fill=(20, 20, 20))
    colored = Image.new("RGB", (_W, _H), (255, 255, 255))
    ImageDraw.Draw(colored).rectangle([40, 40, 200, _H - 40], fill=(200, 20, 20))
    tinted = tmp_path / "page-02.png"
    colored.save(tinted)
    assert verify_pdf.verify_black_ink([clean, tinted], "color") is None


# --- verify_text_block -------------------------------------------------------

# Twelve pages at the render geometry of a 6 x 9 trim at 120 dpi; the first
# 20 percent are front matter and are not judged. The geometries are the house
# profile's: reading right margin 0.68in (measure x=638); print recto 0.58in
# (x=650), verso 0.88in (x=614).
_TB_W, _TB_H = 720, 1080
_TB_PAGES = 12
_READING = (6.0, {0: 0.68})
_PRINT = (6.0, {1: 0.58, 0: 0.88})


def _measure_page(
    tmp_path: Path, index: int, right: int, *, folio_right: int | None = None
) -> Path:
    """A body page whose lines run from x=90 to bbox edge x=right (PIL bbox
    edges are exclusive, so the last inked column is right - 1); a folio may
    sit in the bottom band at folio_right."""

    img = Image.new("RGB", (_TB_W, _TB_H), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    for top in range(120, _TB_H - 120, 24):
        draw.rectangle([90, top, right - 1, top + 10], fill=(10, 10, 10))
    if folio_right is not None:
        draw.rectangle([folio_right - 20, _TB_H - 50, folio_right, _TB_H - 40], fill=(10, 10, 10))
    dest = tmp_path / f"tb-{index:02d}.png"
    img.save(dest)
    return dest


def _print_page(tmp_path: Path, index: int, overrun: int = 0) -> Path:
    return _measure_page(tmp_path, index, (650 if index % 2 else 614) + overrun)


@pytest.mark.invariant("INV-pdf-text-block")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_page_overrunning_the_measure_is_rejected(tmp_path):
    # Every page ends its lines at its side's measure; page 9 sets a code line
    # that runs 30 px past it, the overflow a too-wide table cell produces.
    pages = [_print_page(tmp_path, i, 30 if i == 9 else 0) for i in range(1, _TB_PAGES + 1)]
    with pytest.raises(SystemExit, match=r"print profile: page 9 runs 30 px past the text block"):
        verify_pdf.verify_text_block(pages, "print", geometry=_PRINT)


@pytest.mark.invariant("INV-pdf-text-block")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_pages_within_the_measure_pass(tmp_path):
    # Every page ends at the measure, page 4 protrudes by the 6 px slack; a
    # folio in the bottom band sits further right (outside the text block)
    # and must not count against the page.
    pages = [
        _measure_page(tmp_path, i, 644 if i == 4 else 638, folio_right=700 if i == 7 else None)
        for i in range(1, _TB_PAGES + 1)
    ]
    assert verify_pdf.verify_text_block(pages, "reading", geometry=_READING) is None


@pytest.mark.invariant("INV-pdf-text-block")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_ragged_pages_pass_against_the_geometry(tmp_path):
    # A verse book: most pages are ragged poems ending far short of the
    # measure, one justified page ends exactly at it. A sampled median would
    # settle on the poems and refuse the prose page; the geometry does not.
    pages = [
        _measure_page(tmp_path, i, 638 if i == 9 else 400 + 7 * i) for i in range(1, _TB_PAGES + 1)
    ]
    assert verify_pdf.verify_text_block(pages, "reading", geometry=_READING) is None
    assert (
        max(o for _p, o in verify_pdf.text_block_overruns(pages, "reading", geometry=_READING)) == 0
    )


@pytest.mark.invariant("INV-pdf-text-block")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_the_measure_is_judged_per_parity_in_print(tmp_path):
    # The gutter shifts a recto's block right of a verso's: a recto ending at
    # 650 is on its measure, a verso ending there is 36 px into its margin.
    pages = [_print_page(tmp_path, i) for i in range(1, _TB_PAGES + 1)]
    assert verify_pdf.text_block_right(pages, "print", _PRINT) == {1: 650, 0: 614}
    assert verify_pdf.verify_text_block(pages, "print", geometry=_PRINT) is None
    pages[7] = _measure_page(tmp_path, 8, 650)
    with pytest.raises(SystemExit, match=r"print profile: page 8 runs 36 px past"):
        verify_pdf.verify_text_block(pages, "print", geometry=_PRINT)


@pytest.mark.invariant("INV-pdf-text-block")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_the_reading_profile_judges_one_measure(tmp_path):
    # The reading PDF is one-sided, so one right margin serves every page; a
    # recto running past it is caught even though it is odd.
    pages = [_measure_page(tmp_path, i, 653 if i == 5 else 638) for i in range(1, _TB_PAGES + 1)]
    assert verify_pdf.text_block_right(pages, "reading", _READING) == {0: 638}
    with pytest.raises(SystemExit, match=r"reading profile: page 5 runs 15 px past the text block"):
        verify_pdf.verify_text_block(pages, "reading", geometry=_READING)


@pytest.mark.invariant("INV-pdf-text-block")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_short_book_is_judged_without_a_sample(tmp_path):
    # Three pages: cover, title, one body page. There is no median to take
    # and none is needed; the one body page is still judged and refused.
    pages = [_measure_page(tmp_path, i, 660 if i == 3 else 638) for i in range(1, 4)]
    assert verify_pdf.text_block_overruns(pages, "reading", geometry=_READING) == [(3, 22)]
    with pytest.raises(SystemExit, match=r"page 3 runs 22 px past"):
        verify_pdf.verify_text_block(pages, "reading", geometry=_READING)


@pytest.mark.invariant("INV-pdf-text-block")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_the_geometry_comes_from_the_profile_and_print_header():
    # The house profile's outer margin for the reading PDF; the print
    # header's inner/outer, swapped by parity, for the print interior.
    house = verify_pdf.profiles.load("house-6x9")
    assert verify_pdf.text_block_geometry("reading", house) == (6.0, {0: 0.68})
    assert verify_pdf.text_block_geometry("print", house) == (6.0, {1: 0.58, 0: 0.88})
    novella = verify_pdf.profiles.load("novella-5x8")
    assert verify_pdf.text_block_geometry("reading", novella) == (5.0, {0: 0.55})


@pytest.mark.invariant("INV-pdf-text-block")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_short_books_contents_is_skipped_by_its_page_labels(tmp_path):
    # A short book's Contents can sit past the 20 percent guess (Alice's is
    # page 5 of 23) with right-aligned folios inking past the measure. main
    # hands the first arabic-labelled page as the start, so the Contents is
    # front matter; without it the page is refused.
    from pypdf import PdfWriter

    pages = [_measure_page(tmp_path, i, 718 if i == 5 else 638) for i in range(1, _TB_PAGES + 1)]
    with pytest.raises(SystemExit, match=r"page 5 runs 80 px past"):
        verify_pdf.verify_text_block(pages, "reading", geometry=_READING)
    writer = PdfWriter()
    for _ in range(_TB_PAGES):
        writer.add_blank_page(width=432, height=648)
    writer.set_page_label(0, 5, style="/r")
    writer.set_page_label(6, _TB_PAGES - 1, style="/D")
    pdf = tmp_path / "labelled.pdf"
    writer.write(pdf)
    assert verify_pdf.first_body_index(pdf) == 6
    start = verify_pdf.first_body_index(pdf)
    assert verify_pdf.verify_text_block(pages, "reading", start, _READING) is None
    unlabelled = tmp_path / "plain.pdf"
    bare = PdfWriter()
    bare.add_blank_page(width=432, height=648)
    bare.write(unlabelled)
    assert verify_pdf.first_body_index(unlabelled) is None


@pytest.mark.invariant("INV-pdf-text-block")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_profile_whose_margin_eats_the_page_is_refused():
    # A margin as wide as the trim leaves no text block to judge against;
    # the check refuses the geometry rather than measuring against nonsense.
    house = verify_pdf.profiles.load("house-6x9")
    data = {**house.data, "interior": {**house.data["interior"]}}
    data["interior"]["margins"] = {**house.margins, "outer": 6.0}
    broken = verify_pdf.profiles.Profile("broken", data)
    with pytest.raises(SystemExit, match="leave no text block"):
        verify_pdf.text_block_geometry("reading", broken)
