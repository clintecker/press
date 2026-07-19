"""Toolchain-stable visual features for design-regression proofs.

Raw PDF or PNG bytes change with every encoder tweak, so they cannot be
snapshotted. What is stable for a fixed design across pandoc and
LuaLaTeX patch versions is geometry: how many pages, at what trim,
which fonts are embedded, and where the ink sits on the page. This
harness extracts exactly those features from a built PDF and from
rendered web surfaces, so a design regression (a margin shift, a font
swap, a plate displaced) is a geometry diff, while an irrelevant
encoding change is not.

Features are compared to a baseline scoped by design major (v1). A
baseline is data a human reviewed and committed; updating one is a
deliberate act with a recorded reason, never a silent overwrite.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PIL import Image


@dataclass
class PageGeometry:
    width_pt: float
    height_pt: float
    ink_left: float  # fraction of page width, 0..1
    ink_right: float
    ink_top: float  # fraction of page height, 0..1
    ink_bottom: float


@dataclass
class PdfFeatures:
    page_count: int
    fonts: list[str]
    pages: list[PageGeometry] = field(default_factory=list)


def _pdfinfo_pages(pdf: Path) -> int:
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    raise SystemExit("pdfinfo reported no page count")


def _embedded_fonts(pdf: Path) -> list[str]:
    out = subprocess.run(["pdffonts", str(pdf)], capture_output=True, text=True, check=True).stdout
    names = []
    for line in out.splitlines()[2:]:
        parts = line.split()
        if parts:
            # Strip pandoc/LuaTeX's per-build subset tag (ABCDEF+Name).
            name = parts[0]
            if "+" in name:
                name = name.split("+", 1)[1]
            names.append(name)
    return sorted(set(names))


def _ink_box(image: Image.Image) -> tuple[float, float, float, float]:
    gray = image.convert("L")
    # Dark pixels are ink; the bounding box of everything below mid-gray.
    mask = gray.point(lambda v: 255 if v < 160 else 0)
    box = mask.getbbox()
    if box is None:
        return (0.0, 0.0, 0.0, 0.0)
    w, h = gray.size
    left, top, right, bottom = box
    return (left / w, right / w, top / h, bottom / h)


def extract_pdf(pdf: Path, sample_pages: list[int], dpi: int = 72) -> PdfFeatures:
    """Geometry of the sampled pages plus the whole document's page count
    and embedded fonts. Pages are 1-indexed."""

    from pypdf import PdfReader

    reader = PdfReader(str(pdf))
    features = PdfFeatures(page_count=_pdfinfo_pages(pdf), fonts=_embedded_fonts(pdf))
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        for page_no in sample_pages:
            if page_no > len(reader.pages):
                continue
            box = reader.pages[page_no - 1].mediabox
            subprocess.run(
                ["pdftoppm", "-png", "-r", str(dpi), "-f", str(page_no),
                 "-l", str(page_no), str(pdf), str(out / "p")],
                check=True, capture_output=True,
            )
            rendered = sorted(out.glob("p*.png"))
            if not rendered:
                continue
            with Image.open(rendered[-1]) as image:
                ink = _ink_box(image)
            features.pages.append(PageGeometry(
                width_pt=round(float(box.width), 1),
                height_pt=round(float(box.height), 1),
                ink_left=round(ink[0], 3), ink_right=round(ink[1], 3),
                ink_top=round(ink[2], 3), ink_bottom=round(ink[3], 3),
            ))
    return features


# ---- baseline comparison ----

@dataclass
class Drift:
    field: str
    baseline: object
    actual: object
    tolerance: float


def compare_pdf(baseline: dict, actual: PdfFeatures, geometry_tol: float = 0.03,
                pt_tol: float = 1.0) -> list[Drift]:
    """Geometry drift beyond tolerance, scoped so a toolchain patch does
    not trip it but a layout change does."""

    drifts: list[Drift] = []
    if baseline["page_count"] != actual.page_count:
        drifts.append(Drift("page_count", baseline["page_count"], actual.page_count, 0))
    if sorted(baseline["fonts"]) != sorted(actual.fonts):
        drifts.append(Drift("fonts", baseline["fonts"], actual.fonts, 0))
    for index, (base_page, act_page) in enumerate(zip(baseline["pages"], actual.pages)):
        for dim in ("width_pt", "height_pt"):
            if abs(base_page[dim] - getattr(act_page, dim)) > pt_tol:
                drifts.append(Drift(f"page{index}.{dim}", base_page[dim],
                                    getattr(act_page, dim), pt_tol))
        for edge in ("ink_left", "ink_right", "ink_top", "ink_bottom"):
            if abs(base_page[edge] - getattr(act_page, edge)) > geometry_tol:
                drifts.append(Drift(f"page{index}.{edge}", base_page[edge],
                                    getattr(act_page, edge), geometry_tol))
    return drifts


def to_baseline(features: PdfFeatures) -> dict:
    return asdict(features)


def write_review(path: Path, baseline: dict, actual: PdfFeatures, drifts: list[Drift]) -> None:
    """A compact review artifact: expected, actual, and the drift, for a
    human deciding whether a change is a regression or a new baseline."""

    path.write_text(json.dumps({
        "baseline": baseline,
        "actual": to_baseline(actual),
        "drift": [asdict(d) for d in drifts],
    }, indent=2), encoding="utf-8")
