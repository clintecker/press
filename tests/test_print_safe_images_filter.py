"""The print-safe-images filter redirects interior figure paths to the
flattened, resolution-capped copies press.print_safe writes under
build/print-assets/. Applied only through the print defaults, so the reading
PDF keeps the originals. This is the one filter that had no focused test
(test_print_safe.py covers the Python module, not the Lua); it was exercised
only incidentally through a full print build. docs/LUA-QUALITY-PLAN.md §6.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

FILTER = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "press"
    / "data"
    / "lua"
    / "print-safe-images.lua"
)

_needs_pandoc = pytest.mark.skipif(
    shutil.which("pandoc") is None, reason="requires capability: pandoc"
)


def _rewrite(src: str) -> str:
    """The image src after the filter runs, read from the HTML output."""
    md = f"![a figure]({src})\n"
    result = subprocess.run(
        ["pandoc", "-f", "markdown", "-t", "html", f"--lua-filter={FILTER}"],
        input=md,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    m = re.search(r'src="([^"]*)"', result.stdout)
    assert m, f"no <img src> in output:\n{result.stdout}"
    return m.group(1)


@_needs_pandoc
@pytest.mark.layer("integration")
@pytest.mark.parametrize(
    "given",
    ["assets/plate.png", "./assets/plate.png", "/assets/plate.png"],
)
def test_interior_asset_paths_redirect_to_print_safe(given):
    # Every way an assets/ path can be written lands on the same print copy,
    # with any leading ./ or / normalized away.
    assert _rewrite(given) == "build/print-assets/assets/plate.png"


@_needs_pandoc
@pytest.mark.layer("integration")
def test_a_non_asset_path_is_left_alone():
    # A path outside assets/ (an absolute URL, a sibling dir) is not a book
    # figure the print pack sanitizes; the filter must not touch it.
    assert _rewrite("https://example.com/x.png") == "https://example.com/x.png"
    assert _rewrite("img/plate.png") == "img/plate.png"


@_needs_pandoc
@pytest.mark.layer("integration")
def test_an_already_redirected_path_is_not_doubled():
    # Idempotent: a path already under build/print-assets/ is not rewritten
    # again, so re-running the print defaults cannot nest the prefix.
    already = "build/print-assets/assets/plate.png"
    assert _rewrite(already) == already
