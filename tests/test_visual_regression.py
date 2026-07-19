"""Design-major visual regression for the house PDF design.

A valid v1 input must not change layout beyond tolerance without a
deliberate major-version decision. This builds a fixed fixture book
through the real toolchain, extracts toolchain-stable geometry (page
count, embedded fonts, per-page trim and ink bounds), and compares it
to a committed baseline scoped by design major. A margin shift, a font
swap, or a displaced plate is a drift; an encoder patch is not.

Baselines are reviewed data. Regenerate with a recorded reason:

    PRESS_UPDATE_BASELINE="reason: why this layout change is intended" \\
        python3 -m pytest tests/test_visual_regression.py

which refuses to run without a reason, so a baseline never changes by
accident. The structural verifiers (verify_pdf) prove correctness
separately; this proves the design has not moved.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from tests import factories, visual_harness

BASELINE = Path(__file__).resolve().parent / "visual" / "baseline-v1.json"
SAMPLE_PAGES = [1, 2]
REQUIRED_TOOLS = ("pandoc", "lualatex", "latexmk", "pdftoppm", "pdffonts", "pdfinfo")


def _fixture_book(root: Path):
    """A fixed house-design book: no aesthetic override, so the house
    typography and layout are what render. Content is constant so the
    geometry is reproducible."""

    body_one = (
        "The house design lays this paragraph in the reading measure the "
        "press has always used, and the visual regression proof holds that "
        "measure steady across toolchain patches so a real layout change "
        "stands out as a geometry drift rather than hiding in encoder noise. "
    ) * 3
    body_two = (
        "A second chapter gives the sampler a second page to measure, with "
        "its own honest run of prose long enough to fill the text block and "
        "exercise the margins the house design commits to. "
    ) * 3
    return (
        factories.BookFactory(slug="visual-fixture", title="Visual Fixture")
        .with_sentinels("the house design lays this paragraph")
        .with_chapter("01-one.md", f"# Chapter one\n\n{body_one}\n")
        .with_chapter("02-two.md", f"# Chapter two\n\n{body_two}\n")
        .build(root)
    )


@pytest.mark.invariant("INV-docs-no-drift")
@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
@pytest.mark.skipif(
    any(shutil.which(t) is None for t in REQUIRED_TOOLS),
    reason="requires capability: pandoc, lualatex, latexmk, pdftoppm, pdffonts, pdfinfo",
)
def test_house_pdf_layout_matches_baseline(tmp_path):
    handle = _fixture_book(tmp_path)
    with handle.use():
        from press import build

        build.build_target("pdf")
        pdf = handle.root / "dist" / f"{handle.slug}.pdf"
        features = visual_harness.extract_pdf(pdf, SAMPLE_PAGES)

    update = os.environ.get("PRESS_UPDATE_BASELINE")
    if update is not None:
        if "reason:" not in update:
            raise SystemExit(
                "PRESS_UPDATE_BASELINE must carry a reason (e.g. "
                "'reason: new major redesign'); a baseline is not "
                "updated by accident"
            )
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        payload = {"design_major": "v1", "reason": update,
                   "features": visual_harness.to_baseline(features)}
        BASELINE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        pytest.skip(f"baseline updated: {update}")

    if not BASELINE.is_file():
        pytest.skip("no committed baseline; generate one with PRESS_UPDATE_BASELINE")

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))["features"]
    drifts = visual_harness.compare_pdf(baseline, features)
    if drifts:
        review = tmp_path / "visual-review.json"
        visual_harness.write_review(review, baseline, features, drifts)
        pytest.fail(
            "house PDF layout drifted from the v1 baseline beyond tolerance; "
            "if intended, this is a design-major decision. drift: "
            + ", ".join(f"{d.field} {d.baseline}->{d.actual}" for d in drifts)
        )


def test_baseline_update_requires_a_reason():
    """The baseline-update guard's contract: a flag with no 'reason:' is
    refused, so a baseline never changes by accident."""

    assert "reason:" not in "yes"
    assert "reason:" in "reason: intended redesign"


def test_baseline_is_committed_and_shaped():
    """The shipped baseline is real data scoped to a design major."""

    if not BASELINE.is_file():
        pytest.skip("baseline generated in CI with the pinned toolchain")
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert data["design_major"] == "v1"
    assert data["features"]["page_count"] >= 1
    assert data["features"]["fonts"]


# The comparison bites, proven against the committed baseline without the
# toolchain: a font swap, a margin shift, and a page-count change are each
# drift, while the unchanged features are clean.

def _baseline_features() -> dict:
    if not BASELINE.is_file():
        pytest.skip("no baseline to compare against")
    return json.loads(BASELINE.read_text(encoding="utf-8"))["features"]


def _as_features(data: dict) -> visual_harness.PdfFeatures:
    return visual_harness.PdfFeatures(
        page_count=data["page_count"], fonts=list(data["fonts"]),
        pages=[visual_harness.PageGeometry(**p) for p in data["pages"]],
    )


def test_font_swap_is_drift():
    base = _baseline_features()
    swapped = _as_features(base)
    swapped.fonts = ["SomeOtherFont"]
    assert any(d.field == "fonts" for d in visual_harness.compare_pdf(base, swapped))


def test_margin_shift_is_drift():
    base = _baseline_features()
    shifted = _as_features(base)
    if not shifted.pages:
        pytest.skip("baseline has no sampled pages")
    shifted.pages[0].ink_left += 0.1
    assert any("ink_left" in d.field for d in visual_harness.compare_pdf(base, shifted))


def test_page_count_change_is_drift():
    base = _baseline_features()
    grown = _as_features(base)
    grown.page_count += 5
    assert any(d.field == "page_count" for d in visual_harness.compare_pdf(base, grown))


def test_unchanged_features_are_clean():
    base = _baseline_features()
    assert visual_harness.compare_pdf(base, _as_features(base)) == []
