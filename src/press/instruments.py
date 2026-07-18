"""The packaged authoring instruments: skills and agent workflows.

The press ships its skills and workflows as package data so that no step
depends on a press checkout existing on disk. This module is the one
place that knows where they land after install; everything else (agents,
workflows, scaffolded books) asks `press skills` / `press workflows`
instead of guessing at paths.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import booklib, version

SKILLS = booklib.DATA / "skills"
WORKFLOWS = booklib.DATA / "workflows"
STAMP_PREFIX = "// scaffolded by press "


def skill_paths() -> dict[str, Path]:
    """Installed skills by name: flat .md files plus SKILL.md directories."""

    found: dict[str, Path] = {}
    for path in sorted(SKILLS.glob("*.md")):
        found[path.stem] = path
    for manifest in sorted(SKILLS.glob("*/SKILL.md")):
        found[manifest.parent.name] = manifest
    return found


def workflow_paths() -> dict[str, Path]:
    """Installed workflow scripts by name."""

    return {path.stem: path for path in sorted(WORKFLOWS.glob("*.js"))}


def workflow_usage(path: Path) -> str:
    """The whenToUse line from a workflow's meta block, if it states one."""

    match = re.search(
        r"whenToUse:\s*(['\"`])((?:\\.|(?!\1).)*)\1",
        path.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    return match.group(2) if match else ""


def book_root() -> Path | None:
    """The book repository this command runs inside, if it runs inside one."""

    try:
        return booklib.root()
    except SystemExit:
        return None


def stripped(text: str) -> str:
    return "".join(
        line for line in text.splitlines(keepends=True)
        if not line.startswith(STAMP_PREFIX)
    )


def list_skills() -> int:
    for name, path in skill_paths().items():
        print(f"{name}\t{path}")
    return 0


def list_workflows() -> int:
    """Print each workflow with a paste-ready invocation.

    Inside a book the invocation targets the book's pinned copy by name,
    with the real root filled in, and the pinned copy is diffed against
    the installed press so drift is a printed fact rather than a comment
    someone must remember to read.
    """

    root = book_root()
    for name, path in workflow_paths().items():
        print(name)
        usage = workflow_usage(path)
        if usage:
            print(f"  {usage}")
        pinned = (root / ".claude" / "workflows" / f"{name}.js") if root else None
        if pinned and pinned.is_file():
            drift = stripped(pinned.read_text(encoding="utf-8")) != path.read_text(encoding="utf-8")
            state = (
                f"DIFFERS from installed press {version()}"
                if drift
                else f"matches installed press {version()}"
            )
            print(f"  pinned: {pinned} ({state})")
            print(f'  invoke: Workflow({{name: "{name}", args: {{root: "{root}"}}}})')
        else:
            root_arg = str(root) if root else "<absolute book root>"
            print(f"  script: {path}")
            print(
                f'  invoke: Workflow({{scriptPath: "{path}", '
                f'args: {{root: "{root_arg}"}}}})'
            )
    return 0
