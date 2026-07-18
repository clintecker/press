"""Create a clean, deterministic-ish source archive of the book repository.

The archive is published on the Pages site and attached to releases, so
its policy is a publication policy: no symlink is ever dereferenced (a
link pointing outside the repository must not leak outside bytes into a
public artifact), secret-prone files block the archive outright rather
than shipping, junk files are skipped with a note, and every member
path is proven to stay beneath the archive prefix. The run ends with an
auditable summary of what was included and what was not.
"""

from __future__ import annotations

import fnmatch
import os
import zipfile

from . import booklib

EXCLUDE_PARTS = {"build", "dist", ".git", "__pycache__"}

# Files that end the run: publishing one of these is never intended.
SECRET_PATTERNS = [
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*",
    "id_ed25519*", ".netrc", "*.keychain", "credentials*", "*.secret",
]

# Files that are merely noise; skipped, and said so.
JUNK_PATTERNS = [".DS_Store", "Thumbs.db", "*.swp", "*~"]


def main() -> int:
    root = booklib.root()
    out = root / "dist" / f"{booklib.slug()}-source.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    resolved_root = root.resolve()
    included = 0
    skipped: list[str] = []
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
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
            if not path.resolve().is_relative_to(resolved_root):
                skipped.append(f"{relative} (resolves outside the repository)")
                continue
            info = zipfile.ZipInfo(str(booklib.slug() + "/" + str(relative)))
            info.date_time = (2026, 7, 16, 12, 0, 0)
            info.external_attr = (0o755 if os.access(path, os.X_OK) else 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
            included += 1
    print(out)
    print(f"archived {included} files; excluded dirs {sorted(EXCLUDE_PARTS)}")
    for note in skipped:
        print(f"  skipped {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
