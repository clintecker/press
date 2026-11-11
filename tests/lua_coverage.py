"""Opt-in line coverage for the pandoc Lua filters (test infra, not shipped).

The filter tests build their ``--lua-filter`` argument with :func:`filter_arg`.
With ``PRESS_LUA_COV_DIR`` unset it is the plain filter, so nothing changes.
With it set, the argument names a generated shim in that directory: the shim is
``tests/lua/coverage-hook.lua`` with its config line inlined; it traces every
executed line under the filter's directory with ``debug.sethook``, runs the real
filter, and appends ``file<TAB>line`` rows to a fresh ``hits-*.tsv`` when the
document finishes. :func:`merge` folds every hits file into one map.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from press import adapters

ENV = "PRESS_LUA_COV_DIR"
HOOK = Path(__file__).resolve().parent / "lua" / "coverage-hook.lua"
# The hook's config line; the generator replaces its `...` with literals.
CONFIG_LINE = "local PRESS_LUA_DIR, PRESS_REAL_FILTER, PRESS_COV_DIR = ..."

_written: set[Path] = set()


def _lua_str(value: str) -> str:
    """A double-quoted Lua string literal for ``value``."""
    escaped = (
        value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
    )
    return f'"{escaped}"'


def _shim_source(filter_path: Path, cov_dir: Path) -> str:
    hook = HOOK.read_text(encoding="utf-8")
    if hook.count(CONFIG_LINE) != 1:
        raise RuntimeError(f"{HOOK} must contain its config line exactly once: {CONFIG_LINE!r}")
    values = (str(filter_path.parent) + os.sep, str(filter_path), str(cov_dir))
    config = CONFIG_LINE.replace("...", ", ".join(_lua_str(v) for v in values))
    return hook.replace(CONFIG_LINE, config)


def filter_arg(filter_path: Path) -> str:
    """The ``--lua-filter`` argument for ``filter_path``, traced when the env asks."""
    raw = os.environ.get(ENV)
    if not raw:
        return f"--lua-filter={filter_path}"
    cov_dir = Path(raw).resolve()
    real = filter_path.resolve()
    shim = cov_dir / f"shim-{real.stem}.lua"
    if shim not in _written or not shim.exists():
        cov_dir.mkdir(parents=True, exist_ok=True)
        # xdist workers share the directory: write aside and rename, so a
        # concurrent pandoc never reads a half-written shim.
        staging = shim.with_name(f".{shim.name}.{os.getpid()}")
        staging.write_text(_shim_source(real, cov_dir), encoding="utf-8")
        staging.replace(shim)
        _written.add(shim)
    return f"--lua-filter={shim}"


def merge(cov_dir: Path) -> dict[str, set[int]]:
    """Every ``hits-*.tsv`` in ``cov_dir`` merged to ``{filter filename: lines hit}``.

    An in-progress ``*.tsv.part`` file is never matched by the glob.
    """
    merged: dict[str, set[int]] = {}
    for hits in sorted(cov_dir.glob("hits-*.tsv")):
        for row in hits.read_text(encoding="utf-8").splitlines():
            fields = row.split("\t")
            # A malformed row (no tab, or a non-integer line) is skipped, not
            # fatal; the hook's write-then-rename means a finished run has none.
            if len(fields) != 2 or not fields[1].isdigit():
                continue
            merged.setdefault(fields[0], set()).add(int(fields[1]))
    return merged


REQUIRE_ENV = "PRESS_REQUIRE_LUA"


def pandoc_missing_and_optional() -> bool:
    """True when the Lua filter tests should skip: pandoc is absent and nothing
    says it must be there. ``PRESS_TOOLCHAIN`` (the toolchain image) or
    ``PRESS_REQUIRE_LUA`` (CI) turn the skip off, so a missing pandoc fails the
    tests loudly instead of letting the whole suite pass unrun."""
    return shutil.which("pandoc") is None and not (
        adapters.environment.get("PRESS_TOOLCHAIN") or adapters.environment.get(REQUIRE_ENV)
    )


needs_pandoc = pytest.mark.skipif(
    pandoc_missing_and_optional(), reason="requires capability: pandoc"
)
