"""The cover-wrap layout engine composes a wrap from trim, spine, margin,
inner offset, and board/jacket deltas per binding. These tests pin the
topologies: perfect-bound reproduces the v1 geometry exactly, a no-spine
binding drops the spine, and casewrap and dust jacket match IngramSpark's
published total-size formulas. The binding-resolution logic is pinned too.
"""

from __future__ import annotations

import pytest

from press import gen_coverwrap as cw
from press.provider_specs import ProviderSpec

BLEED = 0.125


@pytest.mark.layer("unit")
def test_perfect_bound_reproduces_v1_geometry():
    # trim 6x9, spine 0.115 (make-ready): the exact v1 wrap numbers.
    lay = cw.wrap_geometry(6.0, 9.0, 0.115, True, BLEED, 0.0, 0.0, 0.0, "paperback")
    assert lay.wrap_w == pytest.approx(2 * BLEED + 2 * 6.0 + 0.115)   # 12.365
    assert lay.wrap_h == pytest.approx(2 * BLEED + 9.0)               # 9.250
    assert lay.back_x == pytest.approx(BLEED)
    assert lay.front_x == pytest.approx(BLEED + 6.0 + 0.115)
    assert lay.front_art_w == pytest.approx(6.0 + BLEED)
    assert lay.cloth_field is True


@pytest.mark.layer("unit")
def test_no_spine_binding_drops_the_spine():
    lay = cw.wrap_geometry(6.0, 9.0, 0.0, False, BLEED, 0.0, 0.0, 0.0, "paperback")
    assert lay.wrap_w == pytest.approx(2 * BLEED + 2 * 6.0)   # no spine
    assert lay.front_x == pytest.approx(BLEED + 6.0)          # front butts back
    assert lay.has_spine is False


@pytest.mark.layer("unit")
def test_casewrap_matches_ingram_formula():
    # IngramSpark casewrap: wrap 0.625, hinge 0.5, board = trim-0.185 x trim+0.25.
    # BleedW = 0.625 + board + 0.5 + spine + 0.5 + board + 0.625.
    lay = cw.wrap_geometry(6.0, 9.0, 0.25, True, 0.625, 0.5, -0.185, 0.25, "casewrap")
    board_w = 6.0 - 0.185
    assert lay.wrap_w == pytest.approx(0.625 + board_w + 0.5 + 0.25 + 0.5 + board_w + 0.625)
    assert lay.wrap_h == pytest.approx(0.625 + (9.0 + 0.25) + 0.625)


@pytest.mark.layer("unit")
def test_jacket_matches_ingram_formula():
    # IngramSpark jacket: bleed 0.125, flap 3.25 + strip 0.25 (inner), cover = trim+0.4375.
    lay = cw.wrap_geometry(6.0, 9.0, 0.25, True, BLEED, 3.5, 0.4375, 0.25, "linen")
    cover_w = 6.0 + 0.4375
    assert lay.wrap_w == pytest.approx(
        0.125 + 3.25 + 0.25 + cover_w + 0.25 + cover_w + 0.25 + 3.25 + 0.125
    )
    assert lay.back_x == pytest.approx(BLEED + 3.5)          # bleed + flap + strip
    assert lay.front_art_w == pytest.approx(cover_w)         # art stays on panel
    assert lay.cloth_field is False                          # linen: no field


def _spec(bindings: dict) -> ProviderSpec:
    return ProviderSpec("v", {"spine": {"shape": "constant", "calipers": {}},
                              "cover": {"bleed": BLEED, "bindings": bindings}})


@pytest.mark.layer("unit")
def test_soft_binding_defaults_need_no_spec():
    spec = _spec({})
    assert cw._binding_geometry(spec, "perfect-bound") == (True, BLEED, 0.0, 0.0, 0.0)
    assert cw._binding_geometry(spec, "saddle-stitch") == (False, BLEED, 0.0, 0.0, 0.0)


@pytest.mark.layer("unit")
def test_hardcover_bindings_read_the_spec():
    spec = _spec({
        "casewrap": {"spine": True, "margin": 0.625, "hinge": 0.5,
                     "panel-width-delta": -0.185, "panel-height-delta": 0.25},
        "dust-jacket": {"spine": True, "margin": 0.125, "flap": 3.25, "strip": 0.25,
                        "panel-width-delta": 0.4375, "panel-height-delta": 0.25},
    })
    assert cw._binding_geometry(spec, "casewrap") == (True, 0.625, 0.5, -0.185, 0.25)
    # inner = flap + strip = 3.5
    assert cw._binding_geometry(spec, "dust-jacket") == (True, 0.125, 3.5, 0.4375, 0.25)


@pytest.mark.layer("unit")
def test_unsupported_binding_is_refused():
    # KDP has no dust jacket: a spec that does not define it must refuse.
    with pytest.raises(SystemExit, match="does not define the 'dust-jacket'"):
        cw._binding_geometry(_spec({}), "dust-jacket")


