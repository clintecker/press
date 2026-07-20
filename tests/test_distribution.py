"""The built distributions are clean and reproducible in membership.

A wheel or sdist whose contents depend on whether the packaged scripts
were run locally, or on the interpreter version that ran them, is not a
distribution anyone can trust. These tests build both artifacts and
prove no bytecode or cache leaks in, that a build after running the
scripts yields the same logical member set, and that the build emits no
warnings.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JUNK_MARKERS = ("__pycache__", ".pyc", ".pyo", ".DS_Store", ".swp")


def _build(outdir: Path) -> tuple[str, list[str]]:
    result = subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(outdir)],
        cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise AssertionError(f"build failed:\n{result.stdout}\n{result.stderr}")
    return result.stdout + result.stderr, _members(outdir)


def _members(outdir: Path) -> list[str]:
    names: list[str] = []
    for whl in outdir.glob("*.whl"):
        names += zipfile.ZipFile(whl).namelist()
    for sdist in outdir.glob("*.tar.gz"):
        names += tarfile.open(sdist).getnames()
    return names


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("build") is None,
    reason="requires capability: build (pip install '.[dev]')",
)


@pytest.mark.invariant("INV-docs-no-drift")
@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_distributions_carry_no_bytecode(tmp_path):
    # Run a packaged script so its __pycache__ exists, exactly the state
    # the audit's dirty build was made from.
    script = ROOT / "src" / "press" / "data" / "skills" / "overused-jargon" / "scripts"
    import py_compile
    for py in script.glob("*.py"):
        py_compile.compile(str(py))
    try:
        _output, members = _build(tmp_path)
    finally:
        for cache in script.rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)
    bad = [m for m in members if any(marker in m for marker in JUNK_MARKERS)]
    assert not bad, f"distribution carries bytecode or cache: {bad}"


def test_build_is_warning_free(tmp_path):
    output, _ = _build(tmp_path)
    warnings = [line for line in output.splitlines()
                if line.lower().startswith("warning:")]
    assert not warnings, f"build emitted warnings (treated as failures): {warnings}"


def test_wheel_carries_the_provider_qualification_record(tmp_path):
    _output, members = _build(tmp_path)
    assert "press/data/providers.yaml" in members


def test_membership_is_stable_across_runs(tmp_path):
    """Two builds, one after running the scripts, produce the same
    logical member set (ignoring the dist filenames themselves)."""

    def logical(outdir: Path) -> set[str]:
        return {m for m in _members(outdir)
                if not any(marker in m for marker in JUNK_MARKERS)}

    first = tmp_path / "a"
    second = tmp_path / "b"
    _build(first)
    script = ROOT / "src" / "press" / "data" / "skills" / "overused-jargon" / "scripts"
    import py_compile
    for py in script.glob("*.py"):
        py_compile.compile(str(py))
    try:
        _build(second)
    finally:
        for cache in script.rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)
    assert logical(first) == logical(second)
