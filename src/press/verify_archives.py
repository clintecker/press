"""Verify the archives and companions press all emits.

The reader zip, the source zip, and the sources companion were built
and published but never verified: a reader zip could disagree with the
verified reader directory, a source zip could carry an escaping path,
and the companion could be an empty file with a good name. Each is now
held to its contract byte for byte: the reader zip must digest-match
the verified reader directory, the source zip must contain exactly
what the publication policy admits (the same function the packager
ran) with matching digests, and extraction-style checks never trust a
member name that would land outside its prefix.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from . import booklib


def member_safe(name: str, prefix: str) -> bool:
    if name.startswith("/") or ".." in Path(name).parts:
        return False
    return name == prefix or name.startswith(prefix + "/") or prefix == ""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_site_zip(archive_path: Path, site_dir: Path) -> list[str]:
    """The boxed reader must be exactly the verified reader directory,
    proven by digest, not by name and size: a flipped byte in a member
    is a different book."""

    failures: list[str] = []
    expected = {
        str(p.relative_to(site_dir.parent)): _digest(p.read_bytes())
        for p in sorted(site_dir.rglob("*")) if p.is_file()
    }
    with zipfile.ZipFile(archive_path) as archive:
        members = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            if not member_safe(info.filename, "site"):
                failures.append(f"site zip member escapes its prefix: {info.filename}")
                continue
            members[info.filename] = _digest(archive.read(info.filename))
    missing = sorted(set(expected) - set(members))
    surplus = sorted(set(members) - set(expected))
    if missing:
        failures.append(f"site zip is missing {len(missing)} reader files "
                        f"(first: {missing[0]})")
    if surplus:
        failures.append(f"site zip carries {len(surplus)} files the reader "
                        f"does not (first: {surplus[0]})")
    mismatched = sorted(n for n in expected.keys() & members.keys()
                        if expected[n] != members[n])
    if mismatched:
        failures.append(f"site zip bytes disagree with the reader on "
                        f"{len(mismatched)} files (first: {mismatched[0]})")
    return failures


def verify_source_zip(archive_path: Path, slug: str) -> list[str]:
    """Exactly the members the publication policy admits, digest for
    digest. The expectation is recomputed from the same
    publication_members() the packager ran, so an appended member, a
    missing member, or altered bytes each fail by name."""

    from .package_source import publication_members

    failures: list[str] = []
    root = booklib.root()
    expected = {
        f"{slug}/{relative}": _digest(path.read_bytes())
        for path, relative in publication_members(root)[0]
    }
    members: dict[str, str] = {}
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            if not member_safe(info.filename, slug):
                failures.append(f"source zip member escapes its prefix: {info.filename}")
                continue
            if info.compress_type != zipfile.ZIP_DEFLATED:
                failures.append(f"source zip member not deflated: {info.filename}")
            members[info.filename] = _digest(archive.read(info.filename))
    missing = sorted(set(expected) - set(members))
    surplus = sorted(set(members) - set(expected))
    if missing:
        failures.append(f"source zip is missing {len(missing)} files the "
                        f"policy admits (first: {missing[0]})")
    if surplus:
        failures.append(f"source zip carries {len(surplus)} files the "
                        f"policy did not admit (first: {surplus[0]})")
    mismatched = sorted(n for n in expected.keys() & members.keys()
                        if expected[n] != members[n])
    if mismatched:
        failures.append(f"source zip bytes disagree with the repository on "
                        f"{len(mismatched)} files (first: {mismatched[0]})")
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