@pytest.mark.layer("unit")
def test_scanline_rejects_a_near_uniform_barcode_smear():
    # A near-uniform dark smear where the barcode belongs -- a white card
    # with a solid dark block instead of resolved bars -- is unscannable:
    # scanline must reject it as not structurally readable. This is the
    # known-bad fixture for the transitions floor (verify_coverwrap ~L92);
    # regressing that guard to 'transitions < 0' turns this test red.
    from PIL import Image, ImageDraw

    from press import verify_coverwrap

    # The v1 perfect-bound geometry, so the passed args match a real wrap.
    wrap_w = 12.365
    image_w = 1855
    image_h = 1388
    margin = 0.125
    back_right = 6.125  # back panel right edge: bleed(0.125) + trim(6.0)
    isbn = "9781234567897"

    # Replicate scanline's crop/anchor math to place the smear exactly on
    # the sampled bar row, within the symbol window, and clear of the quiet
    # zones -- so the ONLY thing that trips is the readability floor.
    dpi = image_w / wrap_w
    anchor_y = margin + 0.5
    x0 = max(0, int((back_right - 0.5 - 2.4) * dpi))
    row_y = image_h - int((anchor_y + 0.32 + 0.45) * dpi)  # image-space bar row
    module = 0.0130
    symbol_right = int((2.4 - 0.15) * dpi)  # region-local
    symbol_left = symbol_right - int(95 * module * dpi)

    image = Image.new("L", (image_w, image_h), 255)  # white card everywhere
    draw = ImageDraw.Draw(image)
    # A solid dark block spanning the symbol window (region-local
    # symbol_left..symbol_right), a band tall enough to cover the sampled
    # row. It leaves the quiet zones white, so no transitions AND no quiet
    # zone ink: only the transitions floor can fire.
    draw.rectangle(
        (x0 + symbol_left, row_y - 12, x0 + symbol_right, row_y + 12),
        fill=0,
    )

    with pytest.raises(SystemExit, match="not structurally readable"):
        verify_coverwrap.scanline(image, back_right, margin, wrap_w, isbn)


@pytest.mark.layer("unit")
def test_check_print_safe_accepts_a_clean_wrap(tmp_path):
    # A wrap with no raster images carries no transparency and nothing over
    # 600 PPI, so the print-safety check passes. (The rejection paths are
    # proven end to end by the integration coverwrap build.)
    from pypdf import PdfWriter

    from press import verify_coverwrap

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    wrap = tmp_path / "wrap.pdf"
    with open(wrap, "wb") as handle:
        writer.write(handle)
    assert verify_coverwrap.check_print_safe(wrap) is None   # clean: no raise


@pytest.mark.layer("unit")
def test_check_print_safe_rejects_a_transparent_image(tmp_path):
    # A cover that embeds a transparent image -- an image XObject carrying an
    # /SMask soft mask -- must be refused before it ships: a print-on-demand
    # preflight (KDP, IngramSpark) flags transparency on the cover. The clean
    # path above proves the check passes valid wraps; this proves the guard has
    # teeth, so regressing the /SMask arm cannot ship a transparent PNG cover
    # under a green suite. (The >600 PPI arm is proven separately in
    # test_adapters_routing.py.)
    from pypdf import PdfWriter
    from pypdf.generic import (
        DecodedStreamObject,
        DictionaryObject,
        NameObject,
        NumberObject,
    )

    from press import verify_coverwrap

    def _image_xobject() -> DecodedStreamObject:
        stream = DecodedStreamObject()
        stream.set_data(b"\x00" * 4)
        stream[NameObject("/Type")] = NameObject("/XObject")
        stream[NameObject("/Subtype")] = NameObject("/Image")
        stream[NameObject("/Width")] = NumberObject(2)
        stream[NameObject("/Height")] = NumberObject(2)
        stream[NameObject("/ColorSpace")] = NameObject("/DeviceGray")
        stream[NameObject("/BitsPerComponent")] = NumberObject(8)
        return stream

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)

    smask_ref = writer._add_object(_image_xobject())
    image = _image_xobject()
    image[NameObject("/SMask")] = smask_ref        # the soft mask == transparency
    image_ref = writer._add_object(image)

    resources = DictionaryObject()
    xobjects = DictionaryObject()
    xobjects[NameObject("/Im0")] = image_ref
    resources[NameObject("/XObject")] = xobjects
    writer.pages[0][NameObject("/Resources")] = resources

    wrap = tmp_path / "wrap.pdf"
    with open(wrap, "wb") as handle:
        writer.write(handle)

    with pytest.raises(SystemExit, match="transparency"):
        verify_coverwrap.check_print_safe(wrap)
