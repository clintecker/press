"""The stranded-page warning (#291): verify-print flags a page whose ink is
only its running head, its folio, and one or two lines of text (a lone
Contents entry under a head and a folio passed the ink check and read as a
blank Colophon page). It is a layout warning, never a failure. The pages are
synthesised at the 120 dpi the verifier renders a 6 x 9 in page."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from press import verify_pdf

_W, _H = 720, 1080  # 6 x 9 in at 120 dpi
_LINE = 21  # a 10pt line at 1.045 leading


def _page(tmp_path: Path, name: str, *, lines: int, head: bool = True, plate: bool = False) -> Path:
    img = Image.new("RGB", (_W, _H), "white")
    draw = ImageDraw.Draw(img)
    if head:
        draw.rectangle((90, 60, 300, 68), fill="black")  # running head
    draw.rectangle((350, 1025, 370, 1033), fill="black")  # folio
    for k in range(lines):
        top = 120 + k * _LINE
        draw.rectangle((90, top, 630, top + 13), fill="black")
    if plate:
        draw.rectangle((150, 300, 570, 800), fill=(60, 60, 60))
    dest = tmp_path / f"{name}.png"
    img.save(dest)
    return dest


def test_one_or_two_lines_under_a_head_and_folio_are_warned(tmp_path, capsys):
    pages = [
        _page(tmp_path, "full", lines=30),
        _page(tmp_path, "lone", lines=1),
        _page(tmp_path, "pair", lines=2),
        _page(tmp_path, "three", lines=3),
    ]
    assert verify_pdf.warn_stranded_pages(pages) == [2, 3]
    out = capsys.readouterr().out
    assert "page 2 carries only its running head, its folio, and 1 line(s)" in out
    assert "page 3" in out and "page 4" not in out


def test_a_plate_page_and_a_text_page_are_not_warned(tmp_path):
    plate = _page(tmp_path, "plate", lines=1, head=False, plate=True)
    opener = _page(tmp_path, "opener", lines=12, head=False)
    folio_only = _page(tmp_path, "folio", lines=0)
    assert verify_pdf.warn_stranded_pages([plate, opener, folio_only]) == []


def test_ink_bands_split_lines_of_text(tmp_path):
    with Image.open(_page(tmp_path, "bands", lines=3)) as image:
        bands = verify_pdf.ink_bands(image)
    assert len(bands) == 5  # head, three lines, folio
