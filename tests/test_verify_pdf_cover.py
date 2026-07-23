"""verify_pdf.verify_cover_page -- the reading PDF must lead with its cover.

The absence of exactly this check let two bugs ship: a book with a cover but no
front-matter.yaml got a coverless title page, and a fixed-size cover plate
clipped off a 5x8 page into a blank one. This proves the verifier now rejects
both, and leaves a coverless book and a hand-authored title page alone.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from press import verify_pdf

_HEADER = ("page   num  type   width height color comp bpc  enc interp  object "
           "ID x-ppi y-ppi size ratio\n" + "-" * 80 + "\n")
_WITH_COVER = _HEADER + "   1     0 image    1000  1500  rgb     3   8  jpeg   no   4  0  267  267  397K\n"
_NO_IMAGE = _HEADER


def _page(tmp_path: Path, *, blank: bool) -> Path:
    img = Image.new("RGB", (100, 150), (255, 255, 255))
    if not blank:
        ImageDraw.Draw(img).rectangle([8, 8, 92, 142], fill=(20, 40, 60))
    dest = tmp_path / "page1.png"
    img.save(dest)
    return dest


def _book(tmp_path: Path, *, cover: bool, title_tex: bool = False) -> Path:
    if cover:
        (tmp_path / "assets").mkdir(exist_ok=True)
        Image.new("RGB", (10, 15)).save(tmp_path / "assets" / "cover.jpg")
    if title_tex:
        (tmp_path / "tex").mkdir(exist_ok=True)
        (tmp_path / "tex" / "title-page.tex").write_text("% custom", encoding="utf-8")
    return tmp_path


@pytest.mark.layer("unit")
def test_a_baked_cover_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(verify_pdf.shutil, "which", lambda _: "/pdfimages")
    monkeypatch.setattr(verify_pdf, "run_capture", lambda _: _WITH_COVER)
    root = _book(tmp_path, cover=True)
    assert verify_pdf.verify_cover_page(tmp_path / "x.pdf", root,
                                        _page(tmp_path, blank=False)) is None


@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_dropped_cover_is_rejected(tmp_path, monkeypatch):
    # page 1 renders (a text title page) but carries no cover raster.
    monkeypatch.setattr(verify_pdf.shutil, "which", lambda _: "/pdfimages")
    monkeypatch.setattr(verify_pdf, "run_capture", lambda _: _NO_IMAGE)
    root = _book(tmp_path, cover=True)
    with pytest.raises(SystemExit, match="no cover image"):
        verify_pdf.verify_cover_page(tmp_path / "x.pdf", root, _page(tmp_path, blank=False))


@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_clipped_blank_cover_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(verify_pdf.shutil, "which", lambda _: "/pdfimages")
    root = _book(tmp_path, cover=True)
    with pytest.raises(SystemExit, match="renders blank"):
        verify_pdf.verify_cover_page(tmp_path / "x.pdf", root, _page(tmp_path, blank=True))


@pytest.mark.layer("unit")
def test_a_coverless_book_is_left_alone(tmp_path):
    root = _book(tmp_path, cover=False)
    # No cover asset: even a blank page 1 is fine (a plain title page).
    assert verify_pdf.verify_cover_page(tmp_path / "x.pdf", root,
                                        _page(tmp_path, blank=True)) is None


@pytest.mark.layer("unit")
def test_a_hand_authored_title_page_is_left_alone(tmp_path):
    root = _book(tmp_path, cover=True, title_tex=True)
    assert verify_pdf.verify_cover_page(tmp_path / "x.pdf", root,
                                        _page(tmp_path, blank=True)) is None
