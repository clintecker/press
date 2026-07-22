"""ONIX 3.0 generation: a well-formed record with the right identifiers,
product forms, and honest degradation where the press holds nothing.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from press import onix
from press.bookmodel import Book

NS = "{http://ns.editeur.org/onix/3.0/reference}"


def _book(**over) -> Book:
    base = dict(
        root=None, title="The Analytical Engine", subtitle="Notes on the Engine",
        authors=("Ada Lovelace",), date="First edition, 2026", year="2026",
        copyright="2026", publisher="LGTM Publishing", publisher_place="London",
        description="A book.", keywords=(), slug="analytical-engine",
        repository="https://github.com/x/y", site_url="https://x.github.io/y",
        trim_width=6.0, trim_height=9.0, sentinels=(), min_pages=1,
        print_config={"binding": "perfect-bound"}, registrations={},
    )
    base.update(over)
    return Book(**base)


def _parse(xml: str) -> ET.Element:
    return ET.fromstring(xml)


@pytest.mark.layer("unit")
def test_message_is_well_formed_and_namespaced():
    book = _book()
    editions = onix.editions_for(book, "9781234567897", None)
    xml = onix.build(book, editions, lang="en-US", sent="20260101T0000",
                     sender="LGTM Publishing")
    root = _parse(xml)   # raises if malformed
    assert root.tag == f"{NS}ONIXMessage"
    assert root.get("release") == "3.0"
    assert root.find(f"{NS}Header/{NS}Sender/{NS}SenderName").text == "LGTM Publishing"


@pytest.mark.layer("unit")
def test_isbn_is_product_id_type_15():
    book = _book()
    editions = onix.editions_for(book, "9781234567897", None)
    root = _parse(onix.build(book, editions, lang="en", sent="20260101", sender="p"))
    ident = root.find(f"{NS}Product/{NS}ProductIdentifier")
    assert ident.find(f"{NS}ProductIDType").text == "15"
    assert ident.find(f"{NS}IDValue").text == "9781234567897"


@pytest.mark.layer("unit")
def test_hardcover_binding_is_form_bb():
    book = _book(print_config={"binding": "casewrap"})
    assert onix.product_form("casewrap") == "BB"
    editions = onix.editions_for(book, "9781234567897", None)
    root = _parse(onix.build(book, editions, lang="en", sent="20260101", sender="p"))
    form = root.find(f"{NS}Product/{NS}DescriptiveDetail/{NS}ProductForm")
    assert form.text == "BB"


@pytest.mark.layer("unit")
def test_epub_isbn_adds_a_second_ea_product():
    book = _book()
    editions = onix.editions_for(book, "9781234567897", "9789876543210")
    root = _parse(onix.build(book, editions, lang="en", sent="20260101", sender="p"))
    products = root.findall(f"{NS}Product")
    forms = [p.find(f"{NS}DescriptiveDetail/{NS}ProductForm").text for p in products]
    assert forms == ["BC", "EA"]


@pytest.mark.layer("unit")
def test_no_isbn_still_produces_a_structural_record():
    book = _book()
    editions = onix.editions_for(book, None, None)
    root = _parse(onix.build(book, editions, lang="en", sent="20260101", sender="p"))
    product = root.find(f"{NS}Product")
    assert product.find(f"{NS}RecordReference").text.endswith("analytical-engine-print")
    # No fabricated identifier when the book has no ISBN yet.
    assert product.find(f"{NS}ProductIdentifier") is None


@pytest.mark.layer("unit")
def test_no_price_is_emitted_ever():
    book = _book()
    editions = onix.editions_for(book, "9781234567897", None)
    xml = onix.build(book, editions, lang="en", sent="20260101", sender="p")
    # A book repository holds no price by design; ONIX must not invent one.
    assert "<Price>" not in xml and "ProductSupply" not in xml


@pytest.mark.layer("unit")
def test_year_only_publishing_date():
    book = _book()
    editions = onix.editions_for(book, "9781234567897", None)
    root = _parse(onix.build(book, editions, lang="en", sent="20260101", sender="p"))
    date = root.find(f"{NS}Product/{NS}PublishingDetail/{NS}PublishingDate/{NS}Date")
    assert date.text == "2026" and date.get("dateformat") == "05"


@pytest.mark.layer("unit")
def test_unmappable_language_omits_the_element():
    book = _book()
    editions = onix.editions_for(book, "9781234567897", None)
    root = _parse(onix.build(book, editions, lang="xx-YY", sent="20260101", sender="p"))
    assert root.find(f"{NS}Product/{NS}DescriptiveDetail/{NS}Language") is None


@pytest.mark.layer("unit")
def test_special_characters_are_escaped():
    book = _book(title="Ada & the <Engine>")
    editions = onix.editions_for(book, "9781234567897", None)
    root = _parse(onix.build(book, editions, lang="en", sent="20260101", sender="p"))
    title = root.find(f"{NS}Product/{NS}DescriptiveDetail/{NS}TitleDetail/"
                      f"{NS}TitleElement/{NS}TitleText")
    assert title.text == "Ada & the <Engine>"   # parsed back intact -> was escaped


@pytest.mark.layer("unit")
def test_forthcoming_status():
    book = _book()
    editions = onix.editions_for(book, "9781234567897", None)
    root = _parse(onix.build(book, editions, lang="en", sent="20260101",
                             sender="p", status="02"))
    assert root.find(f"{NS}Product/{NS}PublishingDetail/{NS}PublishingStatus").text == "02"
