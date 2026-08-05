"""The pure Lua helpers (press-util.lua) under unit test.

The filters mix pure computation -- the figure measure vocabulary, width_opt,
the is_true predicate -- with pandoc-AST manipulation. The pure half now lives
in a require-able press-util.lua and is tested here under pandoc's Lua 5.4 with
no render: fast, deterministic, and independent of the AST paths (which stay
integration-tested through pandoc). docs/LUA-QUALITY-PLAN.md §4.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from press import adapters

LUA_DIR = Path(__file__).resolve().parent.parent / "src" / "press" / "data" / "lua"
SCRIPT = Path(__file__).resolve().parent / "lua" / "test_press_util.lua"

_needs_pandoc = pytest.mark.skipif(
    shutil.which("pandoc") is None and not adapters.environment.get("PRESS_TOOLCHAIN"),
    reason="requires capability: pandoc",
)


@_needs_pandoc
@pytest.mark.layer("unit")
def test_press_util_pure_helpers():
    result = subprocess.run(
        ["pandoc", "lua", str(SCRIPT)],
        env={**os.environ, "PRESS_LUA_DIR": str(LUA_DIR)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "all assertions passed" in result.stdout
