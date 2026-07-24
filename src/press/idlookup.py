"""Opt-in, read-only lookup of already-issued identifiers.

The registrations ledger states an ISBN, ISSN, or LCCN once, and the
press validates its arithmetic offline. This module is the one place that
reaches outward, and only when a human asks: given an LCCN or ISSN the
author was *already issued* by an authority, confirm it resolves to a
record and that the record is really that identifier's. It is never an
issuance path -- there is no API that mints an identifier, and this asks
for none. An ordinary build never calls it; ``press check``,
``press all``, and front-matter generation stay offline and
deterministic.

Every outward call is injected as a typed transport (the boundary in
:mod:`press.adapters.http`); this domain code opens no socket and holds
no session, so a test drives a canned exchange with no network. The
lookup is bounded on every axis and fails closed: a timeout, a
connection loss, or a server error is retried a fixed number of times
and then reported *unavailable* (never a crash, never a false
not-found); redirects are followed to a fixed depth; the response body
is capped in size, its media type is checked against an allow-list, a
document that declares XML entities is refused unparsed, and the parsed
record must carry the exact identifier that was requested or the outcome
is *mismatch*. The result is a typed record carrying the source URL, the
provenance, and one explicit outcome: found, not-found, ambiguous,
mismatch, invalid, or unavailable.

Authoritative endpoints:

* LCCN -- the Library of Congress LCCN Permalink service
  (``lccn.loc.gov/<lccn>/mods``), which returns a MODS record.
* ISSN -- the ISSN Portal (``portal.issn.org/resource/ISSN/<issn>``)
  under content negotiation, which returns JSON-LD.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urljoin

from . import registrations
from .providers.transport import Response, TransportError, TransportTimeout

# --- bounds; fail closed past any of them -------------------------------

TIMEOUT = 10.0          # seconds handed to the transport per request
MAX_RETRIES = 2         # extra attempts on timeout / connection loss / 5xx
MAX_REDIRECTS = 3       # 3xx hops followed before giving up
MAX_BYTES = 512 * 1024  # largest response body accepted

_USER_AGENT = "press-registrations-lookup (+https://github.com/clintecker/press)"
_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})

_MODS_NS = "{http://www.loc.gov/mods/v3}"
_LCCN_URL = "https://lccn.loc.gov/{lccn}/mods"
_LCCN_ACCEPT = "application/mods+xml, application/xml;q=0.9"
_LCCN_MEDIA = frozenset({"application/xml", "text/xml", "application/mods+xml"})
_LCCN_PROVENANCE = "Library of Congress LCCN Permalink (lccn.loc.gov, MODS)"

_ISSN_URL = "https://portal.issn.org/resource/ISSN/{issn}"
_ISSN_ACCEPT = "application/ld+json, application/json;q=0.9"
_ISSN_MEDIA = frozenset({"application/json", "application/ld+json"})
_ISSN_PROVENANCE = "ISSN Portal content negotiation (portal.issn.org, JSON-LD)"


class Outcome(str, Enum):
    """The one explicit thing a lookup can conclude."""

    FOUND = "found"            # a single record, and it carries the request
    NOT_FOUND = "not-found"    # the authority has no such record
    AMBIGUOUS = "ambiguous"    # more than one record carries the request
    MISMATCH = "mismatch"      # a record came back, for a different identifier
    INVALID = "invalid"        # the request is not a well-formed identifier
    UNAVAILABLE = "unavailable"  # the lookup could not be completed, bounded out


@dataclass(frozen=True)
class LookupResult:
    """The typed record a lookup returns: the outcome, where it came from,
    and (when found) the identifier the record actually carries and its
    title. Never raises for a network or data problem -- those are
    outcomes, not exceptions."""

    kind: str                       # "lccn" | "issn"
    query: str                      # the normalized identifier requested
    outcome: Outcome
    source_url: str                 # the endpoint consulted ("" if never reached)
    provenance: str                 # human description of the authority
    identifier: str | None = None   # the identifier the matched record carries
    title: str | None = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.outcome is Outcome.FOUND


@dataclass(frozen=True)
class _Fail:
    """An internal fetch/parse dead-end, carried until it becomes a
    LookupResult with the same outcome."""

    outcome: Outcome
    detail: str = ""


@dataclass(frozen=True)
class _Body:
    """A fetched, bounded, decoded response body and the URL it came
    from."""

    text: str
    final_url: str


# --- the bounded fetch pipeline -----------------------------------------


def _fetch_once(transport: object, url: str, accept: str, *,
                timeout: float, max_retries: int) -> "Response | _Fail":
    """One URL, retried a fixed number of times on a lost/refused request
    or a 5xx, then reported unavailable. A 4xx or a redirect is a real
    response and is returned as-is for the caller to classify."""

    headers = {"Accept": accept, "User-Agent": _USER_AGENT}
    attempt = 0
    while True:
        try:
            response = transport("GET", url, headers=headers, timeout=timeout)  # type: ignore[operator]
        except TransportTimeout:
            if attempt >= max_retries:
                return _Fail(Outcome.UNAVAILABLE, f"timed out after {attempt + 1} attempts")
            attempt += 1
            continue
        except TransportError as exc:
            if attempt >= max_retries:
                return _Fail(Outcome.UNAVAILABLE, f"connection failed: {exc}")
            attempt += 1
            continue
        if 500 <= response.status < 600:
            if attempt >= max_retries:
                return _Fail(Outcome.UNAVAILABLE, f"server error {response.status}")
            attempt += 1
            continue
        return response


def _fetch(transport: object, url: str, accept: str, media_types: frozenset[str], *,
           timeout: float, max_retries: int, max_redirects: int) -> "_Body | _Fail":
    """Fetch a URL, following bounded redirects, and return a size- and
    media-type-checked body -- or a failure carrying an explicit
    outcome."""

    current = url
    hops = 0
    while True:
        response = _fetch_once(transport, current, accept,
                               timeout=timeout, max_retries=max_retries)
        if isinstance(response, _Fail):
            return response
        if response.status in _REDIRECT_CODES:
            if hops >= max_redirects:
                return _Fail(Outcome.UNAVAILABLE, f"exceeded {max_redirects} redirects")
            location = _header(response.headers, "Location")
            if not location:
                return _Fail(Outcome.UNAVAILABLE, "redirect with no Location header")
            current = urljoin(current, location)
            hops += 1
            continue
        if response.status == 404:
            return _Fail(Outcome.NOT_FOUND, "the authority returned 404")
        if response.status != 200:
            return _Fail(Outcome.UNAVAILABLE, f"unexpected status {response.status}")
        return _read(response, media_types, current)


def _read(response: Response, media_types: frozenset[str], final_url: str) -> "_Body | _Fail":
    """Bound the body by declared and actual size, check its media type,
    and decode it as UTF-8 -- any of which can fail closed."""

    declared = _header(response.headers, "Content-Length")
    if declared and declared.isdigit() and int(declared) > MAX_BYTES:
        return _Fail(Outcome.UNAVAILABLE, "declared response exceeds the size bound")
    body = response.body or b""
    if len(body) > MAX_BYTES:
        return _Fail(Outcome.UNAVAILABLE, "response exceeds the size bound")
    media = _content_type(response.headers)
    if media not in media_types:
        return _Fail(Outcome.UNAVAILABLE, f"unexpected media type {media!r}")
    try:
        return _Body(body.decode("utf-8"), final_url)
    except UnicodeDecodeError:
        return _Fail(Outcome.UNAVAILABLE, "response body was not valid UTF-8")


def _header(headers: dict[str, str], name: str) -> str:
    """Case-insensitive header read; '' when absent."""

    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return ""


def _content_type(headers: dict[str, str]) -> str:
    """The media type alone, lower-cased, parameters stripped."""

    return _header(headers, "Content-Type").split(";", 1)[0].strip().lower()


# --- LCCN --------------------------------------------------------------


def lookup_lccn(transport: object, raw: str, *, timeout: float = TIMEOUT,
                max_retries: int = MAX_RETRIES,
                max_redirects: int = MAX_REDIRECTS) -> LookupResult:
    """Resolve an already-issued LCCN through the LC Permalink MODS
    endpoint. The LCCN is normalized before lookup and the returned record
    must carry it."""

    normalized = registrations.lccn_normalize(str(raw).strip())
    if not registrations.lccn_plausible(normalized):
        return LookupResult("lccn", normalized, Outcome.INVALID, "", _LCCN_PROVENANCE,
                            detail="not the shape of an LCCN")
    url = _LCCN_URL.format(lccn=normalized)
    body = _fetch(transport, url, _LCCN_ACCEPT, _LCCN_MEDIA,
                  timeout=timeout, max_retries=max_retries, max_redirects=max_redirects)
    if isinstance(body, _Fail):
        return LookupResult("lccn", normalized, body.outcome, url,
                            _LCCN_PROVENANCE, detail=body.detail)
    return _match_lccn(normalized, body, url)


def _match_lccn(query: str, body: _Body, url: str) -> LookupResult:
    records = _parse_mods(body.text)
    if records is None:
        return LookupResult("lccn", query, Outcome.UNAVAILABLE, url, _LCCN_PROVENANCE,
                            detail="MODS response was malformed or declared entities")
    if not records:
        return LookupResult("lccn", query, Outcome.NOT_FOUND, url, _LCCN_PROVENANCE,
                            detail="no MODS record in the response")
    matches = [record for record in records if query in record[0]]
    if len(matches) == 1:
        return LookupResult("lccn", query, Outcome.FOUND, url, _LCCN_PROVENANCE,
                            identifier=query, title=matches[0][1])
    if len(matches) > 1:
        return LookupResult("lccn", query, Outcome.AMBIGUOUS, url, _LCCN_PROVENANCE,
                            detail=f"{len(matches)} records carry this LCCN")
    return LookupResult("lccn", query, Outcome.MISMATCH, url, _LCCN_PROVENANCE,
                        detail="the record returned carries a different LCCN")


def _parse_mods(text: str) -> "list[tuple[set[str], str | None]] | None":
    """Each MODS record as (its normalized LCCNs, its title). ``None`` when
    the document is malformed or declares XML entities (refused unparsed to
    defeat entity-expansion)."""

    if _declares_entities(text):
        return None
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    records: list[tuple[set[str], str | None]] = []
    for mods in _mods_elements(root):
        lccns = {
            registrations.lccn_normalize(ident.text.strip())
            for ident in mods.findall(f"{_MODS_NS}identifier")
            if (ident.get("type") or "").lower() == "lccn" and ident.text
        }
        records.append((lccns, _mods_title(mods)))
    return records


def _mods_elements(root: ET.Element) -> list[ET.Element]:
    if root.tag == f"{_MODS_NS}mods":
        return [root]
    return root.findall(f"{_MODS_NS}mods")


def _mods_title(mods: ET.Element) -> str | None:
    title = mods.find(f"{_MODS_NS}titleInfo/{_MODS_NS}title")
    if title is not None and title.text and title.text.strip():
        return title.text.strip()
    return None


def _declares_entities(text: str) -> bool:
    head = text[:4096].upper()
    return "<!DOCTYPE" in head or "<!ENTITY" in head


# --- ISSN --------------------------------------------------------------


def lookup_issn(transport: object, raw: str, *, timeout: float = TIMEOUT,
                max_retries: int = MAX_RETRIES,
                max_redirects: int = MAX_REDIRECTS) -> LookupResult:
    """Resolve an already-issued ISSN through the ISSN Portal under content
    negotiation. The ISSN is check-digit-validated before lookup and the
    returned resource must carry it."""

    digits = _normalize_issn(str(raw))
    if not registrations.issn_valid(digits):
        return LookupResult("issn", digits, Outcome.INVALID, "", _ISSN_PROVENANCE,
                            detail="fails the ISSN check digit")
    canonical = f"{digits[:4]}-{digits[4:]}"
    url = _ISSN_URL.format(issn=canonical)
    body = _fetch(transport, url, _ISSN_ACCEPT, _ISSN_MEDIA,
                  timeout=timeout, max_retries=max_retries, max_redirects=max_redirects)
    if isinstance(body, _Fail):
        return LookupResult("issn", canonical, body.outcome, url,
                            _ISSN_PROVENANCE, detail=body.detail)
    return _match_issn(canonical, digits, body, url)


def _normalize_issn(raw: str) -> str:
    return "".join(ch for ch in raw.upper() if ch.isdigit() or ch == "X")


def _match_issn(canonical: str, digits: str, body: _Body, url: str) -> LookupResult:
    records = _parse_issn(body.text)
    if records is None:
        return LookupResult("issn", canonical, Outcome.UNAVAILABLE, url, _ISSN_PROVENANCE,
                            detail="JSON-LD response was malformed")
    if not records:
        return LookupResult("issn", canonical, Outcome.NOT_FOUND, url, _ISSN_PROVENANCE,
                            detail="no ISSN resource in the response")
    matches = [record for record in records if digits in record[0]]
    if len(matches) == 1:
        return LookupResult("issn", canonical, Outcome.FOUND, url, _ISSN_PROVENANCE,
                            identifier=canonical, title=matches[0][1])
    if len(matches) > 1:
        return LookupResult("issn", canonical, Outcome.AMBIGUOUS, url, _ISSN_PROVENANCE,
                            detail=f"{len(matches)} resources carry this ISSN")
    return LookupResult("issn", canonical, Outcome.MISMATCH, url, _ISSN_PROVENANCE,
                        detail="the portal returned a different ISSN")


def _parse_issn(text: str) -> "list[tuple[set[str], str | None]] | None":
    """Each ISSN resource in the JSON-LD graph as (its ISSNs, its title).
    ``None`` when the JSON is malformed or not an object/graph."""

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    graph = data.get("@graph")
    nodes = graph if isinstance(graph, list) else [data]
    records: list[tuple[set[str], str | None]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        issns = _issn_ids(node)
        if issns:
            records.append((issns, _issn_title(node)))
    return records


def _issn_ids(node: dict) -> set[str]:
    identifier = node.get("@id")
    if not isinstance(identifier, str):
        return set()
    token = _issn_from_id(identifier)
    return {token} if token else set()


def _issn_from_id(identifier: str) -> str:
    marker = "resource/issn/"
    lowered = identifier.lower()
    if marker not in lowered:
        return ""
    tail = identifier[lowered.index(marker) + len(marker):]
    digits = "".join(ch for ch in tail.upper() if ch.isdigit() or ch == "X")
    return digits if len(digits) == 8 else ""


def _issn_title(node: dict) -> str | None:
    for key in ("name", "mainTitle", "title", "label"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    return item.strip()
    return None
