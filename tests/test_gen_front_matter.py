"""Generated front matter, and the cover it leads the reading PDF with.

Two regressions these pin: a book with a cover but no config/front-matter.yaml
was getting no generated front matter at all, so its cover never reached the
PDF; and the cover plate was a fixed 5.6x7.1in, which overflowed a 5x8 page and
clipped on the right. Both are proven here at the source layer, without a build.
"""

from __future__ import annotations

import pytest
from PIL import Image

from press import gen_front_matter
from tests import factories


def _book(tmp_path, *, cover: bool, front_matter: bool):
    fac = factories.minimal().with_metadata(
        copyright="Copyright 2026 A. Author.", publisher="Test Press",
        **{"publisher-place": "Nowhere"})
    if front_matter:
        fac = fac.with_front_matter(dedication="For the test.")
    handle = fac.build(tmp_path)
    if cover:
        (handle.root / "assets").mkdir(exist_ok=True)
        Image.new("RGB", (200, 300), (40, 60, 80)).save(handle.root / "assets" / "cover.jpg")
    return handle


@pytest.mark.layer("unit")
def test_cover_leads_the_reading_pdf_without_a_front_matter_yaml(tmp_path):
    handle = _book(tmp_path, cover=True, front_matter=False)
    with handle.use():
        out = gen_front_matter.generate(include_cover=True)
    assert out is not None, "a cover-only book got no front matter, so no cover"
    tex = out.read_text(encoding="utf-8")
    assert "assets/cover.jpg" in tex and "includegraphics" in tex


@pytest.mark.layer("unit")
def test_cover_plate_fits_the_trim_and_is_not_a_fixed_size(tmp_path):
    handle = _book(tmp_path, cover=True, front_matter=True)
    with handle.use():
        out = gen_front_matter.generate(include_cover=True)
    tex = out.read_text(encoding="utf-8")
    line = next(ln for ln in tex.splitlines() if "includegraphics" in ln)
    # The plate fits the text block of whatever trim this is; never a fixed
    # inch size, which clipped a 5x8 page.
    assert r"width=\textwidth,height=\textheight,keepaspectratio" in line
    assert "in," not in line and "in]" not in line


@pytest.mark.layer("unit")
def test_no_cover_and_no_front_matter_keeps_the_pandoc_default(tmp_path):
    handle = _book(tmp_path, cover=False, front_matter=False)
    with handle.use():
        assert gen_front_matter.generate(include_cover=True) is None


@pytest.mark.layer("unit")
def test_non_pdf_formats_drop_the_cover(tmp_path):
    # include_cover is False for EPUB/HTML; a cover-only book then opts out.
    handle = _book(tmp_path, cover=True, front_matter=False)
    with handle.use():
        assert gen_front_matter.generate(include_cover=False) is None
