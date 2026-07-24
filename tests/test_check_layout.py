"""The documentation layout regression check (scripts/check_layout.py).

Two halves, proven the way each can be. `assess_page` is pure policy: given
measured geometry, does the layout hold the #195 invariants? It is pinned here
against known-good and known-bad measurements, so every rejection branch has a
case that trips it -- a checker is only real with input it refuses. The browser
half (driving headless Chrome over CDP to produce those measurements) is proven
end to end against the committed good/bad HTML fixtures when a browser is
present; without one the browser tests skip, the same posture the epubcheck and
toolchain tests take.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "layout"


def _load():
    path = ROOT / "scripts" / "check_layout.py"
    spec = importlib.util.spec_from_file_location("check_layout", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


cl = _load()


def _sound() -> dict:
    """A measurement of a healthy page: disjoint but flush nav/article, no
    overflow of the document or the sidebar, a visibly-focused current item,
    and a reachable, on-screen last item."""

    return {
        "nav": {"x": 0.0, "y": 0.0, "width": 240.0, "height": 697.0},
        "main": {"x": 240.0, "y": 0.0, "width": 1025.0, "height": 500.0},
        "doc_scroll_w": 1265.0,
        "doc_client_w": 1265.0,
        "nav_scroll_w": 239.0,
        "nav_client_w": 239.0,
        "current_id": "a1.html|Overview",
        "last_id": "repo|source",
        "current_focus": {"focusVisible": True, "outlineWidth": 2.0,
                          "outlineStyle": "solid"},
        "last_focus": {"onScreen": True, "area": 900.0},
    }


# --- pure policy: the sound page and every rejection branch ------------------


def test_a_sound_page_has_no_problems():
    assert cl.assess_page(_sound()) == []


def test_flush_sidebar_and_article_are_not_an_overlap():
    # The desktop sidebar and prose sit edge-to-edge; sharing a seam must not
    # read as an overlap.
    m = _sound()
    assert cl._rects_intersect(m["nav"], m["main"]) is False


def test_overlapping_nav_and_article_is_rejected():
    m = _sound()
    m["main"]["x"] = 120.0  # article slides under the 240px-wide nav
    problems = cl.assess_page(m)
    assert any("overlap" in p for p in problems)


def test_a_wrapped_clipped_sidebar_is_rejected():
    # The #195 signature: an over-tall sidebar wraps into a second column and
    # overflows its own box horizontally.
    m = _sound()
    m["nav_scroll_w"] = 419.0
    m["nav_client_w"] = 239.0
    problems = cl.assess_page(m)
    assert any("clipped second column" in p for p in problems)


def test_document_horizontal_overflow_is_rejected():
    m = _sound()
    m["doc_scroll_w"] = 1400.0
    problems = cl.assess_page(m)
    assert any("document overflows horizontally" in p for p in problems)


def test_a_missing_region_is_rejected():
    m = _sound()
    m["main"] = None
    problems = cl.assess_page(m)
    assert any("missing" in p for p in problems)


def test_current_item_without_focus_visible_is_rejected():
    m = _sound()
    m["current_focus"]["focusVisible"] = False
    problems = cl.assess_page(m)
    assert any("visible focus" in p for p in problems)


def test_current_item_with_no_outline_is_rejected():
    m = _sound()
    m["current_focus"] = {"focusVisible": True, "outlineWidth": 0.0,
                          "outlineStyle": "none"}
    problems = cl.assess_page(m)
    assert any("visible focus" in p for p in problems)


def test_current_item_never_focused_is_rejected():
    m = _sound()
    m["current_focus"] = None
    problems = cl.assess_page(m)
    assert any("never took keyboard focus" in p for p in problems)


def test_a_page_with_no_current_marker_is_exempt_from_focus():
    # A footer page carries no aria-current nav link; absence is not a failure.
    m = _sound()
    m["current_id"] = None
    m["current_focus"] = None
    assert cl.assess_page(m) == []


def test_unreachable_last_item_is_rejected():
    m = _sound()
    m["last_focus"] = None
    problems = cl.assess_page(m)
    assert any("not keyboard reachable" in p for p in problems)


def test_last_item_reachable_but_offscreen_is_rejected():
    m = _sound()
    m["last_focus"] = {"onScreen": False, "area": 900.0}
    problems = cl.assess_page(m)
    assert any("not on screen" in p for p in problems)


def test_a_page_with_no_nav_items_is_rejected():
    m = _sound()
    m["last_id"] = None
    problems = cl.assess_page(m)
    assert any("no navigation items" in p for p in problems)


# --- entry point posture: required vs. skip ---------------------------------


def test_required_run_without_a_browser_is_a_hard_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(cl, "find_chrome", lambda: None)
    with pytest.raises(SystemExit, match="required"):
        cl.run(tmp_path, required=True)


def test_optional_run_without_a_browser_skips(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cl, "find_chrome", lambda: None)
    assert cl.run(tmp_path, required=False) == []
    assert "skipped" in capsys.readouterr().out


def test_env_flag_makes_the_browser_required(monkeypatch, tmp_path):
    monkeypatch.setattr(cl, "find_chrome", lambda: None)
    monkeypatch.setenv("PRESS_REQUIRE_BROWSER_CHECK", "1")
    with pytest.raises(SystemExit):
        cl.run(tmp_path)  # required defaults from the env flag


def test_find_chrome_honours_an_explicit_override(monkeypatch):
    monkeypatch.setenv("PRESS_CHROME", str(FIXTURES / "good-sidebar.html"))
    assert cl.find_chrome() == str(FIXTURES / "good-sidebar.html")
    monkeypatch.setenv("PRESS_CHROME", "/no/such/browser")
    assert cl.find_chrome() is None


# --- browser end to end: the fixtures the checker must accept and reject -----


def test_the_good_fixture_passes_in_a_real_browser():
    chrome = cl.find_chrome()
    if chrome is None:
        pytest.skip("no Chrome/Chromium available for the browser layout check")
    url = (FIXTURES / "good-sidebar.html").resolve().as_uri()
    with cl.Chrome(chrome) as browser:
        m = cl.measure(browser, url, 1265, 697)
    assert cl.assess_page(m) == []


def test_the_known_bad_fixture_is_rejected_in_a_real_browser():
    chrome = cl.find_chrome()
    if chrome is None:
        pytest.skip("no Chrome/Chromium available for the browser layout check")
    url = (FIXTURES / "bad-sidebar.html").resolve().as_uri()
    with cl.Chrome(chrome) as browser:
        m = cl.measure(browser, url, 1265, 697)
    problems = cl.assess_page(m)
    assert any("clipped second column" in p for p in problems), problems
