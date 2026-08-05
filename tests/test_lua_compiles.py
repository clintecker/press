"""The Lua filters must at least parse.

Six Lua filters run inside pandoc's bundled Lua 5.4 and shape every edition.
pandoc loads a filter before it renders, so a syntax slip -- a stray non-ASCII
byte in a comment, an unclosed string, a typo'd `end` -- otherwise surfaces only
when pandoc or LuaLaTeX chokes mid-build. This compiles each filter with
pandoc's own interpreter (`pandoc lua`, no extra install) and asserts it loads.

The Lua-quality M1 syntax gate (docs/LUA-QUALITY-PLAN.md §1). Skipped only where
pandoc is genuinely absent; under the toolchain image (PRESS_TOOLCHAIN) a missing
pandoc is a hard failure, never a silent skip where a release is cut (§7).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from press import adapters

LUA_DIR = Path(__file__).resolve().parent.parent / "src" / "press" / "data" / "lua"
FILTERS = sorted(LUA_DIR.glob("*.lua"))

_needs_pandoc = pytest.mark.skipif(
    shutil.which("pandoc") is None and not adapters.environment.get("PRESS_TOOLCHAIN"),
    reason="requires capability: pandoc",
)


def test_lua_filters_are_found():
    # A broken glob would leave the parametrized gate silently empty; the six
    # filters shape every edition, so the floor is a real guard, not decoration.
    assert len(FILTERS) >= 6, f"expected the six Lua filters, found {[p.name for p in FILTERS]}"


@_needs_pandoc
@pytest.mark.parametrize("lua", FILTERS, ids=lambda p: p.name)
def test_lua_filter_compiles(lua: Path):
    # loadfile COMPILES without running, so a filter's top-level `require` (of a
    # sibling module, resolvable only when pandoc runs the filter) is not
    # executed here. The path goes through the environment, not a positional
    # arg: `pandoc lua -e CODE -- FILE` would run CODE and then execute FILE.
    result = subprocess.run(
        ["pandoc", "lua", "-e", 'assert(loadfile(os.getenv("LUA_SYNTAX_FILE")))'],
        env={**os.environ, "LUA_SYNTAX_FILE": str(lua)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"{lua.name} failed to load:\n{result.stderr}"
