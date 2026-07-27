"""Art intake: a plate is taken as a surface-agnostic alpha master, never a
baked-white box.

The house retired baked-white plate JPEGs (#226): a plate must composite onto
any surface -- the white interior, a coloured cloth cover, a transparent web
panel -- so its master carries alpha. A baked-white delivery is segmented with
a luminance key at intake; a transparent delivery keeps its mask. These tests
are the known-bad for that producer: a fully-opaque, ink-on-white line-art
master must come out with a real transparent ground, not shipped opaque.
"""

from __future__ import annotations

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from press import art  # noqa: E402


def _baked_line_art(size: tuple[int, int] = (40, 40)) -> Image.Image:
    """Ink strokes on a solid white ground, fully opaque -- the baked master
    the intake must segment rather than ship as an opaque box."""

    img = Image.new("RGB", size, (255, 255, 255))
    px = img.load()
    assert px is not None
    for i in range(size[0]):
        px[i, size[1] // 2] = (0, 0, 0)  # a horizontal ink rule
        px[size[0] // 2, i] = (0, 0, 0)  # and a vertical one
    return img


def _accept_plate(tmp_path, monkeypatch, image, *, single_ink=True):
    from press import booklib

    monkeypatch.setattr(booklib, "root", lambda: tmp_path)
    monkeypatch.setattr(art, "_single_ink_plates", lambda: single_ink)
    src = tmp_path / "delivery.png"
    image.save(src)
    return art.accept(src, "plate:a-plate")


@pytest.mark.layer("unit")
def test_plate_accepts_as_a_png_master(tmp_path, monkeypatch):
    dst = _accept_plate(tmp_path, monkeypatch, _baked_line_art())
    assert dst == tmp_path / "assets" / "woodcuts" / "a-plate.png"
    assert dst.is_file()


@pytest.mark.layer("unit")
def test_baked_white_master_is_segmented_not_shipped_opaque(tmp_path, monkeypatch):
    # The known-bad: a fully opaque ink-on-white master must not ship opaque.
    # The intake keys the white ground out, so the master carries a genuine
    # transparent region (the paper) and a genuine opaque region (the ink).
    dst = _accept_plate(tmp_path, monkeypatch, _baked_line_art())
    master = Image.open(dst)
    assert master.mode == "RGBA"
    low, high = master.getchannel("A").getextrema()
    assert low == 0, "the white ground must be transparent, not baked opaque"
    assert high == 255, "the ink must stay fully opaque"


@pytest.mark.layer("unit")
def test_segmented_single_ink_master_reproduces_grayscale_on_white(tmp_path, monkeypatch):
    # Compositing the single-ink master back onto white reproduces the delivered
    # ink-on-white: dark where the ink was, white where the paper was.
    dst = _accept_plate(tmp_path, monkeypatch, _baked_line_art())
    master = Image.open(dst)
    flat = Image.new("RGB", master.size, (255, 255, 255))
    flat.paste(master, mask=master.getchannel("A"))
    assert flat.getpixel((0, 0)) == (255, 255, 255)  # paper stays white
    assert flat.getpixel((20, 20)) == (0, 0, 0)  # ink stays black


@pytest.mark.layer("unit")
def test_gradient_ground_is_refused_not_ghosted(tmp_path, monkeypatch):
    # The luminance key cannot tell a gradient ground from ink -- the dark end
    # survives as a ghost -- so intake refuses it rather than ship the smudge.
    grad = Image.new("L", (60, 60))
    for y in range(60):
        for x in range(60):
            grad.putpixel((x, y), int(245 - (y / 60) * 120))
    with pytest.raises(SystemExit):
        _accept_plate(tmp_path, monkeypatch, grad.convert("RGB"))


@pytest.mark.layer("unit")
def test_transparent_delivery_keeps_its_mask(tmp_path, monkeypatch):
    # A plate that arrives already on transparency is not re-keyed: its mask
    # (an author's deliberate cut-out) survives intake.
    art_on_alpha = Image.new("RGBA", (30, 30), (0, 0, 0, 0))
    px = art_on_alpha.load()
    assert px is not None
    for i in range(30):
        px[i, 15] = (0, 0, 0, 255)
    dst = _accept_plate(tmp_path, monkeypatch, art_on_alpha)
    master = Image.open(dst)
    assert master.getchannel("A").getpixel((0, 0)) == 0  # kept transparent
    assert master.getchannel("A").getpixel((0, 15)) == 255  # kept opaque


@pytest.mark.layer("unit")
def test_colour_plate_keeps_exact_colour_not_luminance_keyed(tmp_path, monkeypatch):
    # A colour interior (#214) is not line art: a luminance key would shift its
    # hues, so a colour plate defers to a matting model (not implemented) and
    # keeps exact colour -- an opaque flatten onto white, unchanged.
    img = Image.new("RGB", (20, 20), (255, 255, 255))
    px = img.load()
    assert px is not None
    for i in range(20):
        px[i, 10] = (180, 20, 20)  # a red ink stroke
    dst = _accept_plate(tmp_path, monkeypatch, img, single_ink=False)
    master = Image.open(dst).convert("RGBA")
    assert master.getpixel((5, 10)) == (180, 20, 20, 255)  # exact hue, opaque
    assert master.getpixel((0, 0)) == (255, 255, 255, 255)  # white ground kept
