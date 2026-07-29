"""verify_pdf.verify_plate_links -- the hypcap scar, with teeth.

The List of Plates links must resolve to pages that actually carry an image;
hyperref anchors a float at its caption, not its raster, so without hypcap a
plate link overshoots onto the following, imageless page. The checker guards
that (verify_pdf.py, lines 51-75), but its only production caller builds a
factory book with no plates, so ``lof_index`` is ``None`` and it returns before
touching the substantive logic. A checker is only real once a known-bad
rejects it: these cases synthesize a PDF whose "List of plates" page links at
an imageless page (rejected) and one whose link lands on an illustrated page
(passes), driving the exact link/destination/XObject inspection the checker
performs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
)

from press import verify_pdf


def _image_xobject(writer: PdfWriter) -> DictionaryObject:
    """A minimal /XObject image dict, the raster a real plate page holds."""

    image = DecodedStreamObject()
    image.set_data(b"\x00" * 16)
    image[NameObject("/Type")] = NameObject("/XObject")
    image[NameObject("/Subtype")] = NameObject("/Image")
    image[NameObject("/Width")] = NumberObject(4)
    image[NameObject("/Height")] = NumberObject(4)
    image[NameObject("/ColorSpace")] = NameObject("/DeviceGray")
    image[NameObject("/BitsPerComponent")] = NumberObject(8)
    xobjects = DictionaryObject()
    xobjects[NameObject("/Im0")] = writer._add_object(image)
    return xobjects


def _plate_pdf(path: Path, *, target_has_image: bool, label: str = "List of plates") -> Path:
    """A two-page PDF: an illustration-list page (named *label*) whose link
    points at the second page, which carries an image only when
    ``target_has_image`` is set."""

    writer = PdfWriter()
    lof = writer.add_blank_page(width=200, height=200)
    target = writer.add_blank_page(width=200, height=200)

    # The lof page needs real text so extract_text() finds the list label.
    contents = DecodedStreamObject()
    contents.set_data(b"BT /F1 12 Tf 20 150 Td (" + label.encode("latin-1") + b") Tj ET")
    lof[NameObject("/Contents")] = writer._add_object(contents)
    font = DictionaryObject()
    font[NameObject("/Type")] = NameObject("/Font")
    font[NameObject("/Subtype")] = NameObject("/Type1")
    font[NameObject("/BaseFont")] = NameObject("/Helvetica")
    fonts = DictionaryObject()
    fonts[NameObject("/F1")] = writer._add_object(font)
    lof_resources = DictionaryObject()
    lof_resources[NameObject("/Font")] = fonts
    lof[NameObject("/Resources")] = lof_resources

    target_resources = DictionaryObject()
    if target_has_image:
        target_resources[NameObject("/XObject")] = _image_xobject(writer)
    target[NameObject("/Resources")] = target_resources

    # A Link annotation whose explicit /Dest array leads with the target page,
    # exactly the shape verify_plate_links resolves.
    link = DictionaryObject()
    link[NameObject("/Type")] = NameObject("/Annot")
    link[NameObject("/Subtype")] = NameObject("/Link")
    link[NameObject("/Rect")] = ArrayObject([NumberObject(v) for v in (20, 140, 180, 160)])
    link[NameObject("/Dest")] = ArrayObject([target.indirect_reference, NameObject("/Fit")])
    lof[NameObject("/Annots")] = ArrayObject([writer._add_object(link)])

    with path.open("wb") as handle:
        writer.write(handle)
    return path


@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_plate_link_to_an_imageless_page_is_rejected(tmp_path):
    pdf = _plate_pdf(tmp_path / "imageless.pdf", target_has_image=False)
    # The link genuinely resolves to a real page; that page just holds no image.
    assert "List of plates" in (PdfReader(str(pdf)).pages[0].extract_text() or "")
    with pytest.raises(SystemExit, match="List of plates links point at imageless pages"):
        verify_pdf.verify_plate_links(pdf)


@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_list_of_figures_link_to_an_imageless_page_is_rejected(tmp_path):
    # The split's other list is held to the same rule: a numbered figure's
    # link must land on a page that actually carries its raster.
    pdf = _plate_pdf(tmp_path / "figs.pdf", target_has_image=False, label="List of Figures")
    with pytest.raises(SystemExit, match="List of Figures links point at imageless pages"):
        verify_pdf.verify_plate_links(pdf)


@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_a_plate_link_to_an_illustrated_page_passes(tmp_path):
    pdf = _plate_pdf(tmp_path / "illustrated.pdf", target_has_image=True)
    assert verify_pdf.verify_plate_links(pdf) is None
