"""A toolchain-free golden of the generated front matter and the pure
cover-wrap geometry (INV-graph-escaping, INV-coverwrap-geometry).

gen_front_matter.generate assembles the title page, colophon, and epigraph
from config by keeping or dropping template blocks and substituting escaped
fields -- pure text work that needs no LuaLaTeX. This snapshots its output
for a fixed, fully-populated fixture and holds it against a committed golden,
and asserts the structure directly: which blocks are present or absent per
config, the cover and logo \\includegraphics sizing, and that TeX-active
characters in the data are escaped. The cover wrap's geometry is proven
through its pure ``wrap_geometry`` (the LaTeX assembly and compile need the
toolchain and are proven at the integration tier).

Regenerate the golden with a recorded reason after a deliberate template
change (which, for a valid book's layout, is a design-major decision):

    PRESS_UPDATE_GOLDEN="reason: why" python3 -m pytest \\
        tests/test_gen_front_matter_golden.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image

from press import gen_coverwrap, gen_front_matter
from tests import factories

GOLDEN = Path(__file__).resolve().parent / "golden" / "front-matter-full.tex"


def _full_book(tmp_path: Path):
    """A fixed book that exercises every front-matter block, with TeX-active
    characters in the data so escaping is on the record."""

    handle = (
        factories.minimal()
        .with_metadata(
            title="Make & Ready",
            subtitle="A Manual; OR, The Devil's Work",
            copyright="Copyright 2026 A. Author.",
            publisher="Test Press",
            date="2026",
            **{"publisher-place": "Nowhere"},
        )
        .with_front_matter(
            dedication="For R&D, and 50% of the shop.",
            epigraph={"quote": "Type is 100% honest.", "attribution": "A. Printer"},
            acknowledgements="Thanks to the whole shop.",
            **{
                "edition-note": "First edition",
                "rights-notice": "All rights reserved.",
                "manufacture": "Printed by hand.",
                "colophon-note": "Set in Libertinus.",
                "contact": "press@example.org",
                "motto": "Festina lente.",
            },
        )
        .build(tmp_path)
    )
    assets = handle.root / "assets"
    assets.mkdir(exist_ok=True)
    Image.new("RGB", (200, 300), (40, 60, 80)).save(assets / "cover.jpg")
    Image.new("RGBA", (120, 120), (0, 0, 0, 255)).save(assets / "press-logo.png")
    return handle


def _generate(tmp_path: Path) -> str:
    handle = _full_book(tmp_path)
    with handle.use():
        out = gen_front_matter.generate(include_cover=True)
    assert out is not None
    return out.read_text(encoding="utf-8")


@pytest.mark.invariant("INV-graph-escaping")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_generated_front_matter_matches_the_golden(tmp_path):
    tex = _generate(tmp_path)

    update = os.environ.get("PRESS_UPDATE_GOLDEN")
    if update is not None:
        if "reason:" not in update:
            raise SystemExit(
                "PRESS_UPDATE_GOLDEN must carry a reason; a golden is not "
                "updated by accident"
            )
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(tex, encoding="utf-8")
        pytest.skip(f"golden updated: {update}")

    assert GOLDEN.is_file(), "no committed golden; generate with PRESS_UPDATE_GOLDEN"
    assert tex == GOLDEN.read_text(encoding="utf-8"), (
        "generated front matter drifted from tests/golden/front-matter-full.tex; "
        "if the template change is intended (a design-major decision), regenerate "
        "with PRESS_UPDATE_GOLDEN"
    )


@pytest.mark.invariant("INV-graph-escaping")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_present_blocks_and_escaped_fields(tmp_path):
    tex = _generate(tmp_path)
    # Every configured block is kept, with its (escaped) content.
    assert "For R\\&D, and 50\\% of the shop." in tex          # dedication, escaped
    assert "Type is 100\\% honest." in tex                     # epigraph quote, escaped
    assert "A. Printer" in tex                                 # epigraph attribution
    assert "Thanks to the whole shop." in tex                 # acknowledgements
    assert "Festina lente." in tex                             # motto
    assert "Printed by hand." in tex                           # manufacture
    assert "Set in Libertinus." in tex                         # colophon-note
    assert "All rights reserved." in tex                       # rights-notice
    assert "press@example.org" in tex                          # contact
    # The uppercased title keeps its ampersand escaped.
    assert "MAKE \\& READY." in tex
    # No raw TeX-active ampersand or percent survives from the data.
    assert "R&D" not in tex and "100%" not in tex


@pytest.mark.invariant("INV-graph-escaping")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_cover_and_logo_includegraphics_sizing(tmp_path):
    tex = _generate(tmp_path)
    cover_line = next(ln for ln in tex.splitlines()
                      if "includegraphics" in ln and "cover.jpg" in ln)
    # The cover plate fits the text block; never a fixed inch size (which
    # clipped a 5x8 page) -- the scar this sizing carries.
    assert r"width=\textwidth,height=\textheight,keepaspectratio" in cover_line
    assert "in]" not in cover_line and "in," not in cover_line
    assert "press-logo.png" in tex  # the logo block is kept when the asset exists


@pytest.mark.invariant("INV-graph-escaping")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_absent_blocks_are_dropped_for_a_bare_book(tmp_path):
    """A book whose only front matter is a cover keeps no dedication,
    epigraph, colophon note, or registration block: the keep_block machinery
    removes what the config does not populate."""

    handle = factories.minimal().with_metadata(
        copyright="Copyright 2026 A. Author.", publisher="Test Press",
        **{"publisher-place": "Nowhere"}).build(tmp_path)
    (handle.root / "assets").mkdir(exist_ok=True)
    Image.new("RGB", (200, 300), (40, 60, 80)).save(handle.root / "assets" / "cover.jpg")
    with handle.use():
        out = gen_front_matter.generate(include_cover=True)
    tex = out.read_text(encoding="utf-8")
    assert "Festina lente." not in tex
    assert "ISBN (print)" not in tex and "ISBN (ebook)" not in tex
    assert "Thanks to" not in tex
    # But the cover it does have still reaches the page.
    assert "cover.jpg" in tex and "includegraphics" in tex


# ---- gen_coverwrap: the pure wrap geometry (INV-coverwrap-geometry) ----

@pytest.mark.invariant("INV-coverwrap-geometry")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_perfect_bound_wrap_geometry_is_exact():
    """The pure wrap composition for a perfect-bound 6x9 with a 0.5in spine
    and 0.125in bleed: total size and panel edges are the documented v1
    numbers, computed with no toolchain."""

    lay = gen_coverwrap.wrap_geometry(
        trim_w=6.0, trim_h=9.0, spine=0.5, has_spine=True,
        margin=0.125, inner=0.0, width_delta=0.0, height_delta=0.0,
        material="paperback",
    )
    # wrap_w = 2*bleed + 2*trim + spine; wrap_h = 2*bleed + trim_h.
    assert lay.wrap_w == pytest.approx(2 * 0.125 + 2 * 6.0 + 0.5)   # 12.75
    assert lay.wrap_h == pytest.approx(2 * 0.125 + 9.0)             # 9.25
    assert lay.back_x == pytest.approx(0.125)
    assert lay.front_x == pytest.approx(0.125 + 6.0 + 0.5)          # 6.625
    assert lay.panel_w == pytest.approx(6.0)
    # A flat wrap (inner 0) bleeds the front art past its panel to the edge.
    assert lay.front_art_w == pytest.approx(6.0 + 0.125)
    assert lay.cloth_field is True


@pytest.mark.invariant("INV-coverwrap-geometry")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_linen_material_paints_no_field_and_spine_flag_carries():
    lay = gen_coverwrap.wrap_geometry(
        trim_w=5.0, trim_h=8.0, spine=0.0, has_spine=False,
        margin=0.125, inner=0.0, width_delta=0.0, height_delta=0.0,
        material="linen",
    )
    assert lay.cloth_field is False   # linen: the material is the finish
    assert lay.has_spine is False
    assert lay.spine == 0.0
    # A hinged/flapped cover (inner > 0) keeps the art to its own panel.
    hinged = gen_coverwrap.wrap_geometry(
        trim_w=6.0, trim_h=9.0, spine=0.6, has_spine=True,
        margin=0.75, inner=0.5, width_delta=0.125, height_delta=0.125,
        material="cloth",
    )
    assert hinged.front_art_w == pytest.approx(6.0 + 0.125)  # panel_w, not bled
    assert hinged.panel_w == pytest.approx(6.125)
