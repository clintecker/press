"""Direct print-ordering config and the generated CTA. A disabled or
absent block is silent; an enabled block must name an HTTPS storefront, an
explicit seller of record, and complete HTTPS policy links, and carry no
secret. The rendered control is a script-free link that discloses the
seller and the policies, and the site verifier refuses a CTA that does not
match the config.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from press import commerce, verify_pages


def _cfg(**over):
    block = {"enabled": True, "edition": "paperback",
             "storefront-url": "https://store.example.test/book",
             "seller-of-record": "Lulu", "support-url": "https://ex.test/s",
             "privacy-url": "https://ex.test/p", "refund-url": "https://ex.test/r"}
    block.update(over)
    return commerce.load({"commerce": {"print-ordering": block}})


# ---- load ----

def test_absent_block_loads_none():
    assert commerce.load({}) is None
    assert commerce.load({"commerce": "not-a-mapping"}) is None
    assert commerce.load({"commerce": {"print-ordering": "nope"}}) is None


def test_a_valid_block_loads_and_validates():
    assert commerce.validate(_cfg()) == []


# ---- validate (the verifier) ----

def test_a_disabled_block_is_silent():
    assert commerce.validate(_cfg(enabled=False)) == []
    assert commerce.render(_cfg(enabled=False)) == ""


@pytest.mark.invariant("INV-commerce-config")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_non_https_storefront_is_refused():
    assert any("storefront-url must be https" in p
               for p in commerce.validate(_cfg(**{"storefront-url": "http://x.test"})))


@pytest.mark.invariant("INV-commerce-config")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_missing_policy_link_is_refused():
    assert any("refund-url is required" in p
               for p in commerce.validate(_cfg(**{"refund-url": ""})))


@pytest.mark.invariant("INV-commerce-config")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_an_unnamed_seller_is_refused():
    assert any("seller-of-record" in p
               for p in commerce.validate(_cfg(**{"seller-of-record": ""})))


@pytest.mark.invariant("INV-commerce-config")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_an_embedded_secret_is_refused():
    bad = _cfg(**{"support-url": "https://ex.test/s?api_key=sk_live_abcdef"})
    assert any("secret" in p for p in commerce.validate(bad))


@pytest.mark.invariant("INV-commerce-config")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_an_unknown_key_is_refused():
    bad = commerce.load({"commerce": {"print-ordering": {
        "enabled": True, "edition": "paperback",
        "storefront-url": "https://s.test/x", "seller-of-record": "Lulu",
        "support-url": "https://ex.test/s", "privacy-url": "https://ex.test/p",
        "refund-url": "https://ex.test/r", "broker-url": "https://oops"}}})
    assert any("unknown key" in p for p in commerce.validate(bad))


def test_failures_reads_book_metadata(monkeypatch):
    from press import booklib

    monkeypatch.setattr(booklib, "metadata", lambda: {"commerce": {
        "print-ordering": {"enabled": True, "edition": "pb",
                            "storefront-url": "http://x", "seller-of-record": "",
                            "support-url": "", "privacy-url": "", "refund-url": ""}}})
    assert commerce.failures()  # a broken enabled block fails press check


# ---- render (the CTA) ----

def test_the_cta_is_a_scriptless_link_with_disclosure_and_policies():
    html = commerce.render(_cfg())
    assert 'class="print-order"' in html
    assert "https://store.example.test/book" in html
    assert "<script" not in html  # CSP-safe, no JavaScript
    assert "seller of record" in html
    assert "Lulu" in html
    for _, url in _cfg().policy_links():
        assert url in html


def test_html_in_config_is_escaped():
    cfg = _cfg(**{"seller-of-record": 'Ac<me>&"'})
    html = commerce.render(cfg)
    assert "<me>" not in html
    assert "&lt;me&gt;" in html


def test_the_documented_commerce_example_actually_validates():
    # The guide's config example must stay in sync with the runtime: it
    # parses, validates, and carries no secret. (A #138 documentation test.)
    import re

    import yaml

    doc = (Path(__file__).resolve().parent.parent / "docs" / "PRINT-ORDERING.md")
    blocks = re.findall(r"```yaml\n(.*?)```", doc.read_text(encoding="utf-8"), re.S)
    examples = [b for b in blocks if "print-ordering" in b]
    assert examples, "the print-ordering guide has no commerce example"
    for block in examples:
        cfg = commerce.load(yaml.safe_load(block))
        assert commerce.validate(cfg) == []


# ---- the site verifier ----

def _pages_with(index_html: str, tmp_path: Path) -> Path:
    pages = tmp_path / "pages"
    (pages / "read").mkdir(parents=True)
    (pages / "index.html").write_text(index_html, encoding="utf-8")
    return pages


def test_verifier_accepts_a_matching_enabled_page(tmp_path):
    cfg = _cfg()
    page = f"<html><body>{commerce.render(cfg)}</body></html>"
    pages = _pages_with(page, tmp_path)
    assert verify_pages.check_commerce(pages, cfg) == []


@pytest.mark.invariant("INV-commerce-config")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_verifier_refuses_a_stray_cta_when_disabled(tmp_path):
    cfg_on = _cfg()
    page = f"<html><body>{commerce.render(cfg_on)}</body></html>"
    pages = _pages_with(page, tmp_path)
    problems = verify_pages.check_commerce(pages, _cfg(enabled=False))
    assert any("not enabled" in p for p in problems)


@pytest.mark.invariant("INV-commerce-config")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_verifier_refuses_a_missing_cta_when_enabled(tmp_path):
    pages = _pages_with("<html><body>no cta here</body></html>", tmp_path)
    problems = verify_pages.check_commerce(pages, _cfg())
    assert any("no print-order CTA" in p for p in problems)


@pytest.mark.invariant("INV-commerce-config")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_verifier_refuses_a_leaked_secret_in_a_page(tmp_path):
    cfg = _cfg()
    page = (f"<html><body>{commerce.render(cfg)}"
            "<!-- oops api_key=sk_live_leak --></body></html>")
    pages = _pages_with(page, tmp_path)
    assert any("leak a secret" in p for p in verify_pages.check_commerce(pages, cfg))


# ---- the release gate (pure decision) ----

def test_release_gate_ships_a_book_that_sells_nothing():
    assert commerce.release_problems(None, edition_qualified=False) == []
    assert commerce.release_problems(_cfg(enabled=False), edition_qualified=False) == []


def test_release_gate_passes_a_qualified_valid_edition():
    assert commerce.release_problems(_cfg(), edition_qualified=True) == []


@pytest.mark.invariant("INV-commerce-release-gate")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_release_gate_refuses_an_unqualified_edition():
    problems = commerce.release_problems(_cfg(), edition_qualified=False)
    assert any("no passed physical qualification" in p for p in problems)


@pytest.mark.invariant("INV-commerce-release-gate")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_release_gate_surfaces_a_config_error_even_when_qualified():
    bad = _cfg(**{"storefront-url": "http://insecure"})
    assert any("https" in p for p in commerce.release_problems(bad, edition_qualified=True))


# ---- the release gate (orchestrator, end to end) ----

def _write_pdf(path, pages):
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=432, height=648)
    with open(path, "wb") as handle:
        writer.write(handle)


@pytest.mark.layer("integration")
def test_release_gate_end_to_end(scaffolded_book, monkeypatch):
    import yaml

    from press import booklib, edition, qualification, registry

    root = booklib.root()
    slug = booklib.slug()
    book = booklib.book()
    (root / "dist").mkdir(exist_ok=True)
    _write_pdf(edition.interior_path(root, slug), 88)
    _write_pdf(edition.cover_path(root, slug), 1)

    # Enable ordering in the book's metadata (clear the cached read).
    meta_path = root / "config" / "metadata.yaml"
    meta_path.write_text(meta_path.read_text() + (
        "\ncommerce:\n  print-ordering:\n    enabled: true\n"
        "    edition: paperback\n"
        "    storefront-url: \"https://store.example.test/x\"\n"
        "    seller-of-record: \"Lulu\"\n"
        "    support-url: \"https://ex.test/s\"\n"
        "    privacy-url: \"https://ex.test/p\"\n"
        "    refund-url: \"https://ex.test/r\"\n"), encoding="utf-8")
    booklib.metadata.cache_clear()
    # The print pack is already on disk; do not rebuild it in the test.
    monkeypatch.setattr(registry, "build", lambda name: None)

    # The edition identity the gate will compute, to scope the inspection.
    manifest = edition.build([], root=root, book=book, fmt="paperback")
    qual_path = root / "config" / "qualification.yaml"

    def write_inspection(edition_id):
        qual_path.write_text(yaml.safe_dump({"schema_version": 1, "inspections": [{
            "provider": "lulu", "product_id": "PB-BW-6x9", "region": "US",
            "edition_id": edition_id, "inspector": "tester",
            "results": {p: "pass" for p in qualification.REQUIRED_CHECKLIST}}]}),
            encoding="utf-8")

    # With a passed inspection scoped to this edition, the gate is green.
    write_inspection(manifest.edition_id)
    problems, summary = commerce.release_gate(root, book)
    assert problems == [], problems
    assert "1 passed qualification" in summary

    # An inspection of a different edition is stale: the gate fails closed.
    write_inspection("a-different-edition-id")
    problems, _ = commerce.release_gate(root, book)
    assert any("no passed physical qualification" in p or "different edition" in p
               for p in problems)

    # No qualification file at all: fail closed.
    qual_path.unlink()
    problems, _ = commerce.release_gate(root, book)
    assert any("no passed physical qualification" in p for p in problems)
