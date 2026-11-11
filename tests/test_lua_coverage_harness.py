"""The Lua filter coverage harness (tests/lua_coverage.py) is itself proven.

With PRESS_LUA_COV_DIR set, every filter render loads a generated shim that
traces executed lines with debug.sethook, runs the real filter, and appends
per-file hits to a fresh hits-*.tsv. These tests pin the passthrough, the hits,
the per-run uniqueness, the raising-filter case, the scoping to the filters
directory, the long-path case short_src would truncate, and that rendered
output is byte-identical with and without the harness.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from press import adapters
from tests import lua_coverage

LUA_DIR = Path(__file__).resolve().parent.parent / "src" / "press" / "data" / "lua"
SCENE_BREAK = LUA_DIR / "scene-break.lua"
SET_PIECES = LUA_DIR / "set-pieces.lua"
_DOC = "a\n\n* * *\n\nb\n"

_needs_pandoc = pytest.mark.skipif(
    shutil.which("pandoc") is None and not adapters.environment.get("PRESS_TOOLCHAIN"),
    reason="requires capability: pandoc",
)


def _pandoc(arg: str, doc: str = _DOC, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["pandoc", "-f", "markdown+fenced_divs", "-t", "html", arg],
        input=doc,
        check=check,
        capture_output=True,
        text=True,
    )


def _lines(path: Path) -> set[int]:
    return {int(row.split("\t")[1]) for row in path.read_text().splitlines() if row}


@pytest.mark.layer("unit")
def test_filter_arg_is_passthrough_without_env(monkeypatch, tmp_path):
    monkeypatch.delenv("PRESS_LUA_COV_DIR", raising=False)
    assert lua_coverage.filter_arg(Path("/x/f.lua")) == "--lua-filter=/x/f.lua"


@pytest.mark.layer("unit")
@_needs_pandoc
def test_shim_records_hits_for_a_real_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESS_LUA_COV_DIR", str(tmp_path))
    arg = lua_coverage.filter_arg(SCENE_BREAK)
    assert arg == f"--lua-filter={tmp_path / 'shim-scene-break.lua'}"
    _pandoc(arg)
    hits = lua_coverage.merge(tmp_path)
    assert "scene-break.lua" in hits and len(hits["scene-break.lua"]) > 5
    # Every recorded line exists in the real filter.
    assert max(hits["scene-break.lua"]) <= len(SCENE_BREAK.read_text().splitlines())


@pytest.mark.layer("unit")
@_needs_pandoc
def test_two_runs_write_two_files_and_merge(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESS_LUA_COV_DIR", str(tmp_path))
    arg = lua_coverage.filter_arg(SCENE_BREAK)
    _pandoc(arg, "a\n")  # the default "rule" ornament returns before the walk
    first = set(tmp_path.glob("hits-*.tsv"))
    _pandoc(arg, "---\nscene-break-ornament: asterism\n---\n\n" + _DOC)
    files = set(tmp_path.glob("hits-*.tsv"))
    assert len(files) == 2, files
    (only_first,) = first
    (only_second,) = files - first
    assert _lines(only_second) - _lines(only_first), "the asterism run reaches the walk"
    union = _lines(only_first) | _lines(only_second)
    assert lua_coverage.merge(tmp_path)["scene-break.lua"] == union


@pytest.mark.layer("unit")
@_needs_pandoc
def test_a_raising_filter_leaves_no_hits_file(tmp_path, monkeypatch):
    cov = tmp_path / "cov"
    cov.mkdir()
    bad = tmp_path / "bad.lua"
    bad.write_text("function Pandoc(doc) error('boom') end\n")
    monkeypatch.setenv("PRESS_LUA_COV_DIR", str(cov))
    result = _pandoc(lua_coverage.filter_arg(bad), check=False)
    assert result.returncode != 0
    assert "boom" in result.stderr
    assert not list(cov.glob("hits-*.tsv"))


@pytest.mark.layer("unit")
@_needs_pandoc
def test_hits_only_name_filters_under_the_lua_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESS_LUA_COV_DIR", str(tmp_path))
    # set-pieces requires press-util, so a sibling module is traced too.
    _pandoc(lua_coverage.filter_arg(SET_PIECES), "::: {.letter}\nDear sir.\n:::\n")
    hits = lua_coverage.merge(tmp_path)
    in_lua_dir = {p.name for p in LUA_DIR.glob("*.lua")}
    assert hits, "no hits recorded"
    assert set(hits) <= in_lua_dir, set(hits) - in_lua_dir
    assert {"set-pieces.lua", "press-util.lua"} <= set(hits)


@pytest.mark.layer("unit")
@_needs_pandoc
def test_the_shim_never_records_itself_even_beside_the_filter(tmp_path, monkeypatch):
    # PRESS_LUA_COV_DIR is the filter's own directory, so the shim lives under
    # the traced prefix; its lines must still never be hits.
    filt = tmp_path / "beside.lua"
    filt.write_text("function Str(el)\n  return el\nend\n")
    monkeypatch.setenv("PRESS_LUA_COV_DIR", str(tmp_path))
    _pandoc(lua_coverage.filter_arg(filt), "word\n")
    # Line 3 (`end`) is where Lua 5.4 binds the closure at chunk load.
    assert lua_coverage.merge(tmp_path) == {"beside.lua": {1, 2, 3}}


@pytest.mark.layer("unit")
@_needs_pandoc
def test_a_filter_under_a_long_path_is_still_traced(tmp_path, monkeypatch):
    # short_src truncates long chunk names to "...<tail>"; the hook must match
    # on the full source path, so a deep filters directory is still recorded.
    deep = tmp_path.joinpath(*(["a-rather-long-directory-name"] * 6))
    deep.mkdir(parents=True)
    assert len(str(deep)) > 120
    filt = deep / "long.lua"
    filt.write_text("function Str(el)\n  el.text = el.text\n  return el\nend\n")
    cov = tmp_path / "cov"
    cov.mkdir()
    monkeypatch.setenv("PRESS_LUA_COV_DIR", str(cov))
    _pandoc(lua_coverage.filter_arg(filt), "word\n")
    assert lua_coverage.merge(cov) == {"long.lua": {1, 2, 3, 4}}


@pytest.mark.layer("unit")
@_needs_pandoc
@pytest.mark.parametrize("filt", [SCENE_BREAK, SET_PIECES], ids=lambda p: p.name)
def test_output_is_byte_identical_with_and_without_the_harness(filt, tmp_path, monkeypatch):
    doc = "# Chapter\n\nA line.\n\n* * *\n\n::: {.letter}\nDear sir.\n:::\n"
    monkeypatch.delenv("PRESS_LUA_COV_DIR", raising=False)
    plain = _pandoc(lua_coverage.filter_arg(filt), doc)
    monkeypatch.setenv("PRESS_LUA_COV_DIR", str(tmp_path))
    traced = _pandoc(lua_coverage.filter_arg(filt), doc)
    assert traced.stdout == plain.stdout
    assert list(tmp_path.glob("hits-*.tsv"))


@pytest.mark.layer("unit")
@_needs_pandoc
def test_hits_are_renamed_into_place_and_part_files_are_ignored(tmp_path, monkeypatch):
    # A run killed mid-write leaves only a .part file; merge must never read it.
    (tmp_path / "hits-x.tsv.part").write_text("scene-break.lua\t99999\nscene-bre")
    monkeypatch.setenv("PRESS_LUA_COV_DIR", str(tmp_path))
    _pandoc(lua_coverage.filter_arg(SCENE_BREAK))
    assert [p.name for p in tmp_path.glob("*.part")] == ["hits-x.tsv.part"]
    assert len(list(tmp_path.glob("hits-*.tsv"))) == 1
    assert 99999 not in lua_coverage.merge(tmp_path)["scene-break.lua"]


@pytest.mark.layer("unit")
def test_merge_skips_malformed_rows(tmp_path):
    (tmp_path / "hits-a.tsv").write_text(
        "f.lua\t3\n\nf.lua\nf.lua\tx\nf.lua\t4\textra\ng.lua\t-1\nf.lua\t7\n"
    )
    assert lua_coverage.merge(tmp_path) == {"f.lua": {3, 7}}
