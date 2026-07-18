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


def git_identity() -> str | None:
    import subprocess

    try:
        result = subprocess.run(
            ["git", "config", "user.name"], capture_output=True, text=True
        )
    except OSError:
        return None
    name = result.stdout.strip()
    return name or None


def main(args: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="press new",
        description="Scaffold a book; the directory name becomes the slug. "
        "Identity is never assumed: it comes from these flags, your git "
        "config, or neutral placeholders.",
    )
    parser.add_argument("directory")
    parser.add_argument("--author", default=None,
                        help="byline (default: git config user.name, else 'The Author')")
    parser.add_argument("--publisher", default=None,
                        help="imprint (default: the author, self-published)")
    parser.add_argument("--place", default="Earth",
                        help="imprint place for the colophon (default: Earth)")
    parser.add_argument("--owner", default=None,
                        help="GitHub owner for repository and Pages URLs; "
                        "omitted, those lines are left commented for later")
    parsed = parser.parse_args(args)

    destination = Path(parsed.directory).resolve()
    if destination.exists():
        raise SystemExit(f"refusing to scaffold into existing path: {destination}")
    # The directory name becomes the slug; a name that cannot be a slug
    # must fail before a single file is copied.
    booklib.validate_slug(destination.name)
    shutil.copytree(TEMPLATE, destination)
    for path in sorted(destination.rglob("dot-*"), reverse=True):
        path.rename(path.with_name("." + path.name[len("dot-") :]))
    stamp_workflows(destination)
    slug = destination.name
    author = parsed.author or git_identity() or "The Author"
    publisher = parsed.publisher or author
    if parsed.owner:
        repository_line = f'repository: "https://github.com/{parsed.owner}/{slug}"'
        site_url_line = f'site-url: "https://{parsed.owner}.github.io/{slug}"'
    else:
        repository_line = f'# repository: "https://github.com/OWNER/{slug}"'
        site_url_line = f'# site-url: "https://OWNER.github.io/{slug}"'
    markers = {
        TEMPLATE_MARKER: slug,
        "{{AUTHOR}}": author,
        "{{PUBLISHER}}": publisher,
        "{{PLACE}}": parsed.place,
        "{{REPOSITORY_LINE}}": repository_line,
        "{{SITE_URL_LINE}}": site_url_line,
    }
    for path in destination.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if any(marker in text for marker in markers):
                for marker, value in markers.items():
                    text = text.replace(marker, value)
                path.write_text(text, encoding="utf-8")
    print(f"scaffolded {slug} -> {destination}")
    print("next: edit config/metadata.yaml, write book/chapters/, run `press all`")
    return 0
