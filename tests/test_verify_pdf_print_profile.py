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


def _write(tmp_path: Path, index: int, left: int, right: int,
           *, fill: tuple[int, int, int] = (10, 10, 10)) -> Path:
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
        _write(tmp_path, i, 40, 200, fill=(v, v, v))
        for i, v in enumerate((0, 30, 90), start=1)
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
