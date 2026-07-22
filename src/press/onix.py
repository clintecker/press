"""ONIX 3.0 generation: the metadata record distributors ingest.

There is no API that issues an identifier or accepts a title feed without
human onboarding, so the automatable work is here: turn the book's config
into a valid ONIX 3.0 message a distributor (Bowker, Ingram, Amazon) can
read. This emits one ``<Product>`` per sellable edition -- a physical
product for the print ISBN, an ``EA`` product for the EPUB ISBN -- from the
typed book model, and degrades honestly where the press deliberately holds
nothing: there is no price in a book repository, so no ``<Price>`` is
emitted, and only a publication *year* is machine-available, so the
publishing date carries a year, not a fabricated day.

ISBN-13 is ``ProductIDType`` 15 (EDItEUR Code List issue 73), not 03. The
reference (long-tag) vocabulary is used, in the default 3.0 namespace.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .bookmodel import Book

NS = "http://ns.editeur.org/onix/3.0/reference"

# Board bindings are hardback (BB); the soft-cover bindings are paperback
# (BC). A digital edition is EA. (ONIX List 150.)
_HARDCOVER = frozenset({"casewrap", "dust-jacket"})

# BCP-47 primary subtag -> ISO 639-2/B, the codes ONIX LanguageCode wants.
# Small on purpose: an unmapped language omits the element rather than emit an
# invalid code.
_LANG3 = {
    "en": "eng", "fr": "fre", "es": "spa", "de": "ger", "it": "ita",
    "pt": "por", "nl": "dut", "sv": "swe", "la": "lat", "ja": "jpn",
    "zh": "chi", "ru": "rus", "ar": "ara",
}


@dataclass(frozen=True)
class Edition:
    """One sellable edition to describe: its ONIX product form and the clean
    13-digit ISBN, or ``None`` when the book has not been assigned one yet."""

    label: str        # "print" | "epub"
    form: str         # ONIX ProductForm: BB | BC | EA
    isbn: str | None


def product_form(binding: str | None) -> str:
    """The ONIX physical product form for a binding."""

    return "BB" if binding in _HARDCOVER else "BC"


def _el(parent: ET.Element, tag: str, text: str | None = None) -> ET.Element:
    child = ET.SubElement(parent, f"{{{NS}}}{tag}")
    if text is not None:
        child.text = text
    return child


def _record_reference(book: Book, label: str) -> str:
    base = book.site_url or book.repository or f"press:{book.slug}"
    return f"{base.rstrip('/')}/{book.slug}-{label}"


def _title_detail(parent: ET.Element, book: Book) -> None:
    detail = _el(parent, "TitleDetail")
    _el(detail, "TitleType", "01")
    element = _el(detail, "TitleElement")
    _el(element, "TitleElementLevel", "01")
    _el(element, "TitleText", book.title)
    if book.subtitle:
        _el(element, "Subtitle", book.subtitle)


def _contributors(parent: ET.Element, book: Book) -> None:
    for seq, name in enumerate(book.authors, 1):
        contributor = _el(parent, "Contributor")
        _el(contributor, "SequenceNumber", str(seq))
        _el(contributor, "ContributorRole", "A01")   # by (author)
        _el(contributor, "PersonName", name)


def _product(book: Book, edition: Edition, lang: str | None, status: str) -> ET.Element:
    product = ET.Element(f"{{{NS}}}Product")
    _el(product, "RecordReference", _record_reference(book, edition.label))
    _el(product, "NotificationType", "03")   # confirmed record
    if edition.isbn:
        identifier = _el(product, "ProductIdentifier")
        _el(identifier, "ProductIDType", "15")   # ISBN-13
        _el(identifier, "IDValue", edition.isbn)

    descriptive = _el(product, "DescriptiveDetail")
    _el(descriptive, "ProductComposition", "00")   # single-component
    _el(descriptive, "ProductForm", edition.form)
    _title_detail(descriptive, book)
    _contributors(descriptive, book)
    code3 = _LANG3.get((lang or "").split("-")[0].lower())
    if code3:
        language = _el(descriptive, "Language")
        _el(language, "LanguageRole", "01")   # language of text
        _el(language, "LanguageCode", code3)

    publishing = _el(product, "PublishingDetail")
    if book.publisher:
        publisher = _el(publishing, "Publisher")
        _el(publisher, "PublishingRole", "01")   # publisher
        _el(publisher, "PublisherName", book.publisher)
    if book.publisher_place:
        _el(publishing, "CityOfPublication", book.publisher_place)
    _el(publishing, "PublishingStatus", status)
    if book.year:
        date = _el(publishing, "PublishingDate")
        _el(date, "PublishingDateRole", "01")   # publication date
        # dateformat 05 = year only; the press knows the year, not the day.
        _el(date, "Date", book.year).set("dateformat", "05")
    # No <ProductSupply>/<Price>: a book repository holds no price, by design.
    return product


def build(
    book: Book,
    editions: list[Edition],
    *,
    lang: str | None,
    sent: str,
    sender: str,
    status: str = "04",
) -> str:
    """A complete ONIX 3.0 message for the given editions, as a UTF-8 XML
    string with a declaration. ``sent`` is the SentDateTime (YYYYMMDD or
    YYYYMMDDThhmm), supplied by the caller so this stays deterministic;
    ``status`` is the ONIX PublishingStatus (04 active, 02 forthcoming)."""

    ET.register_namespace("", NS)
    message = ET.Element(f"{{{NS}}}ONIXMessage", release="3.0")
    header = _el(message, "Header")
    sender_el = _el(header, "Sender")
    _el(sender_el, "SenderName", sender)
    _el(header, "SentDateTime", sent)
    for edition in editions:
        message.append(_product(book, edition, lang, status))

    ET.indent(message, space="  ")
    body = ET.tostring(message, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"


def editions_for(book: Book, print_isbn: str | None, epub_isbn: str | None) -> list[Edition]:
    """The editions worth a record: a physical product whose form follows the
    binding, and an EPUB product when an EPUB ISBN exists. A book with neither
    ISBN still gets its physical record (RecordReference is enough to be
    structurally valid), so `press onix` produces something honest to inspect
    before an ISBN is bought."""

    binding = (book.print_config or {}).get("binding")
    editions = [Edition("print", product_form(binding), print_isbn)]
    if epub_isbn:
        editions.append(Edition("epub", "EA", epub_isbn))
    return editions
