"""Scaffold a new book repository from the press template.

Template files that must start with a dot are stored with a dot- prefix
(package-data globbing skips dotfiles) and renamed on copy.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from . import booklib, instruments, version

TEMPLATE = booklib.DATA / "template"
TEMPLATE_MARKER = "{{SLUG}}"


def stamp_workflows(destination: Path) -> None:
    """Copy packaged workflows into .claude/workflows/, stamped with the
    press version so a book can see when its pinned copies drift."""

    target = destination / ".claude" / "workflows"
    target.mkdir(parents=True, exist_ok=True)
    stamp = f"// scaffolded by press {version()}; source of truth: press data/workflows\n"
    for name, path in instruments.workflow_paths().items():
        (target / f"{name}.js").write_text(
            stamp + path.read_text(encoding="utf-8"), encoding="utf-8"
        )


def main(args: list[str]) -> int:
    if len(args) != 1:
        print("usage: press new <directory>  (directory name becomes the slug)")
        return 2
    destination = Path(args[0]).resolve()
    if destination.exists():
        raise SystemExit(f"refusing to scaffold into existing path: {destination}")
    shutil.copytree(TEMPLATE, destination)
    for path in sorted(destination.rglob("dot-*"), reverse=True):
        path.rename(path.with_name("." + path.name[len("dot-") :]))
    stamp_workflows(destination)
    slug = destination.name
    for path in destination.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if TEMPLATE_MARKER in text:
                path.write_text(text.replace(TEMPLATE_MARKER, slug), encoding="utf-8")
    print(f"scaffolded {slug} -> {destination}")
    print("next: edit config/metadata.yaml, write book/chapters/, run `press all`")
    return 0
