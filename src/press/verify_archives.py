"""Verify the archives and companions press all emits.

The reader zip, the source zip, and the sources companion were built
and published but never verified: a reader zip could disagree with the
verified reader directory, a source zip could carry an escaping path,
and the companion could be an empty file with a good name. Each is now
held to its contract, and extraction-style checks never trust a member
name that would land outside its prefix.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from . import booklib


def member_safe(name: str, prefix: str) -> bool:
    if name.startswith("/") or ".." in Path(name).parts:
        return False
    return name == prefix or name.startswith(prefix + "/") or prefix == ""


def verify_site_zip(archive_path: Path, site_dir: Path) -> list[str]:
    """The boxed reader must be exactly the verified reader directory."""

    failures: list[str] = []
    expected = {
        str(p.relative_to(site_dir.parent)): p.stat().st_size
        for p in sorted(site_dir.rglob("*")) if p.is_file()
    }
    with zipfile.ZipFile(archive_path) as archive:
        members = {i.filename: i.file_size for i in archive.infolist()
                   if not i.is_dir()}
    for name in members:
        if not member_safe(name, "site"):
            failures.append(f"site zip member escapes its prefix: {name}")
    missing = sorted(set(expected) - set(members))
    surplus = sorted(set(members) - set(expected))
    if missing:
        failures.append(f"site zip is missing {len(missing)} reader files "
                        f"(first: {missing[0]})")
    if surplus:
        failures.append(f"site zip carries {len(surplus)} files the reader "
                        f"does not (first: {surplus[0]})")
    mismatched = [n for n in expected.keys() & members.keys()
                  if expected[n] != members[n]]
    if mismatched:
        failures.append(f"site zip disagrees with the reader on "
                        f"{len(mismatched)} files (first: {sorted(mismatched)[0]})")
    return failures


def verify_source_zip(archive_path: Path, slug: str) -> list[str]:
    """Every member beneath the slug prefix, deflated, and policy-clean."""

    from .package_source import JUNK_PATTERNS, SECRET_PATTERNS
    import fnmatch

    failures: list[str] = []
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            if not member_safe(info.filename, slug):
                failures.append(f"source zip member escapes its prefix: {info.filename}")
            if info.compress_type != zipfile.ZIP_DEFLATED:
                failures.append(f"source zip member not deflated: {info.filename}")
            base = Path(info.filename).name
            for pattern in SECRET_PATTERNS + JUNK_PATTERNS:
                if fnmatch.fnmatch(base, pattern):
                    failures.append(
                        f"source zip carries a policy-refused file: {info.filename}"
                    )
    return failures


def verify_sources_companion(path: Path, title: str) -> list[str]:
    failures: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    if title not in text:
        failures.append(f"sources companion does not name the book: {title}")
    entries = text.count("\n- ") + text.count("\n1. ") + text.count("] ")
    if len(text.strip()) < 200 or entries == 0:
        failures.append("sources companion looks empty of entries")
    return failures


def main() -> int:
    root = booklib.root()
    book = booklib.book()
    dist = root / "dist"
    failures: list[str] = []
    verified: list[str] = []

    site_zip = dist / f"{book.slug}-site.zip"
    if not site_zip.is_file() or not (dist / "site").is_dir():
        failures.append("reader zip or reader directory missing")
    else:
        failures += verify_site_zip(site_zip, dist / "site")
        verified.append(site_zip.name)

    source_zip = dist / f"{book.slug}-source.zip"
    if not source_zip.is_file():
        failures.append("source zip missing")
    else:
        failures += verify_source_zip(source_zip, book.slug)
        verified.append(source_zip.name)

    if (root / "config" / "authorities.yaml").is_file():
        companion = dist / f"{book.slug}-sources.md"
        if not companion.is_file():
            failures.append("authorities configured but sources companion missing")
        else:
            failures += verify_sources_companion(companion, book.title)
            verified.append(companion.name)

    if failures:
        print("Archive verification failed:")
        for line in failures:
            print(f"  - {line}")
        return 1
    print(f"Verified archives: {', '.join(verified)}")
    return 0
