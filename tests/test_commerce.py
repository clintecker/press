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


def _meta(**over):
    block = {"enabled": True, "edition": "paperback",
             "storefront-url": "https://store.example.test/book",
             "seller-of-record": "Lulu", "support-url": "https://ex.test/s",
             "privacy-url": "https://ex.test/p", "refund-url": "https://ex.test/r"}
    block.update(over)
    return {"commerce": {"print-ordering": block}}


def _cfg(**over):
    return commerce.load(_meta(**over))


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


def test_an_omitted_policy_link_is_allowed_and_generated():
    # Omitting a policy url means press generates the page on the site.
    cfg = _cfg(**{"refund-url": ""})
    assert commerce.validate(cfg) == []
    assert cfg.policy_href("refund") == "refunds.html"
    assert "refund" in cfg.generated_kinds()


def test_a_provided_policy_link_is_used_and_not_generated():
    cfg = _cfg()  # all three urls provided
    assert cfg.policy_href("support") == "https://ex.test/s"
    assert cfg.generated_kinds() == []


@pytest.mark.invariant("INV-commerce-config")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_non_https_policy_link_is_refused():
    assert any("privacy-url must be https" in p
               for p in commerce.validate(_cfg(**{"privacy-url": "http://x.test"})))


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


# ---- generated policy pages (#151) ----

def test_generated_policy_body_discloses_the_seller_and_publisher():
    cfg = _cfg(**{"privacy-url": ""})
    body = commerce.render_policy_body(cfg, "My Press", "privacy")
    assert "Lulu" in body and "seller of record" in body
    assert "My Press" in body


def test_publisher_policy_text_appears_and_a_secret_is_refused():
    cfg = _cfg(policies={"support": "Email books@example.test with questions."})
    body = commerce.render_policy_body(cfg, "P", "support")
    assert "Email books@example.test" in body
    leaky = _cfg(policies={"privacy": "our api_key=sk_live_oops"})
    assert any("policies.privacy" in p for p in commerce.validate(leaky))


def test_unknown_policy_key_is_refused():
    bad = _cfg(policies={"shipping": "we ship fast"})
    assert any("policies has unknown key" in p for p in commerce.validate(bad))


@pytest.mark.layer("integration")
def test_build_writes_generated_policy_pages_only_where_no_url(scaffolded_book, tmp_path):
    from types import SimpleNamespace

    from press import build

    out = tmp_path / "pages"
    out.mkdir()
    meta = _meta(**{"support-url": "", "privacy-url": ""})  # refund keeps its url
    build._write_policy_pages(out, meta, SimpleNamespace(title="My Book", publisher="My Press"))
    assert (out / "support.html").is_file()
    assert (out / "privacy.html").is_file()
    assert not (out / "refunds.html").exists()
    privacy = (out / "privacy.html").read_text(encoding="utf-8")
    assert "Lulu" in privacy and "My Book" in privacy and "seller of record" in privacy


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


@pytest.mark.invariant("INV-commerce-config")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_verifier_requires_a_generated_policy_page(tmp_path):
    cfg = _cfg(**{"support-url": ""})  # support is generated, not linked out
    page = f"<html><body>{commerce.render(cfg)}</body></html>"
    pages = _pages_with(page, tmp_path)  # but support.html was not written
    problems = verify_pages.check_commerce(pages, cfg)
    assert any("support policy page support.html is missing" in p for p in problems)


def test_verifier_accepts_a_present_disclosing_policy_page(tmp_path):
    cfg = _cfg(**{"support-url": ""})
    page = f"<html><body>{commerce.render(cfg)}</body></html>"
    pages = _pages_with(page, tmp_path)
    (pages / "support.html").write_text(
        "<html><body>Sold by Lulu, the seller of record.</body></html>",
        encoding="utf-8")
    assert verify_pages.check_commerce(pages, cfg) == []


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


@pytest.mark.parametrize(("problems", "release", "expected"), [
    ([], False, 0),
    (["edition has no passed physical qualification"], False, 0),
    (["edition has no passed physical qualification"], True, 1),
])
def test_cli_commerce_gate_is_advisory_locally_and_fail_closed_in_release(
        problems, release, expected, monkeypatch, capsys, tmp_path):
    """The CLI reports the same decision in both modes, but only a release
    may be blocked. This restores proof of the branch added with commerce."""

    from press import __main__ as cli, booklib

    monkeypatch.setattr(booklib, "root", lambda: tmp_path)
    monkeypatch.setattr(booklib, "book", lambda: object())
    monkeypatch.setattr(
        commerce, "release_gate", lambda root, book: (problems, "paperback"))
    if release:
        monkeypatch.setenv("PRESS_RELEASE", "1")
    else:
        monkeypatch.delenv("PRESS_RELEASE", raising=False)

    assert cli._commerce_gate() == expected
    output = capsys.readouterr().out
    assert "commerce release gate: paperback" in output
    if problems:
        assert problems[0] in output
    if problems and not release:
        assert "advisory" in output


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
