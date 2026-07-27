"""The non-goals boundary doc (docs/NON-GOALS.md) and its site wiring (#223).

Press deliberately is not a page-layout tool, a fixed-layout picture-book
designer, or an interactive/rich-media ebook builder; the finisher (the
supplied-interior source mode) is the supported alternative to each. That
boundary is recorded as a doc so it cannot quietly drift, and these tests are
its drift guard: the doc must name each non-goal and point at the finisher, and
the site must actually publish it (in the nav, not silently excluded), or the
build's own completeness check would fail.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "NON-GOALS.md"
DOC_SOURCE = "docs/NON-GOALS.md"


def _load_build_site():
    """Load scripts/build_site.py as a module (its imports are stdlib-only, so
    no browser or heavy dependency is needed to read its nav tables)."""

    path = ROOT / "scripts" / "build_site.py"
    spec = importlib.util.spec_from_file_location("build_site", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_doc_names_each_non_goal() -> None:
    text = DOC.read_text(encoding="utf-8").lower()
    # The three deliberately-excluded shapes, each named.
    assert "page-layout" in text
    assert "fixed-layout picture-book" in text
    assert "interactive or rich-media ebook" in text


def test_doc_points_at_the_finisher_for_each_non_goal() -> None:
    text = DOC.read_text(encoding="utf-8").lower()
    # The finisher / supplied-interior source mode is the supported answer, and
    # it is offered under every non-goal, not just once in passing.
    assert "finisher" in text
    assert "supplied-interior" in text or "supplied interior" in text
    assert text.count("the supported path") >= 3


def test_site_publishes_the_doc_in_the_nav() -> None:
    build_site = _load_build_site()
    published = {source for source, _, _ in build_site.PAGES}
    assert DOC_SOURCE in published, "non-goals doc is not wired into the site nav"
    # Publishing and conscious-exclusion are mutually exclusive; the site's
    # completeness check would reject the doc appearing in both.
    assert DOC_SOURCE not in build_site.NOT_PUBLISHED


def test_site_completeness_accounts_for_the_doc() -> None:
    # The doc is a real docs/*.md file, so build_site's own completeness check
    # (every repo Markdown file is published or consciously excluded) must pass
    # with it present -- i.e. the wiring above is what keeps the site green.
    build_site = _load_build_site()
    assert build_site.check_completeness() is None
