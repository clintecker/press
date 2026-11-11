"""The Lua coverage ratchet: eligible lines, hit counting, floors that only rise."""

import importlib.util
from pathlib import Path

import pytest

from press import yamlio

spec = importlib.util.spec_from_file_location(
    "lua_coverage_ratchet",
    Path(__file__).resolve().parents[1] / "scripts" / "lua_coverage_ratchet.py",
)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def _baseline(tmp_path, floors):
    path = tmp_path / "baseline.yaml"
    yamlio.write(
        path,
        {
            "version": 1,
            "environment": "ci",
            "tool": "lua-line-hook",
            "floors": floors,
            "reasons": ["seed"],
        },
    )
    return path


def _two_filters(tmp_path):
    """f.lua has 4 eligible lines (2 hit = 50%); g.lua has 2 (none hit)."""
    lua = tmp_path / "lua"
    lua.mkdir()
    (lua / "f.lua").write_text("a()\nb()\nc()\nd()\n")
    (lua / "g.lua").write_text("a()\nb()\n")
    cov = tmp_path / "cov"
    cov.mkdir()
    (cov / "hits-1.tsv").write_text("f.lua\t1\nf.lua\t2\n")
    return lua, cov


def test_eligible_lines_skips_blank_comment_and_closers():
    src = "-- c\nlocal x = 1\n\nif x then\n  y()\nend\n"
    assert r.eligible_lines(src) == {2, 4, 5}


def test_eligible_lines_skips_every_closer_form_and_long_comments():
    src = "--[[ a\nb\n]]\nx()\n  end)\nend,\n},\nend end\n)\nelse\n}\n--[==[\nz\n]==]\ny()\n})\n}),\n"
    assert r.eligible_lines(src) == {4, 15}


def test_report_counts_only_eligible_hits(tmp_path):
    (tmp_path / "f.lua").write_text("local a = 1\n-- c\nlocal b = 2\n")
    (tmp_path / "hits-1.tsv").write_text("f.lua\t1\nf.lua\t2\n")  # 2 is a comment
    assert r.report(tmp_path, tmp_path) == {"f.lua": (1, 2)}


def test_report_reports_unhit_filter_as_zero(tmp_path):
    lua, cov = _two_filters(tmp_path)
    assert r.report(cov, lua) == {"f.lua": (2, 4), "g.lua": (0, 2)}


def test_check_fails_below_floor_and_on_zero_hits(tmp_path, capsys):
    lua, cov = _two_filters(tmp_path)
    base = _baseline(tmp_path, {"f.lua": 60.0, "g.lua": 10.0})
    code = r.main(["check", "--cov-dir", str(cov), "--lua-dir", str(lua), "--baseline", str(base)])
    out = capsys.readouterr().out
    assert code == 1
    assert "f.lua: got 50.0% floor 60.0%" in out
    assert "g.lua: got 0.0% floor 10.0%" in out


def test_check_passes_at_or_above_floor(tmp_path, capsys):
    lua, cov = _two_filters(tmp_path)
    base = _baseline(tmp_path, {"f.lua": 50.0, "g.lua": 0.0})
    (cov / "hits-2.tsv").write_text("g.lua\t1\n")
    code = r.main(["check", "--cov-dir", str(cov), "--lua-dir", str(lua), "--baseline", str(base)])
    assert code == 0
    assert "lua coverage: 2 filter(s) at or above floor" in capsys.readouterr().out


def test_check_fails_when_the_harness_was_not_switched_on(tmp_path, capsys):
    lua, cov = _two_filters(tmp_path)
    (cov / "hits-1.tsv").unlink()
    base = _baseline(tmp_path, {"f.lua": 0.0})
    code = r.main(["check", "--cov-dir", str(cov), "--lua-dir", str(lua), "--baseline", str(base)])
    assert code == 1
    assert "PRESS_LUA_COV_DIR" in capsys.readouterr().out


def test_update_never_lowers_a_floor_and_records_the_reason(tmp_path):
    lua, cov = _two_filters(tmp_path)
    base = _baseline(tmp_path, {"f.lua": 60.0, "g.lua": 0.0})
    argv = ["--lua-dir", str(lua), "--baseline", str(base), "--reason", "why"]
    assert r.main(["update", "--cov-dir", str(cov), *argv]) == 0
    data = yamlio.load(base)
    assert data["floors"] == {"f.lua": 60.0, "g.lua": 0.0}
    assert data["reasons"] == ["seed", "why"]


def test_update_raises_a_floor_to_the_measurement(tmp_path):
    lua, cov = _two_filters(tmp_path)
    base = _baseline(tmp_path, {"f.lua": 10.0})
    argv = ["--lua-dir", str(lua), "--baseline", str(base), "--reason", "up"]
    assert r.main(["update", "--cov-dir", str(cov), *argv]) == 0
    assert yamlio.load(base)["floors"] == {"f.lua": 50.0, "g.lua": 0.0}


def test_update_from_report_reproduces_the_measured_floors(tmp_path, capsys):
    lua, cov = _two_filters(tmp_path)
    assert r.main(["report", "--cov-dir", str(cov), "--lua-dir", str(lua)]) == 0
    text = capsys.readouterr().out
    assert "f.lua: 3-4" in text and "g.lua: 1-2" in text
    saved = tmp_path / "report.txt"
    saved.write_text(text)
    base = _baseline(tmp_path, {})
    argv = ["--baseline", str(base), "--reason", "from ci"]
    assert r.main(["update", "--from-report", str(saved), *argv]) == 0
    assert yamlio.load(base)["floors"] == {"f.lua": 50.0, "g.lua": 0.0}


def test_update_requires_exactly_one_source(tmp_path):
    base = _baseline(tmp_path, {})
    with pytest.raises(SystemExit):
        r.main(["update", "--baseline", str(base), "--reason", "x"])


def test_update_keeps_the_baseline_header_comment(tmp_path):
    lua, cov = _two_filters(tmp_path)
    base = _baseline(tmp_path, {})
    base.write_text("# house header\n" + base.read_text())
    argv = ["--lua-dir", str(lua), "--baseline", str(base), "--reason", "r"]
    assert r.main(["update", "--cov-dir", str(cov), *argv]) == 0
    assert base.read_text().startswith("# house header\n")


def test_check_fails_for_a_filter_with_no_floor(tmp_path, capsys):
    lua, cov = _two_filters(tmp_path)
    (lua / "new.lua").write_text("a()\n")
    base = _baseline(tmp_path, {"f.lua": 0.0, "g.lua": 0.0})
    (cov / "hits-2.tsv").write_text("g.lua\t1\n")
    code = r.main(["check", "--cov-dir", str(cov), "--lua-dir", str(lua), "--baseline", str(base)])
    assert code == 1
    assert "new filter new.lua has no floor" in capsys.readouterr().out


def test_update_from_cov_dir_without_hits_refuses_and_writes_nothing(tmp_path, capsys):
    lua, cov = _two_filters(tmp_path)
    (cov / "hits-1.tsv").unlink()
    base = _baseline(tmp_path, {"f.lua": 5.0})
    before = base.read_text()
    argv = ["--lua-dir", str(lua), "--baseline", str(base), "--reason", "x"]
    assert r.main(["update", "--cov-dir", str(cov), *argv]) == 1
    assert "PRESS_LUA_COV_DIR" in capsys.readouterr().out
    assert base.read_text() == before
