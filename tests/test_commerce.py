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
