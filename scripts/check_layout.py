#!/usr/bin/env python3
"""Browser layout regression for the documentation site.

Static markup checks (build_site.py's check_accessibility) cannot see that
the sidebar wrapped into a second column and covered the prose: only a real
engine that lays out the page and measures boxes can. This drives headless
Chrome over the DevTools Protocol (no third-party driver, no network fetch --
Chrome speaks CDP over an inherited pipe), loads each BUILT page at a matrix
of viewports and text-zoom levels, and asserts the invariants issue #195
named:

  * navigation and article rectangles never intersect,
  * the document never overflows horizontally,
  * the current page's nav link takes a *visible* keyboard focus ring, and
  * the last navigation item is reachable by keyboard and actually on screen
    (not sheared off into a clipped second column).

The short-desktop regression case (1265x697) is in the matrix by name.

Two halves, split so each is proven the way it can be: `assess_page` is the
pure policy (given measurements, is the layout sound?) and is unit-tested
against known-good and known-bad geometry; the CDP driver is the boundary
that produces those measurements from a real browser, exercised end to end
by an integration test against good/overlapping HTML fixtures and, in CI, by
running over the whole built site.

Run directly:  python3 scripts/check_layout.py build/site
With PRESS_REQUIRE_BROWSER_CHECK=1 a missing browser is a hard failure (the
posture CI wants); without it, a missing browser skips with a notice (a
contributor without Chrome still gets a green local site build, the same way
a missing epubcheck is a skip, not a red EPUB).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Viewports the site must survive, in CSS pixels at 100% zoom. The
# short-desktop case is the reported regression (#195); the others bracket
# it so a fix that helps one width but breaks another cannot pass.
VIEWPORTS: dict[str, tuple[int, int]] = {
    "desktop": (1440, 900),
    "short-desktop": (1265, 697),
    "tablet": (820, 1180),
    "narrow-mobile": (390, 844),
}

# Text zoom, modelled the way a browser applies it to layout: at 200% the
# page has half as many CSS pixels of viewport, so media queries and wrapping
# behave as at half the width. Dividing the CSS viewport reproduces exactly
# that reflow.
ZOOMS: tuple[int, ...] = (1, 2)

# A representative slice of pages rather than all 23: the sidebar is identical
# on every page, so overlap and reachability are page-independent, while these
# three bracket the content that could overflow -- the long landing, the long
# reference, and the image-and-card gallery.
DEFAULT_PAGES: tuple[str, ...] = ("index.html", "reference.html", "gallery.html")

# Rectangles that merely share an edge (the sidebar and the prose column sit
# flush on the desktop) must not read as an overlap; a real wrap pushes the
# nav well past the seam. One CSS pixel of slack draws that line.
OVERLAP_EPSILON = 1.0

MAX_TABS = 90  # cap the keyboard walk so an unreachable last item terminates

# The candidate browser binaries, in preference order. PRESS_CHROME wins so a
# machine with a non-standard install can point at it.
_CHROME_CANDIDATES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
)
_CHROME_MAC_APP = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def find_chrome() -> str | None:
    """Resolve a Chrome/Chromium executable, or None if none is installed."""

    override = os.environ.get("PRESS_CHROME")
    if override:
        return override if Path(override).exists() else None
    for name in _CHROME_CANDIDATES:
        found = shutil.which(name)
        if found:
            return found
    if Path(_CHROME_MAC_APP).exists():
        return _CHROME_MAC_APP
    return None


# --- the CDP-over-pipe driver ------------------------------------------------
#
# Chrome launched with --remote-debugging-pipe reads NUL-delimited JSON
# commands from file descriptor 3 and writes replies and events to fd 4. That
# is the whole transport: no websocket, no HTTP upgrade, no port to poll, and
# nothing to install. We dup our pipe ends onto 3 and 4 in the child.


class _Pipe:
    def __init__(self, wfd: int, rfd: int) -> None:
        self._wfd = wfd
        self._rfd = rfd
        self._buf = b""
        self._id = 0

    def send(self, method: str, params: dict | None = None,
             session: str | None = None) -> int:
        self._id += 1
        msg: dict = {"id": self._id, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        os.write(self._wfd, json.dumps(msg).encode("utf-8") + b"\0")
        return self._id

    def _recv(self) -> dict:
        while b"\0" not in self._buf:
            chunk = os.read(self._rfd, 65536)
            if not chunk:
                raise RuntimeError("Chrome closed the DevTools pipe")
            self._buf += chunk
        raw, self._buf = self._buf.split(b"\0", 1)
        return json.loads(raw)

    def call(self, method: str, params: dict | None = None,
             session: str | None = None) -> dict:
        want = self.send(method, params, session)
        while True:
            msg = self._recv()
            if msg.get("id") != want:
                continue
            if "error" in msg:
                raise RuntimeError(f"{method} failed: {msg['error']}")
            return msg.get("result", {})

    def wait_event(self, method: str, session: str | None = None) -> None:
        while True:
            msg = self._recv()
            if msg.get("method") == method and (
                session is None or msg.get("sessionId") == session
            ):
                return


class Chrome:
    """A headless Chrome the checker drives page by page. Context manager:
    the browser and its scratch profile are torn down on exit."""

    def __init__(self, executable: str) -> None:
        self._exe = executable
        self._proc: subprocess.Popen | None = None
        self._profile: str | None = None
        self._pipe: _Pipe | None = None
        self._session: str | None = None

    def __enter__(self) -> Chrome:
        cmd_r, cmd_w = os.pipe()
        evt_r, evt_w = os.pipe()
        self._profile = tempfile.mkdtemp(prefix="press-layout-")
        args = [
            self._exe, "--headless=new", "--remote-debugging-pipe",
            "--no-first-run", "--no-default-browser-check", "--no-sandbox",
            "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
            f"--user-data-dir={self._profile}", "about:blank",
        ]

        def _preexec() -> None:  # pragma: no cover - runs in the forked child
            os.dup2(cmd_r, 3)
            os.dup2(evt_w, 4)

        self._proc = subprocess.Popen(
            args, preexec_fn=_preexec, pass_fds=(3, 4), close_fds=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        os.close(cmd_r)
        os.close(evt_w)
        self._pipe = _Pipe(cmd_w, evt_r)
        self._attach()
        return self

    def __exit__(self, *exc: object) -> None:
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:  # pragma: no cover - defensive
                self._proc.kill()
        if self._profile:
            shutil.rmtree(self._profile, ignore_errors=True)

    def _attach(self) -> None:
        pipe = self._pipe
        assert pipe is not None
        result = pipe.call("Target.createTarget", {"url": "about:blank"})
        target = result["targetId"]
        attached = pipe.call(
            "Target.attachToTarget", {"targetId": target, "flatten": True}
        )
        self._session = attached["sessionId"]
        pipe.call("Page.enable", session=self._session)

    def set_viewport(self, width: int, height: int) -> None:
        assert self._pipe is not None
        self._pipe.call(
            "Emulation.setDeviceMetricsOverride",
            {"width": width, "height": height,
             "deviceScaleFactor": 1, "mobile": False},
            session=self._session,
        )

    def navigate(self, url: str) -> None:
        assert self._pipe is not None
        self._pipe.call("Page.navigate", {"url": url}, session=self._session)
        self._pipe.wait_event("Page.loadEventFired", session=self._session)

    def evaluate(self, expression: str) -> object:
        assert self._pipe is not None
        result = self._pipe.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True,
             "awaitPromise": True},
            session=self._session,
        )
        if "exceptionDetails" in result:
            raise RuntimeError(f"page script threw: {result['exceptionDetails']}")
        return result.get("result", {}).get("value")

    def press_key(self, key: str, code: str, vk: int) -> None:
        assert self._pipe is not None
        for kind in ("rawKeyDown", "keyUp"):
            self._pipe.call(
                "Input.dispatchKeyEvent",
                {"type": kind, "key": key, "code": code,
                 "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk},
                session=self._session,
            )

    def tab(self) -> None:
        self.press_key("Tab", "Tab", 9)

    def space(self) -> None:
        self.press_key(" ", "Space", 32)


# --- the page scripts --------------------------------------------------------
#
# Read as much geometry as possible in one round trip. Returned by value, so
# the Python side sees plain dicts.

_GEOMETRY_JS = """
(() => {
  const rect = (el) => {
    if (!el) return null;
    const b = el.getBoundingClientRect();
    return {x: b.x, y: b.y, width: b.width, height: b.height};
  };
  const id = (a) => a
    ? (a.getAttribute('href') || '') + '|' + (a.textContent || '').trim()
    : null;
  const nav = document.querySelector('header.toolbar');
  const main = document.getElementById('main-content');
  const site = document.querySelector('nav[aria-label="Site"]');
  const anchors = site ? Array.from(site.querySelectorAll('a')) : [];
  const last = anchors.length ? anchors[anchors.length - 1] : null;
  const current = document.querySelector(
    'nav[aria-label="Site"] a[aria-current="page"]');
  const de = document.documentElement;
  return {
    nav: rect(nav),
    main: rect(main),
    docScrollW: de.scrollWidth,
    docClientW: de.clientWidth,
    // The regression signature: an over-tall sidebar that wraps into a
    // second column overflows its own box horizontally (scrollWidth grows
    // past clientWidth) and the extra column is clipped -- the sheared
    // labels of #195. A sound sidebar only ever scrolls vertically.
    navScrollW: nav ? nav.scrollWidth : 0,
    navClientW: nav ? nav.clientWidth : 0,
    lastId: id(last),
    currentId: id(current),
    navCount: anchors.length,
  };
})()
"""

_FOCUS_JS = """
(() => {
  const a = document.activeElement;
  if (!a || a === document.body) return null;
  const b = a.getBoundingClientRect();
  const cs = getComputedStyle(a);
  const cx = b.x + b.width / 2;
  const cy = b.y + b.height / 2;
  const top = document.elementFromPoint(cx, cy);
  const onScreen = !!top && (top === a || a.contains(top) || top.contains(a));
  const id = (a.tagName === 'A')
    ? (a.getAttribute('href') || '') + '|' + (a.textContent || '').trim()
    : null;
  return {
    tag: a.tagName,
    isToggle: a.id === 'nav-toggle',
    inSiteNav: !!(a.closest && a.closest('nav[aria-label="Site"]')),
    ariaCurrent: a.getAttribute ? (a.getAttribute('aria-current') || '') : '',
    navId: id,
    focusVisible: !!(a.matches && a.matches(':focus-visible')),
    outlineWidth: parseFloat(cs.outlineWidth) || 0,
    outlineStyle: cs.outlineStyle,
    onScreen: onScreen,
    area: b.width * b.height,
  };
})()
"""


# --- measurement (browser boundary) -----------------------------------------


def _rects_intersect(a: dict, b: dict, epsilon: float = OVERLAP_EPSILON) -> bool:
    return (
        a["x"] < b["x"] + b["width"] - epsilon
        and b["x"] < a["x"] + a["width"] - epsilon
        and a["y"] < b["y"] + b["height"] - epsilon
        and b["y"] < a["y"] + a["height"] - epsilon
    )


def _walk_focus(chrome: Chrome, last_id: str | None,
                current_id: str | None) -> tuple[dict | None, dict | None]:
    """Tab through the page from the top, opening a collapsed mobile nav when
    the toggle takes focus, until the last nav item is reached or the cap is
    hit. Returns the focus record for the current-page item and for the last
    item (each None if never focused)."""

    current_focus: dict | None = None
    last_focus: dict | None = None
    for _ in range(MAX_TABS):
        chrome.tab()
        info = chrome.evaluate(_FOCUS_JS)
        if not isinstance(info, dict):
            continue
        if info["isToggle"]:
            chrome.space()  # reveal the CSS-only mobile disclosure
            continue
        if (current_focus is None and info["inSiteNav"]
                and info["ariaCurrent"] == "page" and info["navId"] == current_id):
            current_focus = info
        if info["navId"] and info["navId"] == last_id:
            last_focus = info
            break
    return current_focus, last_focus


def measure(chrome: Chrome, url: str, css_w: int, css_h: int) -> dict:
    """Load one page at one CSS viewport and gather everything assess_page
    needs. The keyboard walk starts from a freshly loaded document."""

    chrome.set_viewport(css_w, css_h)
    chrome.navigate(url)
    geometry = chrome.evaluate(_GEOMETRY_JS)
    if not isinstance(geometry, dict):
        raise RuntimeError(f"{url}: page geometry script returned no object")
    current_focus, last_focus = _walk_focus(
        chrome, geometry.get("lastId"), geometry.get("currentId"))
    return {
        "nav": geometry["nav"],
        "main": geometry["main"],
        "doc_scroll_w": geometry["docScrollW"],
        "doc_client_w": geometry["docClientW"],
        "nav_scroll_w": geometry["navScrollW"],
        "nav_client_w": geometry["navClientW"],
        "last_id": geometry.get("lastId"),
        "current_id": geometry.get("currentId"),
        "current_focus": current_focus,
        "last_focus": last_focus,
    }


# --- policy (pure, unit-tested) ---------------------------------------------


def assess_page(m: dict) -> list[str]:
    """Given one page's measurements, return the invariant violations. Pure:
    no browser, no I/O -- this is the half a unit test can pin to known-good
    and known-bad geometry."""

    problems: list[str] = []
    nav, main = m.get("nav"), m.get("main")
    if not nav or not main:
        problems.append("nav or article region is missing from the page")
    elif _rects_intersect(nav, main):
        problems.append(
            "navigation and article rectangles overlap "
            f"(nav {nav}, article {main})")

    if m["doc_scroll_w"] > m["doc_client_w"] + OVERLAP_EPSILON:
        problems.append(
            "document overflows horizontally "
            f"(scrollWidth {m['doc_scroll_w']} > clientWidth {m['doc_client_w']})")

    if m.get("nav_client_w", 0) and \
            m["nav_scroll_w"] > m["nav_client_w"] + OVERLAP_EPSILON:
        problems.append(
            "navigation wrapped into a clipped second column "
            f"(nav scrollWidth {m['nav_scroll_w']} > clientWidth "
            f"{m['nav_client_w']})")

    cf = m.get("current_focus")
    if m.get("current_id") is None:
        pass  # a page with no current-nav marker (e.g. a footer page) is fine
    elif cf is None:
        problems.append("current nav item never took keyboard focus")
    elif not cf["focusVisible"] or cf["outlineWidth"] <= 0 \
            or cf["outlineStyle"] == "none":
        problems.append(
            "current nav item has no visible focus ring "
            f"(focus-visible {cf['focusVisible']}, "
            f"outline {cf['outlineWidth']}px {cf['outlineStyle']})")

    lf = m.get("last_focus")
    if m.get("last_id") is None:
        problems.append("page exposes no navigation items")
    elif lf is None:
        problems.append("last nav item is not keyboard reachable")
    elif not lf["onScreen"] or lf["area"] <= 0:
        problems.append(
            "last nav item is reachable but not on screen "
            f"(on-screen {lf['onScreen']}, area {lf['area']})")
    return problems


# --- orchestration -----------------------------------------------------------


def check_site(site_dir: Path, chrome_path: str,
               pages: tuple[str, ...] = DEFAULT_PAGES) -> list[str]:
    """Drive the built site through the full matrix and collect every
    violation, labelled with the page, viewport, and zoom it happened at."""

    problems: list[str] = []
    with Chrome(chrome_path) as chrome:
        for page in pages:
            path = site_dir / page
            if not path.exists():
                problems.append(f"{page}: not present in {site_dir}")
                continue
            url = path.resolve().as_uri()
            for vname, (w, h) in VIEWPORTS.items():
                for zoom in ZOOMS:
                    css_w, css_h = round(w / zoom), round(h / zoom)
                    m = measure(chrome, url, css_w, css_h)
                    label = f"{page} @ {vname} {w}x{h} {zoom * 100}%"
                    problems.extend(f"{label}: {p}" for p in assess_page(m))
    return problems


def run(site_dir: Path, required: bool | None = None) -> list[str]:
    """Entry point build_site.py calls after it writes the pages. Returns the
    list of problems (empty on success). A missing browser is a hard failure
    when required (CI, via PRESS_REQUIRE_BROWSER_CHECK) and a printed skip
    otherwise."""

    if required is None:
        required = os.environ.get("PRESS_REQUIRE_BROWSER_CHECK") == "1"
    chrome_path = find_chrome()
    if chrome_path is None:
        message = ("no Chrome/Chromium found for the layout check "
                   "(set PRESS_CHROME to its path)")
        if required:
            raise SystemExit(f"layout check required but {message}")
        print(f"~ layout check skipped: {message}")
        return []
    problems = check_site(site_dir, chrome_path)
    if problems:
        raise SystemExit(
            "documentation layout regressed:\n  - " + "\n  - ".join(problems))
    matrix = len(DEFAULT_PAGES) * len(VIEWPORTS) * len(ZOOMS)
    print(f"+ layout check passed ({matrix} page/viewport/zoom combinations)")
    return problems


def main(argv: list[str]) -> int:
    site_dir = Path(argv[1]) if len(argv) > 1 else ROOT / "build" / "site"
    run(site_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
