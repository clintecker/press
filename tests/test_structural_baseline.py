"""Golden structural baselines for the non-PDF editions (INV-format-structure).

The PDF has a geometry baseline; the EPUB, reader site, and DOCX had none.
This builds a fixed fixture book through the real toolchain, extracts
toolchain-stable structure (EPUB spine/chapter/nav counts, reader-site page
and nav counts, DOCX declared styles), and compares it to a committed
baseline scoped by design major. A lost chapter document, a dropped nav
entry, or a removed house style is drift; a benign pandoc upgrade is not.

Baselines are reviewed data. Regenerate with a recorded reason:

    PRESS_UPDATE_BASELINE="reason: why this structural change is intended" \\
        python3 -m pytest tests/test_structural_baseline.py

which refuses to run without a reason, so a baseline never changes by
accident.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from tests import factories, structure_harness

BASELINE = Path(__file__).resolve().parent / "visual" / "structure-v1.json"
REQUIRED_TOOLS = ("pandoc",)


def _fixture_book(root: Path):
    """The same fixed house-design book the geometry baseline uses: constant
    content so the structure is reproducible."""

    body_one = (
        "The house design lays this paragraph in the reading measure the "
        "press has always used, and the structural regression proof holds "
        "the edition shapes steady across toolchain patches. "
    ) * 3
    body_two = (
        "A second chapter gives the sampler a second document to measure, "
        "with its own honest run of prose long enough to fill the page. "
    ) * 3
    return (
        factories.BookFactory(slug="structure-fixture", title="Structure Fixture")
        .with_sentinels("the house design lays this paragraph")
        .with_chapter("01-one.md", f"# Chapter one\n\n{body_one}\n")
        .with_chapter("02-two.md", f"# Chapter two\n\n{body_two}\n")
        .build(root)
    )


def _build_and_extract(tmp_path: Path) -> dict:
    handle = _fixture_book(tmp_path)
    with handle.use():
        from press import build

        for target in ("epub", "site", "docx"):
            build.build_target(target)
        dist = handle.root / "dist"
        return structure_harness.extract_editions(dist, handle.slug)


@pytest.mark.invariant("INV-format-structure")
@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
@pytest.mark.skipif(
    any(shutil.which(t) is None for t in REQUIRED_TOOLS),
    reason="requires capability: pandoc",
)
def test_non_pdf_editions_match_structural_baseline(tmp_path):
    actual = _build_and_extract(tmp_path)

    update = os.environ.get("PRESS_UPDATE_BASELINE")
    if update is not None:
        if "reason:" not in update:
            raise SystemExit(
                "PRESS_UPDATE_BASELINE must carry a reason (e.g. "
                "'reason: new epub layout'); a baseline is not updated by accident"
            )
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps({"design_major": "v1", "reason": update, "features": actual},
                       indent=2) + "\n",
            encoding="utf-8",
        )
        pytest.skip(f"structural baseline updated: {update}")

    if not BASELINE.is_file():
        pytest.skip("no committed structural baseline; generate with PRESS_UPDATE_BASELINE")

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))["features"]
    drifts = structure_harness.compare_structure(baseline, actual)
    assert not drifts, (
        "non-PDF editions drifted from the v1 structural baseline; if intended, "
        "regenerate with PRESS_UPDATE_BASELINE. drift: " + "; ".join(drifts)
    )


def test_structural_baseline_is_committed_and_shaped():
    """The shipped structural baseline is real data scoped to a design major."""

    if not BASELINE.is_file():
        pytest.skip("structural baseline generated with pandoc; absent here")
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert data["design_major"] == "v1"
    features = data["features"]
    assert features["epub"]["chapter_docs"] >= 1
    assert features["site"]["page_count"] >= 1
    assert features["docx"]["styles"]


# The comparison bites, proven against the committed baseline without the
# toolchain: a lost chapter document, a dropped nav entry, and a removed
# house style are each drift, while the unchanged structure is clean.

def _baseline_features() -> dict:
    if not BASELINE.is_file():
        pytest.skip("no structural baseline to compare against")
    return json.loads(BASELINE.read_text(encoding="utf-8"))["features"]


@pytest.mark.invariant("INV-format-structure")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_unchanged_structure_is_clean():
    base = _baseline_features()
    assert structure_harness.compare_structure(base, base) == []


@pytest.mark.invariant("INV-format-structure")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_lost_chapter_document_is_drift():
    base = _baseline_features()
    broken = json.loads(json.dumps(base))
    broken["epub"]["chapter_docs"] -= 1
    assert any("chapter_docs" in d for d in structure_harness.compare_structure(base, broken))


@pytest.mark.invariant("INV-format-structure")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_dropped_nav_entry_and_page_are_drift():
    base = _baseline_features()
    broken = json.loads(json.dumps(base))
    broken["epub"]["nav_entries"] -= 1
    broken["site"]["page_count"] -= 1
    drifts = structure_harness.compare_structure(base, broken)
    assert any("nav_entries" in d for d in drifts)
    assert any("page_count" in d for d in drifts)


@pytest.mark.invariant("INV-format-structure")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_removed_docx_style_is_drift():
    base = _baseline_features()
    broken = json.loads(json.dumps(base))
    if not broken["docx"]["styles"]:
        pytest.skip("baseline declares no docx styles")
    broken["docx"]["styles"] = broken["docx"]["styles"][1:]
    assert any("styles removed" in d for d in structure_harness.compare_structure(base, broken))


@pytest.mark.invariant("INV-format-structure")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_a_pandoc_added_style_is_not_drift():
    """A pandoc that declares an extra style is a benign upgrade, not drift."""

    base = _baseline_features()
    grown = json.loads(json.dumps(base))
    grown["docx"]["styles"] = grown["docx"]["styles"] + ["SomeNewTok"]
    grown["epub"]["spine_itemrefs"] += 1
    assert structure_harness.compare_structure(base, grown) == []
