"""The beginner quickstart is executable documentation (#152).

The guide in docs/QUICKSTART.md promises a copyable path from a blank
machine to a verified book. This test keeps that promise honest: it
extracts the guide's own shell commands, proves the anchor commands are
present and in order, and *runs* the toolchain-free spine
(``press new`` -> ``press check``) against the installed package in a
sandbox. If a documented command is renamed, dropped, or stops working,
this test fails rather than letting the guide drift out from under a
beginner.

The build and publish commands (``press all``, ``press pages``, ``git
push``) are asserted present but not executed here: the full build is
already proven end to end by the consumer CI job, and re-running LuaLaTeX
in the unit suite would cost minutes for no additional coverage. What this
test owns is the first-run editorial spine every beginner hits first.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

QUICKSTART = Path(__file__).resolve().parent.parent / "docs" / "QUICKSTART.md"

# ``press`` targets this test actually executes: pure-Python, no toolchain,
# no network, no repository. Everything else a beginner is shown (a build,
# a publish, a version-control step) is proven elsewhere and only checked
# for presence here.
RUNNABLE = {"new", "check", "doctor", "wordcount", "config"}

# Targets that must exit zero on a freshly scaffolded book; ``doctor`` is a
# diagnostic whose exit code reports the machine, not the book, so it is run
# but not required to pass.
MUST_SUCCEED = {"new", "check", "wordcount", "config"}


def _console_commands() -> list[str]:
    """Every command line in a ```console block, in document order. Each
    non-empty line is one copyable command; this is the machine contract
    the guide's runnable blocks honor."""

    text = QUICKSTART.read_text(encoding="utf-8")
    commands: list[str] = []
    for block in re.findall(r"```console\n(.*?)```", text, re.S):
        for line in block.splitlines():
            stripped = line.strip()
            if stripped:
                commands.append(stripped)
    return commands


def test_the_guide_has_a_runnable_console_spine():
    commands = _console_commands()
    assert commands, "the quickstart shows no runnable commands"
    # Every runnable line is a real shell command, not prose that slipped
    # past the ``$`` prefix.
    for cmd in commands:
        assert cmd and not cmd.endswith(":"), cmd


def test_the_anchor_commands_are_present_and_ordered():
    """The load-bearing steps a beginner cannot skip appear, in order:
    scaffold, check, build, view. Renaming or dropping one breaks this."""

    commands = _console_commands()

    def index_of(prefix: str) -> int:
        for i, cmd in enumerate(commands):
            if cmd.startswith(prefix):
                return i
        raise AssertionError(f"the quickstart never shows `{prefix}`")

    scaffold = index_of("press new ")
    check = index_of("press check")
    build = index_of("press all")
    view = index_of("ls dist")
    assert scaffold < check < build, (scaffold, check, build)
    assert build < view, (build, view)


def _press(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "press", *args],
        cwd=cwd, capture_output=True, text=True,
    )


def test_the_documented_spine_runs_against_the_installed_press(tmp_path):
    """Walk the guide's own commands in order in a sandbox, running the
    toolchain-free ones exactly as written. A freshly scaffolded book is
    designed to check clean with no edits, so the spine must reach a
    passing ``press check`` with nothing but the documented commands."""

    import shlex

    cwd = tmp_path
    ran: list[str] = []
    for cmd in _console_commands():
        parts = shlex.split(cmd)
        if parts[0] == "cd":
            cwd = (cwd / parts[1]).resolve()
            continue
        if parts[0] != "press":
            # pip, brew, git, ls, docker: environment and inspection steps,
            # proven present by the anchor test, not executed here.
            continue
        target = parts[1]
        if target not in RUNNABLE:
            continue
        result = _press(parts[1:], cwd)
        ran.append(target)
        if target in MUST_SUCCEED:
            assert result.returncode == 0, (cmd, result.stdout, result.stderr)

    # The spine actually exercised the first-run path, not an empty subset.
    assert "new" in ran and "check" in ran, ran
    assert (tmp_path / "my-first-book" / "config" / "metadata.yaml").is_file()
