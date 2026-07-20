"""Create a clean, deterministic-ish source archive of the book repository.

The archive is published on the Pages site and attached to releases, so
its policy is a publication policy: publication is for committed work,
so inside a git repository the allowlist is git's tracked files; no
symlink is ever dereferenced (a link pointing outside the repository
must not leak outside bytes into a public artifact), secret-prone files
block the archive outright rather than shipping, junk files are skipped
with a note, and every member path is proven to stay beneath the
archive prefix. The run ends with an auditable summary of what was
included and what was not.

publication_members() is the one statement of the policy: the packager
writes exactly its answer and the archive verifier expects exactly its
answer, so an archive member the policy did not admit, or a member
whose bytes disagree with the repository, cannot pass verification.
"""

from __future__ import annotations

import fnmatch
import os
import subprocess
import zipfile
from pathlib import Path

from . import adapters
from . import booklib

EXCLUDE_PARTS = {"build", "dist", ".git", "__pycache__"}

# Files that end the run: publishing one of these is never intended.
SECRET_PATTERNS = [
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*",
    "id_ed25519*", ".netrc", "*.keychain", "credentials*", "*.secret",
]

# Files that are merely noise; skipped, and said so.
JUNK_PATTERNS = [".DS_Store", "Thumbs.db", "*.swp", "*~"]


def tracked_paths(root: Path) -> set[str] | None:
    """Relative paths git tracks, or None when the book is not a git
    repository (or git is absent), in which case the walk policy alone
    governs."""

    try:
        listing = adapters.process_runner.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return {name for name in listing.stdout.decode("utf-8").split("\0") if name}


def publication_members(root: Path) -> tuple[list[tuple[Path, str]], list[str]]:
    """Every file the publication policy admits, with the skip notes.

    The single statement of the source-publication policy; the packager
    and verify_archives.verify_source_zip both consume it.
    """

    resolved_root = root.resolve()
    tracked = tracked_paths(root)
    members: list[tuple[Path, str]] = []
    skipped: list[str] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in EXCLUDE_PARTS for part in relative.parts):
            continue
        if path.is_symlink():
            skipped.append(f"{relative} (symlink; never dereferenced)")
            continue
        if not path.is_file():
            continue
        name = path.name
        if any(fnmatch.fnmatch(name, pattern) for pattern in SECRET_PATTERNS):
            raise SystemExit(
                f"refusing to publish source: {relative} matches a "
                "secret pattern; remove it from the repository or the "
                "archive cannot be made"
            )
        if any(fnmatch.fnmatch(name, pattern) for pattern in JUNK_PATTERNS):
            skipped.append(f"{relative} (junk)")
            continue
        if tracked is not None and str(relative) not in tracked:
            skipped.append(f"{relative} (untracked; publication is for committed work)")
            continue
        if not path.resolve().is_relative_to(resolved_root):
            skipped.append(f"{relative} (resolves outside the repository)")
            continue
        members.append((path, str(relative)))
    return members, skipped


def main() -> int:
    root = booklib.root()
    out = root / "dist" / f"{booklib.slug()}-source.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    members, skipped = publication_members(root)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, relative in members:
            info = zipfile.ZipInfo(booklib.slug() + "/" + relative)
            info.date_time = (2026, 7, 16, 12, 0, 0)
            info.external_attr = (0o755 if os.access(path, os.X_OK) else 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    print(out)
    print(f"archived {len(members)} files; excluded dirs {sorted(EXCLUDE_PARTS)}")
    for note in skipped:
        print(f"  skipped {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
