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
def test_sanitize_composites_onto_a_given_background(tmp_path):
    src, dst = tmp_path / "logo.png", tmp_path / "out.png"
    Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(src)
    print_safe.sanitize(src, dst, 1000, background=(201, 191, 191))
    out = Image.open(dst)
    # The transparent logo takes the field colour, so it is invisible against
    # the printed field and carries no soft mask.
    assert out.mode == "RGB" and out.getpixel((0, 0)) == (201, 191, 191)


@pytest.mark.layer("unit")
def test_prepare_cover_makes_opaque_capped_assets(tmp_path):
    (tmp_path / "assets").mkdir()
    Image.new("RGBA", (2000, 2000), (0, 0, 0, 0)).save(tmp_path / "assets" / "press-logo.png")
    Image.new("RGB", (5000, 7000), (10, 20, 30)).save(tmp_path / "assets" / "cover.jpg")

    made = print_safe.prepare_cover(
        tmp_path, logo_background=(201, 191, 191), cover_max_edge=3000, logo_max_edge=640
    )
    logo, cover = Image.open(made["logo"]), Image.open(made["cover"])
    # Logo: opaque, on the field colour, capped to its small cover placement.
    # (Saved as JPEG, so the flat field decodes within a unit or two.)
    assert logo.mode == "RGB" and max(logo.size) <= 640
    assert all(abs(got - want) <= 3 for got, want in zip(logo.getpixel((0, 0)), (201, 191, 191)))
    # Cover: opaque, downsampled under the wrap cap.
    assert cover.mode == "RGB" and max(cover.size) <= 3000


@pytest.mark.layer("unit")
def test_prepare_cover_is_empty_without_assets(tmp_path):
    (tmp_path / "assets").mkdir()
    assert print_safe.prepare_cover(tmp_path, (255, 255, 255), 3000, 640) == {}


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


@pytest.mark.layer("unit")
def test_one_alpha_plate_master_composites_per_surface(tmp_path):
    # #226: one alpha plate master serves every surface. The interior print
    # gets it flattened onto white; a coloured cover field gets it flattened
    # onto that field; the web edition keeps the transparent master untouched.
    master = tmp_path / "plate.png"
    ink, ground = (0, 0, 0, 255), (0, 0, 0, 0)
    img = Image.new("RGBA", (4, 4), ground)
    img.putpixel((0, 0), ink)
    img.save(master)

    on_white, on_cloth = tmp_path / "white.png", tmp_path / "cloth.png"
    print_safe.sanitize(master, on_white, 1000)
    print_safe.sanitize(master, on_cloth, 1000, background=(150, 40, 40))

    white, cloth = Image.open(on_white), Image.open(on_cloth)
    assert white.mode == "RGB" and cloth.mode == "RGB"
    # Ink is opaque on every surface; the ground takes each surface's colour.
    assert white.getpixel((0, 0)) == (0, 0, 0) and white.getpixel((3, 3)) == (255, 255, 255)
    assert cloth.getpixel((0, 0)) == (0, 0, 0) and cloth.getpixel((3, 3)) == (150, 40, 40)
    # The master on disk is untouched, so the web edition still serves alpha.
    assert Image.open(master).getchannel("A").getextrema() == (0, 255)


def _image_stream(mode_data: bytes, size, colorspace: str):
    from pypdf.generic import DecodedStreamObject, NameObject, NumberObject

    stream = DecodedStreamObject()
    stream.set_data(mode_data)
    stream[NameObject("/Type")] = NameObject("/XObject")
    stream[NameObject("/Subtype")] = NameObject("/Image")
    stream[NameObject("/Width")] = NumberObject(size[0])
    stream[NameObject("/Height")] = NumberObject(size[1])
    stream[NameObject("/ColorSpace")] = NameObject(colorspace)
    stream[NameObject("/BitsPerComponent")] = NumberObject(8)
    return stream


def _wrap_with(image_path, wrap):
    """A one-page PDF embedding one image the way lualatex embeds a raster
    in the cover wrap: the colour samples as an image XObject and, when the
    image carries alpha, that alpha as its /SMask soft mask -- the
    transparency a print preflight flags."""

    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject

    with Image.open(image_path) as image:
        image.load()
    writer = PdfWriter()
    page = writer.add_blank_page(width=72, height=72)
    xobject = _image_stream(image.convert("RGB").tobytes(), image.size, "/DeviceRGB")
    if "A" in image.getbands():
        alpha = _image_stream(image.getchannel("A").tobytes(), image.size, "/DeviceGray")
        xobject[NameObject("/SMask")] = writer._add_object(alpha)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/XObject"): DictionaryObject(
                {NameObject("/Im0"): writer._add_object(xobject)}
            )
        }
    )
    with open(wrap, "wb") as handle:
        writer.write(handle)
    return wrap


@pytest.mark.layer("unit")
def test_check_print_safe_rejects_a_logo_print_safe_left_transparent(tmp_path, monkeypatch):
    # The no-blind-verifier fixture for print_safe: regress the flatten step
    # (sanitize becomes a plain copy, the bug this module exists to prevent),
    # embed the logo prepare_cover then emits, and the coverwrap verifier must
    # refuse the wrap. The real producer's output, embedded the same way,
    # passes, so the refusal is about the transparency and nothing else.
    import shutil

    from press import adapters, verify_coverwrap
    from press.adapters import fakes

    # Resolution is a separate arm needing pdfimages; keep this fixture about
    # transparency alone, the same on every machine.
    monkeypatch.setattr(adapters, "environment", fakes.FakeEnvironment(present_tools=[]))
    _save(tmp_path / "assets" / "press-logo.png", (40, 40), "RGBA", (0, 0, 0, 0))

    made = print_safe.prepare_cover(tmp_path, (201, 191, 191), 3000, 640)
    verify_coverwrap.check_print_safe(_wrap_with(made["logo"], tmp_path / "good.pdf"))

    def copy_unflattened(src, dst, *_args, **_kwargs):
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

    monkeypatch.setattr(print_safe, "sanitize", copy_unflattened)
    made = print_safe.prepare_cover(tmp_path, (201, 191, 191), 3000, 640)
    with pytest.raises(SystemExit, match="with transparency"):
        verify_coverwrap.check_print_safe(_wrap_with(made["logo"], tmp_path / "bad.pdf"))
