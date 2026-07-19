#!/usr/bin/env python3
"""Per-module branch-coverage ratchet.

Repository-wide coverage can stay green while one module's coverage
quietly rots. This ratchet holds each module to a per-module baseline:
a module may not drop below the branch coverage it had, so removing a
test that covered a decision branch turns the gate red even if the
total percentage barely moves.

The measurement is deterministic on purpose. It runs the fast test
subset, deselecting the toolchain-gated integration tests that run or
skip depending on the machine, so the same tests run everywhere and the
numbers do not swing with pandoc or LuaLaTeX being present. Toolchain-
heavy modules carry low baselines because their real coverage is the
integration layer, not the fast suite; the ratchet does not demand the
impossible of them, only that they not regress.

Usage:
  python3 scripts/coverage_ratchet.py            # check against the baseline
  python3 scripts/coverage_ratchet.py --update   # re-baseline to current
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "quality" / "coverage-baseline.json"
DESELECT = "not integration and not house_pdf and not distribution"

# The rendering toolchain whose presence swings fast-suite coverage of the
# environment-probing modules. measure() hides exactly these so the floor
# is reproducible whether or not the machine has them installed; every
# other executable stays visible so git and the interpreter still work.
HIDDEN_TOOLS = frozenset({
    "pandoc", "lualatex", "latexmk", "xelatex", "pdflatex", "tex", "luatex",
    "pdftoppm", "pdffonts", "pdfinfo", "pdftotext", "pdfimages",
    "epubcheck", "gs", "magick", "convert", "qpdf",
})


def _toolchain_hidden_path(shadow: Path) -> str:
    """Populate `shadow` with symlinks to every executable on the current
    PATH except the rendering toolchain, and return it as a one-entry
    PATH. First occurrence wins, mirroring normal PATH resolution, so the
    only behavioural change is that the hidden tools resolve to nothing."""

    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        try:
            entries = sorted(os.scandir(directory), key=lambda e: e.name)
        except OSError:
            continue
        for entry in entries:
            name = entry.name
            if name in HIDDEN_TOOLS:
                continue
            link = shadow / name
            if link.exists() or link.is_symlink():
                continue  # first-wins, like real PATH order
            try:
                link.symlink_to(entry.path)
            except OSError:
                pass
    return str(shadow)


def measure() -> dict[str, float]:
    cov_json = ROOT / "build" / "coverage.json"
    cov_json.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="press-cov-path-") as shadow:
        env = dict(os.environ)
        env["PATH"] = _toolchain_hidden_path(Path(shadow))
        subprocess.run(
            [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
             "-k", DESELECT, "--cov=press", "--cov-branch",
             f"--cov-report=json:{cov_json}"],
            cwd=ROOT, check=False, capture_output=True, env=env,
        )
    data = json.loads(cov_json.read_text(encoding="utf-8"))
    modules: dict[str, float] = {}
    for path, entry in data["files"].items():
        if not path.startswith("src/press/") or "/desk/" in path:
            continue
        stem = path[len("src/press/"):-3].replace("/", ".")
        modules[stem] = round(entry["summary"]["percent_covered"], 1)
    return modules


def compare(
    current: dict[str, float],
    expected: dict[str, float],
    tolerance: float,
) -> tuple[list[str], list[str]]:
    """Return (regressions, new_modules). A regression is a module whose
    current coverage fell more than `tolerance` below its baseline; a new
    module is one with no baseline yet. Pure, so a proof need not re-run
    the suite."""

    regressions = []
    new_modules = []
    for module, pct in sorted(current.items()):
        if module not in expected:
            new_modules.append(module)
        elif pct < expected[module] - tolerance:
            regressions.append(f"{module}: {pct:.1f}% < baseline {expected[module]:.1f}%")
    return regressions, new_modules


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    current = measure()

    if "--update" in args:
        existing = json.loads(BASELINE.read_text(encoding="utf-8"))
        existing["modules"] = dict(sorted(current.items()))
        BASELINE.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
        print(f"re-baselined {len(current)} modules")
        return 0

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    tolerance = float(baseline.get("tolerance", 1.5))
    regressions, new_modules = compare(current, baseline["modules"], tolerance)
    if new_modules:
        print("modules with no coverage baseline (run --update):")
        for m in new_modules:
            print(f"  - {m}")
    if regressions:
        print("branch coverage regressed below baseline:")
        for r in regressions:
            print(f"  - {r}")
    if regressions or new_modules:
        return 1
    print(f"coverage ratchet holds: {len(current)} modules at or above baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
