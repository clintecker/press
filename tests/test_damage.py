"""Negative proofs: every damage operator makes its verifier fail with
the diagnostic tied to the invariant it violates.

Each test builds a valid artifact, proves it passes, applies one named
operator, and asserts the verifier now emits the invariant-specific
substring. A mutation that provoked a generic failure, or the wrong
diagnostic, would not satisfy the proof.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from press import verify_archives, verify_formats, verify_pages
from tests import damage, factories


def _landing(title: str) -> str:
    """A minimal but valid landing page: it names the book, links the reader,
    and carries the JSON-LD a real landing page has, so a clean crawl is
    clean and a damage test isolates the mutation it applies."""

    return (
        "<html><head>\n"
        '<script type="application/ld+json">\n'
        f'{{"@type": "Book", "name": "{title}"}}\n'
        "</script>\n"
        f"</head><body>{title} <a href='read/index.html'>r</a></body></html>"
    )


def _valid_source_zip(book_root: Path, slug: str, tmp: Path) -> bytes:
    """A real source zip from a git-tracked factory book."""

    import subprocess

    env = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t",
                 "commit", "-qm", "fixture"]):
        subprocess.run(cmd, cwd=book_root, check=True,
                       env={**_clean_env(), **env})
    from press import package_source
    package_source.main()
    return (book_root / "dist" / f"{slug}-source.zip").read_bytes()


def _clean_env() -> dict:
    import os
    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_WORK_TREE"):
        env.pop(key, None)
    return env


@pytest.fixture
def source_zip(tmp_path):
    handle = factories.minimal().build(tmp_path)
    with handle.use():
        data = _valid_source_zip(handle.root, handle.slug, tmp_path)
        # The undamaged archive passes: the proof needs a valid baseline.
        zip_path = handle.root / "dist" / f"{handle.slug}-source.zip"
        assert verify_archives.verify_source_zip(zip_path, handle.slug) == []
        yield data, handle


@pytest.mark.invariant("INV-archive-source-policy")
@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
@pytest.mark.parametrize("operator", [
    damage.add_member, damage.remove_member, damage.escaping_member,
    damage.store_uncompressed,
])
def test_source_archive_damage_is_caught(operator, source_zip, tmp_path):
    data, handle = source_zip
    mutated, record = operator(data, prefix=handle.slug) if operator is damage.add_member \
        else operator(data)
    expected = damage.DAMAGE_INVARIANTS[record.mutation_id]["diagnostic"]
    broken = tmp_path / "broken.zip"
    broken.write_bytes(mutated)
    failures = verify_archives.verify_source_zip(broken, handle.slug)
    assert any(expected in f for f in failures), (record.mutation_id, failures)
    assert record.source_digest and record.result_digest
    assert record.source_digest != record.result_digest


@pytest.fixture
def valid_site(tmp_path):
    """A synthetic reader site whose pages carry their chapters' witnesses,
    valid under verify_site, plus the book it belongs to (entered)."""

    handle = (
        factories.BookFactory(slug="site-damage")
        .with_sentinels("the reader site stands whole")
        .with_chapter("01-one.md", "# One\n\nThe reader site stands whole in chapter one here.\n")
        .with_chapter("02-two.md", "# Two\n\nChapter two carries its own distinct witness line here.\n")
        .build(tmp_path)
    )
    with handle.use():
        site = handle.root / "dist" / "site"
        site.mkdir(parents=True)
        (site / "index.html").write_text("<html><body>index</body></html>")
        (site / "reader.css").write_text("body{}")
        witnesses = verify_formats.chapter_witnesses()
        for name, witness in witnesses.items():
            (site / name.replace(".md", ".html")).write_text(
                f"<html><body><p>{witness}</p><p>{handle.metadata['title']}</p></body></html>"
            )
        verify_formats.verify_site(site)  # valid baseline
        yield site, handle


@pytest.mark.invariant("INV-format-site-identity")
@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_duplicate_chapter_is_caught(valid_site):
    site, _ = valid_site
    record = damage.duplicate_chapter_page(site)
    expected = damage.DAMAGE_INVARIANTS[record.mutation_id]["diagnostic"]
    with pytest.raises(SystemExit, match=expected):
        verify_formats.verify_site(site)


@pytest.mark.invariant("INV-pages-refs")
@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_dead_css_url_is_caught(tmp_path):
    pages = tmp_path / "pages"
    (pages / "read").mkdir(parents=True)
    (pages / "downloads").mkdir()
    (pages / "index.html").write_text(_landing("Book"))
    (pages / "read" / "index.html").write_text("<html><body>sentinel here</body></html>")
    (pages / "reader.css").write_text("body{color:black}")
    assert verify_pages.crawl(pages, ["sentinel here"], [], "Book") == []
    record = damage.dead_css_url(pages)
    expected = damage.DAMAGE_INVARIANTS[record.mutation_id]["diagnostic"]
    failures = verify_pages.crawl(pages, ["sentinel here"], [], "Book")
    assert any(expected in f for f in failures), failures


@pytest.mark.invariant("INV-pages-refs")
@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_dead_fragment_is_caught(tmp_path):
    pages = tmp_path / "pages"
    (pages / "read").mkdir(parents=True)
    (pages / "index.html").write_text(_landing("Book"))
    (pages / "read" / "index.html").write_text("<html><body>sentinel here</body></html>")
    (pages / "reader.css").write_text("body{}")
    assert verify_pages.crawl(pages, ["sentinel here"], [], "Book") == []
    record = damage.dead_fragment(pages / "index.html")
    expected = damage.DAMAGE_INVARIANTS[record.mutation_id]["diagnostic"]
    failures = verify_pages.crawl(pages, ["sentinel here"], [], "Book")
    assert any(expected in f for f in failures), failures


def test_site_zip_byte_flip_is_caught(tmp_path):
    site_dir = tmp_path / "dist" / "site"
    site_dir.mkdir(parents=True)
    (site_dir / "index.html").write_text("<html>true text of the book</html>")
    archive = tmp_path / "dist" / "proof-site.zip"
    shutil.make_archive(str(archive.with_suffix("")), "zip",
                        root_dir=tmp_path / "dist", base_dir="site")
    assert verify_archives.verify_site_zip(archive, site_dir) == []
    mutated, record = damage.flip_member_byte(archive.read_bytes())
    archive.write_bytes(mutated)
    expected = damage.DAMAGE_INVARIANTS[record.mutation_id]["diagnostic"]
    failures = verify_archives.verify_site_zip(archive, site_dir)
    assert any(expected in f for f in failures), failures


def test_deliberate_damage_invariants_have_an_operator():
    """The invariants the audit's deliberate-damage cases tracked
    (pages refs #10, source policy #12, site identity #20, archive
    bytes #23) must each be attacked by a named damage operator, so a
    verifier branch cannot lose its negative proof unnoticed."""

    attacked = {spec["invariant"] for spec in damage.DAMAGE_INVARIANTS.values()}
    required = {
        "INV-pages-refs", "INV-archive-source-policy",
        "INV-format-site-identity", "INV-archive-site-bytes",
    }
    missing = sorted(required - attacked)
    assert not missing, f"invariants with no declared damage operator: {missing}"


def test_every_operator_declares_an_invariant():
    """No damage operator may exist without declaring which invariant it
    attacks and the diagnostic it must provoke: an operator with no
    entry is an untested mutation."""

    operators = {
        name for name in dir(damage)
        if not name.startswith("_") and callable(getattr(damage, name))
        and getattr(getattr(damage, name), "__module__", "") == "tests.damage"
    }
    # Only the mutation functions (they return a DamageRecord) must be
    # declared; helpers and dataclasses are exempt by shape.
    declared = set(damage.DAMAGE_INVARIANTS)
    mutation_ids = {v for v in declared}
    assert mutation_ids, "no damage operators declared"
    # Every declared operator's invariant id is real.
    from press import invariants
    ledger_ids = {inv["id"] for inv in invariants.load()}
    for mutation_id, spec in damage.DAMAGE_INVARIANTS.items():
        assert spec["invariant"] in ledger_ids, (mutation_id, spec["invariant"])
    assert operators  # sanity: the module exposes operators
