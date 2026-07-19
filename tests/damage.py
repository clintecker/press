"""Reusable, named artifact damage operators.

A verifier is only trustworthy if a single, named, single-purpose
mutation makes it fail with the diagnostic tied to the invariant that
mutation violates. Bespoke corruption in each test proves only that a
broken artifact is broken; these operators prove that the specific
failure class the verifier claims to enforce is enforced.

Every operator records the source digest, its stable mutation id, its
parameters, and the resulting digest, so a negative proof carries its
own provenance. Operators run against freshly built valid artifacts
(the factory and the real builders make them), never against
pre-broken golden files.

Each operator declares, via DAMAGE_INVARIANTS, the invariant id it
attacks and the substring the verifier must emit; test_damage.py drives
every operator and asserts exactly that diagnostic, and asserts the
undamaged artifact passes first.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DamageRecord:
    mutation_id: str
    params: dict[str, Any]
    source_digest: str
    result_digest: str = ""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---- zip archive operators (bytes in, bytes out) ----

def _rewrite_zip(data: bytes, transform) -> bytes:
    """Rebuild a zip after a transform((name, info, bytes)) -> list of
    (name, compress_type, external_attr, bytes) members. transform sees
    the full member list and returns the full replacement list."""

    members = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for info in archive.infolist():
            members.append((info, archive.read(info.filename)))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, compress, attr, body in transform(members):
            zi = zipfile.ZipInfo(name)
            zi.compress_type = compress
            zi.external_attr = attr
            archive.writestr(zi, body)
    return out.getvalue()


def add_member(data: bytes, prefix: str = "site", name: str = "intruder.txt") -> tuple[bytes, DamageRecord]:
    rec = DamageRecord("archive.add_member", {"name": name}, _digest(data))

    def t(members):
        rows = [(i.filename, i.compress_type, i.external_attr, b) for i, b in members]
        rows.append((f"{prefix}/{name}", zipfile.ZIP_DEFLATED, 0o644 << 16, b"not admitted"))
        return rows

    result = _rewrite_zip(data, t)
    rec.result_digest = _digest(result)
    return result, rec


def remove_member(data: bytes, which: int = 0) -> tuple[bytes, DamageRecord]:
    rec = DamageRecord("archive.remove_member", {"which": which}, _digest(data))

    def t(members):
        rows = [(i.filename, i.compress_type, i.external_attr, b) for i, b in members]
        del rows[which]
        return rows

    result = _rewrite_zip(data, t)
    rec.result_digest = _digest(result)
    return result, rec


def escaping_member(data: bytes, name: str = "../escape.txt") -> tuple[bytes, DamageRecord]:
    rec = DamageRecord("archive.escaping_path", {"name": name}, _digest(data))

    def t(members):
        rows = [(i.filename, i.compress_type, i.external_attr, b) for i, b in members]
        rows.append((name, zipfile.ZIP_DEFLATED, 0o644 << 16, b"x"))
        return rows

    result = _rewrite_zip(data, t)
    rec.result_digest = _digest(result)
    return result, rec


def store_uncompressed(data: bytes) -> tuple[bytes, DamageRecord]:
    rec = DamageRecord("archive.store_uncompressed", {}, _digest(data))

    def t(members):
        return [(i.filename, zipfile.ZIP_STORED, i.external_attr, b) for i, b in members]

    result = _rewrite_zip(data, t)
    rec.result_digest = _digest(result)
    return result, rec


def flip_member_byte(data: bytes) -> tuple[bytes, DamageRecord]:
    """Flip one byte of the first non-empty file member, preserving its
    length: a different book, same shape."""

    rec = DamageRecord("archive.flip_byte", {}, _digest(data))
    flipped = {"done": False}

    def t(members):
        rows = []
        for info, body in members:
            if not flipped["done"] and body and not info.filename.endswith("/"):
                body = bytes([body[0] ^ 0xFF]) + body[1:]
                flipped["done"] = True
            rows.append((info.filename, info.compress_type, info.external_attr, body))
        return rows

    result = _rewrite_zip(data, t)
    rec.result_digest = _digest(result)
    return result, rec


# ---- reader-site operators (directory in place) ----

def duplicate_chapter_page(site: Path) -> DamageRecord:
    """Copy a chapter page under a new name so its witness appears twice."""

    pages = sorted(p for p in site.glob("*.html") if p.name != "index.html")
    source = pages[0]
    rec = DamageRecord("site.duplicate_chapter", {"page": source.name},
                       _digest(source.read_bytes()))
    (site / "duplicate-chapter.html").write_bytes(source.read_bytes())
    rec.result_digest = _digest((site / "duplicate-chapter.html").read_bytes())
    return rec


def dead_css_url(site: Path) -> DamageRecord:
    css = site / "reader.css"
    rec = DamageRecord("site.dead_css_url", {}, _digest(css.read_bytes()) if css.exists() else "")
    css.write_text("body { background: url(missing-asset.png); }", encoding="utf-8")
    rec.result_digest = _digest(css.read_bytes())
    return rec


def dead_fragment(page: Path) -> DamageRecord:
    rec = DamageRecord("site.dead_fragment", {"page": page.name}, _digest(page.read_bytes()))
    text = page.read_text(encoding="utf-8")
    page.write_text(text + '<a href="#no-such-anchor">dead</a>', encoding="utf-8")
    rec.result_digest = _digest(page.read_bytes())
    return rec


# The map from every operator to the invariant it attacks and the
# diagnostic substring the verifier must emit. A verifier failure class
# without an entry here is an undefended branch; test_damage proves each.
DAMAGE_INVARIANTS: dict[str, dict[str, str]] = {
    "archive.add_member": {"invariant": "INV-archive-source-policy", "diagnostic": "did not admit"},
    "archive.remove_member": {"invariant": "INV-archive-source-policy", "diagnostic": "missing"},
    "archive.escaping_path": {"invariant": "INV-archive-source-policy", "diagnostic": "escapes its prefix"},
    "archive.store_uncompressed": {"invariant": "INV-archive-source-policy", "diagnostic": "not deflated"},
    "archive.flip_byte": {"invariant": "INV-archive-site-bytes", "diagnostic": "bytes disagree"},
    "site.duplicate_chapter": {"invariant": "INV-format-site-identity", "diagnostic": "duplicates"},
    "site.dead_css_url": {"invariant": "INV-pages-refs", "diagnostic": "missing-asset.png"},
    "site.dead_fragment": {"invariant": "INV-pages-refs", "diagnostic": "dead fragment"},
}
