"""Create a clean, deterministic-ish source archive of the book repository."""

from __future__ import annotations

import os
import zipfile

from . import booklib

EXCLUDE_PARTS = {"build", "dist", ".git", "__pycache__"}


def main() -> int:
    root = booklib.root()
    out = root / "dist" / f"{booklib.slug()}-source.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if not path.is_file() or any(part in EXCLUDE_PARTS for part in relative.parts):
                continue
            info = zipfile.ZipInfo(str(booklib.slug() + "/" + str(relative)))
            info.date_time = (2026, 7, 16, 12, 0, 0)
            info.external_attr = (0o755 if os.access(path, os.X_OK) else 0o644) << 16
            archive.writestr(info, path.read_bytes())
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
