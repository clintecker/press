"""print_safe prepares flattened, resolution-capped copies of a book's
interior rasters so a print-on-demand vendor sees no transparency and no
image over 600 PPI. These tests pin the two transformations (flatten,
downsample), the grayscale-preserving path, and the mirror-and-rebuild
contract of ``prepare`` -- all on synthetic images, so nothing depends on a
real book or a renderer.
"""

from __future__ import annotations

import pytest
from PIL import Image

from press import print_safe


def _save(path, size, mode, color):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new(mode, size, color).save(path)


@pytest.mark.layer("unit")
def test_sanitize_flattens_transparency_onto_white(tmp_path):
    src, dst = tmp_path / "logo.png", tmp_path / "out.png"
    # A fully transparent pixel must composite to white, not stay clear.
    Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(src)
    print_safe.sanitize(src, dst, 1000)
    out = Image.open(dst)
    assert out.mode == "RGB"
    assert out.getpixel((0, 0)) == (255, 255, 255)


@pytest.mark.layer("unit")
def test_sanitize_downsamples_over_the_cap(tmp_path):
    src, dst = tmp_path / "big.jpg", tmp_path / "out.jpg"
    _save(src, (4000, 2000), "RGB", (10, 20, 30))
    print_safe.sanitize(src, dst, 1000)
    assert max(Image.open(dst).size) == 1000


@pytest.mark.layer("unit")
def test_sanitize_never_upscales(tmp_path):
    src, dst = tmp_path / "small.jpg", tmp_path / "out.jpg"
    _save(src, (300, 200), "RGB", (0, 0, 0))
    print_safe.sanitize(src, dst, 1000)
    assert Image.open(dst).size == (300, 200)


@pytest.mark.layer("unit")
def test_sanitize_preserves_grayscale(tmp_path):
    # A single-ink plate stays grayscale, not promoted to RGB.
    src, dst = tmp_path / "plate.jpg", tmp_path / "out.jpg"
    _save(src, (2528, 1696), "L", 128)
    print_safe.sanitize(src, dst, 1900)
    out = Image.open(dst)
    assert out.mode == "L"
    assert max(out.size) == 1900


@pytest.mark.layer("unit")
def test_prepare_mirrors_layout_with_per_image_caps(tmp_path):
    root = tmp_path
    # The logo is placed small, so it takes the tighter 1000px cap; a figure
    # of the same width keeps its size because the figure cap is higher.
    _save(root / "assets" / "press-logo.png", (1500, 1500), "RGBA", (0, 0, 0, 255))
    _save(root / "assets" / "author.jpg", (1500, 1000), "RGB", (5, 5, 5))
    _save(root / "assets" / "woodcuts" / "w.jpg", (2528, 1696), "L", 128)

    out = print_safe.prepare(root)

    assert out == root / "build" / "print-assets"
    logo = Image.open(out / "assets" / "press-logo.png")
    assert logo.mode == "RGB" and max(logo.size) <= 1000
    assert Image.open(out / "assets" / "author.jpg").size == (1500, 1000)
    assert max(Image.open(out / "assets" / "woodcuts" / "w.jpg").size) <= 1900


@pytest.mark.layer("unit")
def test_prepare_rebuilds_from_scratch(tmp_path):
    root = tmp_path
    _save(root / "assets" / "cover.jpg", (100, 100), "RGB", (0, 0, 0))
    print_safe.prepare(root)
    stale = root / "build" / "print-assets" / "stale.jpg"
    stale.write_bytes(b"x")
    print_safe.prepare(root)
    assert not stale.exists()


@pytest.mark.layer("unit")
def test_prepare_returns_none_without_rasters(tmp_path):
    (tmp_path / "assets").mkdir()
    assert print_safe.prepare(tmp_path) is None
