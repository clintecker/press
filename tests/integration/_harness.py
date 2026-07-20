"""Shared machinery for the real-tool integration runners.

Each runner under ``tests/integration/`` builds one artifact family from
a source-only factory book, then inspects the output with its *real*
verifier -- the same pandoc, LuaLaTeX, Poppler, ZIP, and git the CLI
shells out to, no fake process and no mock. This module carries the
parts every runner shares:

  - capability detection (``shutil.which``) and the skip reason text, so
    a missing tool skips the runner (naming the toolchain capability the
    collection plugin demands) instead of being read as an artifact
    failure;
  - exact external-tool version capture, run once per tool;
  - a source-manifest digest of the input factory book and a content
    digest of every produced output;
  - the ``Evidence`` record each runner fills and writes as JSON under
    the test's temp directory, so a passing or failing run leaves a
    reviewable receipt (tool versions, input digest, output digests, and
    which verifiers and invariants executed).

This file is not a test module (``python_files = ["test_*.py"]``), so
pytest never collects it; the runners import from it.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# The runners build source-only books with the shared factory; put the
# suite's tests/ dir on the path the same way conftest/factories do.
_TESTS = Path(__file__).resolve().parent.parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from PIL import Image, ImageDraw  # noqa: E402  (needs the src path factories set up)

# The toolchain tools an integration runner may gate on. Every name here
# is a declared capability in press.pytest_invariants._CAPABILITIES, so a
# skip reason built from these satisfies the collection plugin.
PDF_TOOLCHAIN = (
    "pandoc", "lualatex", "latexmk",
    "pdfinfo", "pdffonts", "pdftotext", "pdftoppm",
)


def missing_tools(tools: tuple[str, ...]) -> list[str]:
    """The subset of *tools* absent from PATH."""

    return [tool for tool in tools if shutil.which(tool) is None]


def skip_reason(tools: tuple[str, ...]) -> str:
    """A skip reason naming every required capability, so the collection
    plugin can attribute the skip to a declared toolchain tool rather
    than an unexplained condition."""

    return (
        "integration runner needs these toolchain capabilities present: "
        + " ".join(tools)
    )


def tool_version(tool: str) -> str:
    """The exact version line the tool reports, or ``"absent"``.

    Poppler tools answer ``-v`` on stderr; pandoc, LuaLaTeX, latexmk, and
    git answer ``--version`` on stdout. Try the common flag first, then
    the poppler spelling, and take the first non-empty line. No network,
    no shell, no credentials -- just the tool naming itself.
    """

    if shutil.which(tool) is None:
        return "absent"
    for flag in ("--version", "-v"):
        try:
            result = subprocess.run(
                [tool, flag], capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        for stream in (result.stdout, result.stderr):
            for line in (stream or "").splitlines():
                if line.strip():
                    return line.strip()
    return "present (version unreported)"


def tool_versions(tools: tuple[str, ...]) -> dict[str, str]:
    """``{tool: version-line-or-'absent'}`` for every tool named."""

    return {tool: tool_version(tool) for tool in tools}


def file_digest(path: Path) -> str:
    """SHA-256 of a file's bytes."""

    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


_MANIFEST_SKIP = {"build", "dist", ".git", "__pycache__"}


def source_manifest_digest(root: Path) -> str:
    """A digest over the input book's source tree: every relative path
    and its bytes, sorted, with build/dist/.git excluded. Two identical
    source books hash the same; a changed source changes the digest."""

    hasher = hashlib.sha256()
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(part in _MANIFEST_SKIP for part in p.relative_to(root).parts)
    )
    for path in files:
        rel = path.relative_to(root).as_posix()
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return "sha256:" + hasher.hexdigest()


def digest_outputs(dist: Path, names: list[str]) -> dict[str, str]:
    """``{name: sha256}`` for each named output present under *dist*; a
    directory output records the digest of its file listing instead."""

    digests: dict[str, str] = {}
    for name in names:
        path = dist / name
        if path.is_file():
            digests[name] = file_digest(path)
        elif path.is_dir():
            listing = sorted(
                p.relative_to(path).as_posix()
                for p in path.rglob("*") if p.is_file()
            )
            hasher = hashlib.sha256("\n".join(listing).encode("utf-8"))
            digests[name + "/"] = "sha256-listing:" + hasher.hexdigest()
    return digests


def make_cover(path: Path) -> None:
    """A small varied JPEG cover: real ink with enough spread that the
    cover-wrap front-panel detector reads art, not a blank plate. Solid
    fills read as blank, so the plate carries a gradient and rules."""

    width, height = 1200, 1800
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    assert pixels is not None
    for y in range(height):
        for x in range(width):
            v = (x * 7 + y * 13) % 200 + 30
            pixels[x, y] = (v, (v * 2) % 220 + 20, (v + 80) % 200)
    draw = ImageDraw.Draw(image)
    draw.rectangle([100, 200, width - 100, height - 200], outline=(255, 255, 255), width=20)
    for i in range(0, height, 60):
        draw.line([(0, i), (width, i)], fill=(240, 240, 240), width=3)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=88)


@dataclass
class Evidence:
    """The per-runner receipt: what tools built and inspected the
    artifact, what went in, what came out, and which promises were
    exercised. Written as JSON so a CI run retains it beside the built
    artifacts under the pytest temp root."""

    family: str
    required_tools: tuple[str, ...]
    tool_versions: dict[str, str] = field(default_factory=dict)
    input_manifest_digest: str = ""
    outputs: dict[str, str] = field(default_factory=dict)
    invariants: list[str] = field(default_factory=list)
    verifiers: list[str] = field(default_factory=list)
    notes: dict[str, str] = field(default_factory=dict)

    def record_verifier(self, name: str) -> None:
        if name not in self.verifiers:
            self.verifiers.append(name)

    def record_invariant(self, inv_id: str) -> None:
        if inv_id not in self.invariants:
            self.invariants.append(inv_id)

    def write(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        out = directory / f"evidence-{self.family}.json"
        out.write_text(
            json.dumps(self.__dict__, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return out
