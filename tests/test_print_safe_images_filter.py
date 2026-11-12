"""The print-safe-images filter redirects interior figure paths to the
flattened, resolution-capped copies press.print_safe writes under
build/print-assets/. Applied only through the print defaults, so the reading
PDF keeps the originals. This is the one filter that had no focused test
(test_print_safe.py covers the Python module, not the Lua); it was exercised
only incidentally through a full print build. docs/LUA-QUALITY-PLAN.md §6.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from tests import lua_coverage

FILTER = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "press"
    / "data"
    / "lua"
    / "print-safe-images.lua"
)

_needs_pandoc = lua_coverage.needs_pandoc


def _rewrite(src: str) -> str:
    """The image src after the filter runs, read from the HTML output."""
    md = f"![a figure]({src})\n"
    result = subprocess.run(
        ["pandoc", "-f", "markdown", "-t", "html", lua_coverage.filter_arg(FILTER)],
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


def _rewritten_srcs(chapter: Path) -> list[str]:
    """Every Image src in ``chapter`` after the filter ran, read from pandoc's
    own AST (the JSON writer), so the parity below is against what pandoc
    parses -- a link title, angle brackets, a reference-style image, a nested
    bracket in the caption -- not against a hand-written src string."""
    import json

    result = subprocess.run(
        ["pandoc", "-f", "markdown", "-t", "json", lua_coverage.filter_arg(FILTER), str(chapter)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    found: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("t") == "Image":
                found.append(node["c"][2][0])
            walk(node.get("c"))
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(json.loads(result.stdout)["blocks"])
    return found


# Every spelling pandoc accepts for an image under assets/, each naming a
# distinct file: plain, ./ and / prefixed, a link title, angle brackets
# around a path with a space, a percent-escaped space, a reference-style
# image, a caption with a nested link, and an extensionless src that
# lualatex resolves by extension search.
_PARITY_CHAPTER = """\
# One

![P](assets/figures/pipeline.png){.figure}

![H](./assets/fig/press.jpg)

![W](/assets/woodcuts/w.png){.plate}

![T](assets/fig/titled.png "A title")

![B](<assets/fig/with space.png>)

![E](assets/fig/with%20escape.png)

![R][ref]

![See [the docs](https://example.com)](assets/fig/nested.png)

![X](assets/fig/extensionless)

[ref]: assets/fig/referenced.png
"""

_PARITY_FILES = (
    "assets/figures/pipeline.png",
    "assets/fig/press.jpg",
    "assets/woodcuts/w.png",
    "assets/fig/titled.png",
    "assets/fig/with space.png",
    "assets/fig/with escape.png",
    "assets/fig/referenced.png",
    "assets/fig/nested.png",
    "assets/fig/extensionless.png",
)


def _resolves(path: Path) -> bool:
    """Whether lualatex would find ``path``: the file itself, or, for an
    extensionless src, a sibling with any image extension."""
    if path.is_file():
        return True
    return not path.suffix and any(p.is_file() for p in path.parent.glob(path.name + ".*"))


@_needs_pandoc
@pytest.mark.layer("integration")
def test_the_rewrite_lands_on_the_file_prepare_writes(tmp_path):
    # #272: the filter rewrites every assets/ src pandoc parses, so
    # print_safe.prepare must write every one of them -- a figure in
    # assets/figures/ as much as a plate in woodcuts/, however the markdown
    # spells the path. Run both over the same manuscript and every rewritten
    # src (from pandoc's AST, after the filter) must exist under
    # build/print-assets: the rewrite set is a subset of the copy set.
    from urllib.parse import unquote

    from PIL import Image

    from press import print_safe

    for rel in _PARITY_FILES:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (20, 20), (0, 0, 0)).save(target)
    chapter = tmp_path / "book" / "chapters" / "01-one.md"
    chapter.parent.mkdir(parents=True)
    chapter.write_text(_PARITY_CHAPTER, encoding="utf-8")

    print_safe.prepare(tmp_path)

    rewritten = _rewritten_srcs(chapter)
    assert len(rewritten) == len(_PARITY_FILES), rewritten
    assert all(src.startswith("build/print-assets/assets/") for src in rewritten), rewritten
    # pandoc's LaTeX writer unescapes a non-URI src before \includegraphics.
    missing = [src for src in rewritten if not _resolves(tmp_path / unquote(src))]
    assert not missing, f"rewritten by the filter, never written by prepare: {missing}"
