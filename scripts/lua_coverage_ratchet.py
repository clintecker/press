#!/usr/bin/env python3
"""Lua filter coverage ratchet: per-filter line floors that only rise.

The Lua filter tests, run with PRESS_LUA_COV_DIR set, drop ``hits-*.tsv`` files
(rows ``<filter filename>\\t<line>``) into that directory. This script turns them
into a per-filter percentage of eligible lines and compares it to the committed
floors in ``.celebrimbor/baselines/lua-coverage.yaml``.

    lua_coverage_ratchet.py check  --cov-dir DIR
    lua_coverage_ratchet.py report --cov-dir DIR
    lua_coverage_ratchet.py update (--cov-dir DIR | --from-report FILE) --reason "..."

``report`` prints one ``name<TAB>hit<TAB>eligible<TAB>pct`` row per filter, a
blank line, then ``name: 12, 14-19`` uncovered lines; ``update --from-report``
reads that same text back, so a CI log excerpt can set the floors.

``check`` also fails for any ``*.lua`` filter that has no floor in the baseline:
a new filter must be given one with ``update``.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from press import yamlio

ROOT = Path(__file__).resolve().parents[1]
LUA_DIR = ROOT / "src" / "press" / "data" / "lua"
BASELINE = ROOT / ".celebrimbor" / "baselines" / "lua-coverage.yaml"
CLOSERS = {"end", "else", "}", ")", "end)", "end,", "},", "end end", "})", "}),"}
LONG_OPEN = re.compile(r"--\[(=*)\[")


def _long_close(line: str, level: str) -> bool:
    return f"]{level}]" in line


def eligible_lines(source: str) -> set[int]:
    """1-based lines that can execute: not blank, comment, or a lone closer.

    A ``--[[ ... ]]`` block is a comment for its whole span. Lines inside a
    multi-line string literal are not recognised (none exist in the filters).
    """
    out: set[int] = set()
    level: str | None = None  # the open long comment's ``=`` run, else None
    for n, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if level is not None:
            if _long_close(line, level):
                level = None
            continue
        opened = LONG_OPEN.match(line)
        if opened:
            if not _long_close(line[opened.end() :], opened.group(1)):
                level = opened.group(1)
            continue
        if line and not line.startswith("--") and line not in CLOSERS:
            out.add(n)
    return out


def read_hits(cov_dir: Path) -> dict[str, set[int]]:
    """Fold every ``hits-*.tsv`` under ``cov_dir`` into filename -> hit lines."""
    hits: dict[str, set[int]] = {}
    for path in sorted(cov_dir.glob("hits-*.tsv")):
        for row in path.read_text(encoding="utf-8").splitlines():
            if row.strip():
                name, line = row.split("\t")
                hits.setdefault(name, set()).add(int(line))
    return hits


def _measure(cov_dir: Path, lua_dir: Path) -> dict[str, tuple[set[int], set[int]]]:
    hits = read_hits(cov_dir)
    out = {}
    for path in sorted(lua_dir.glob("*.lua")):
        eligible = eligible_lines(path.read_text(encoding="utf-8"))
        out[path.name] = (hits.get(path.name, set()) & eligible, eligible)
    return out


def report(cov_dir: Path, lua_dir: Path) -> dict[str, tuple[int, int]]:
    """Per filter filename: (eligible lines hit, eligible lines)."""
    return {k: (len(h), len(e)) for k, (h, e) in _measure(cov_dir, lua_dir).items()}


def pct(hit: int, eligible: int) -> float:
    return round(100.0 * hit / eligible, 1) if eligible else 100.0


def _ranges(lines: list[int]) -> str:
    runs: list[list[int]] = []
    for n in lines:
        if runs and n == runs[-1][1] + 1:
            runs[-1][1] = n
        else:
            runs.append([n, n])
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in runs)


def render_report(measured: dict[str, tuple[set[int], set[int]]]) -> str:
    rows = [f"{k}\t{len(h)}\t{len(e)}\t{pct(len(h), len(e))}" for k, (h, e) in measured.items()]
    gaps = [f"{k}: {_ranges(sorted(e - h))}" for k, (h, e) in measured.items() if e - h]
    return "\n".join([*rows, "", *gaps]) + "\n"


def parse_report(text: str) -> dict[str, float]:
    """The floors in ``report`` output: the tab rows before the first blank line."""
    floors: dict[str, float] = {}
    for line in text.splitlines():
        if not line.strip():
            break
        name, _hit, _eligible, value = line.split("\t")
        floors[name] = float(value)
    return floors


def failures(counts: dict[str, tuple[int, int]], floors: dict[str, float]) -> list[str]:
    bad = []
    for name, floor in floors.items():
        hit, eligible = counts.get(name, (0, 0))
        got = pct(hit, eligible)
        if hit == 0 or got < floor:
            bad.append(f"{name}: got {got}% floor {floor}%")
    return bad


def _no_hits(cov_dir: Path) -> bool:
    if list(cov_dir.glob("hits-*.tsv")):
        return False
    print(f"lua coverage: no hits files in {cov_dir}; was PRESS_LUA_COV_DIR set?")
    return True


def new_filters(lua_dir: Path, floors: dict[str, float]) -> list[str]:
    return [
        f'new filter {p.name} has no floor: run scripts/lua_coverage_ratchet.py update '
        '--cov-dir DIR --reason "..."'
        for p in sorted(lua_dir.glob("*.lua"))
        if p.name not in floors
    ]


def cmd_check(args: argparse.Namespace) -> int:
    if _no_hits(args.cov_dir):
        return 1
    floors = yamlio.load(args.baseline)["floors"]
    bad = failures(report(args.cov_dir, args.lua_dir), floors)
    bad += new_filters(args.lua_dir, floors)
    if bad:
        print("\n".join(bad))
        return 1
    print(f"lua coverage: {len(floors)} filter(s) at or above floor")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    print(render_report(_measure(args.cov_dir, args.lua_dir)), end="")
    return 0


def _header(path: Path) -> str:
    """The baseline's leading comment block, which a YAML rewrite would drop."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    head = []
    for line in lines:
        if not line.startswith("#"):
            break
        head.append(line)
    return "".join(head)


def cmd_update(args: argparse.Namespace) -> int:
    if args.cov_dir and _no_hits(args.cov_dir):
        return 1
    if args.from_report:
        measured = parse_report(args.from_report.read_text(encoding="utf-8"))
    else:
        measured = {k: pct(*v) for k, v in report(args.cov_dir, args.lua_dir).items()}
    header = _header(args.baseline)
    data = yamlio.load(args.baseline)
    floors = data["floors"]
    for name, value in measured.items():
        floors[name] = max(float(floors.get(name, 0.0)), value)
    data["reasons"].append(args.reason)
    yamlio.write(args.baseline, data)
    args.baseline.write_text(header + args.baseline.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"lua coverage: floors updated for {len(measured)} filter(s)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, fn in (("check", cmd_check), ("report", cmd_report), ("update", cmd_update)):
        p = sub.add_parser(name)
        p.set_defaults(fn=fn)
        p.add_argument("--lua-dir", type=Path, default=LUA_DIR)
        p.add_argument("--baseline", type=Path, default=BASELINE)
        if name == "update":
            p.add_argument("--reason", required=True)
            src = p.add_mutually_exclusive_group(required=True)
            src.add_argument("--cov-dir", type=Path)
            src.add_argument("--from-report", type=Path)
        else:
            p.add_argument("--cov-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())
