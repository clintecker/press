"""Contract tests for the opt-in, read-only identifier lookup.

No test opens a socket: every case drives the domain code
(``press.idlookup``) through a fake transport that answers from a
programmed script and records the exact outgoing requests, so the bounds
(timeout, retry, redirect, size, media type, schema, identifier match)
are proven against an active signal, not the live authority.

The one live test reaches the real endpoints only when
``PRESS_LIVE_LOOKUP`` is set; it is skipped at runtime otherwise and is
never a release gate.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from press import idlookup, registrations
from press.idlookup import Outcome
from press.providers.transport import Response, TransportError, TransportTimeout

PRESS_SRC = Path(idlookup.__file__).resolve().parent


# --------------------------------------------------------------------------
# A recording fake transport (records requests, answers from a script).
# --------------------------------------------------------------------------


class FakeTransport:
    """A ``Transport`` that records each request and answers from a
    programmed list of ``Response`` values (or raises a programmed
    exception). Accepts and records the bounds the domain passes with each
    request -- ``timeout`` and ``max_bytes`` -- so a test can assert they
    travelled WITH the call rather than being applied afterwards. Never opens
    a socket."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def __call__(self, method, url, *, headers=None, body=None, timeout=None,
                 max_bytes=None):
        self.calls.append(
            {"method": method, "url": url, "headers": dict(headers or {}),
             "timeout": timeout, "max_bytes": max_bytes})
        outcome = self._responses.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def xml_response(body: str, *, media: str = "application/xml", status: int = 200,
                 headers: dict | None = None) -> Response:
    hdrs = {"Content-Type": media}
    hdrs.update(headers or {})
    return Response(status, body.encode("utf-8"), hdrs)


def json_response(body: str, *, media: str = "application/ld+json", status: int = 200,
                  headers: dict | None = None) -> Response:
    hdrs = {"Content-Type": media}
    hdrs.update(headers or {})
    return Response(status, body.encode("utf-8"), hdrs)


VALID_LCCN = "2001012345"
VALID_ISSN = "0378-5955"

MODS_FOUND = """<?xml version="1.0"?>
<mods xmlns="http://www.loc.gov/mods/v3">
  <titleInfo><title>The Example Book</title></titleInfo>
  <identifier type="lccn">  2001012345 </identifier>
</mods>"""

MODS_MISMATCH = """<mods xmlns="http://www.loc.gov/mods/v3">
  <titleInfo><title>A Different Book</title></titleInfo>
  <identifier type="lccn">2009999999</identifier>
</mods>"""

MODS_AMBIGUOUS = """<modsCollection xmlns="http://www.loc.gov/mods/v3">
  <mods><identifier type="lccn">2001012345</identifier></mods>
  <mods><identifier type="lccn">2001012345</identifier></mods>
</modsCollection>"""

MODS_EMPTY = """<modsCollection xmlns="http://www.loc.gov/mods/v3"></modsCollection>"""

MODS_DOCTYPE = """<?xml version="1.0"?>
<!DOCTYPE mods [<!ENTITY x "expand">]>
<mods xmlns="http://www.loc.gov/mods/v3">
  <identifier type="lccn">2001012345</identifier>
</mods>"""

ISSN_FOUND = """{
  "@graph": [
    {"@id": "resource/ISSN/0378-5955", "name": "Ecology Letters"},
    {"@id": "resource/ISSN-L/0378-5955"}
  ]
}"""

ISSN_MISMATCH = """{"@graph": [{"@id": "resource/ISSN/1234-5679", "name": "Other"}]}"""

ISSN_EMPTY = """{"@graph": []}"""

# What the live ISSN Portal actually returns for one issued ISSN: the main
# resource node plus #fragment sub-nodes on the same base IRI. Every node
# reduces to the same eight digits, so this must be FOUND, not AMBIGUOUS.
ISSN_FOUND_WITH_FRAGMENTS = """{
  "@graph": [
    {"@id": "resource/ISSN/0378-5955#ISSN", "value": "0378-5955"},
    {"@id": "resource/ISSN/0378-5955#KeyTitle", "value": "Ecology letters"},
    {"@id": "resource/ISSN/0378-5955#Record"},
    {"@id": "resource/ISSN/0378-5955", "name": "Ecology Letters"},
    {"@id": "resource/ISSN-L/0378-5955"}
  ]
}"""

# Two genuinely distinct resources (different fragment-stripped IRIs) both
# bearing the requested ISSN: this is the real collision AMBIGUOUS guards.
ISSN_AMBIGUOUS = """{
  "@graph": [
    {"@id": "https://portal.issn.org/resource/ISSN/0378-5955", "name": "Journal A"},
    {"@id": "https://mirror.issn.org/resource/ISSN/0378-5955", "name": "Journal B"}
  ]
}"""


# --------------------------------------------------------------------------
# LCCN: success, mismatch, ambiguity, not-found, malformed.
# --------------------------------------------------------------------------


def test_lccn_found_returns_typed_record_with_source_and_provenance():
    transport = FakeTransport([xml_response(MODS_FOUND)])
    result = idlookup.lookup_lccn(transport, "2001-012345")

    assert result.outcome is Outcome.FOUND
    assert result.ok
    assert result.kind == "lccn"
    assert result.query == VALID_LCCN            # normalized before lookup
    assert result.identifier == VALID_LCCN
    assert result.title == "The Example Book"
    assert result.source_url == "https://lccn.loc.gov/2001012345/mods"
    assert "lccn.loc.gov" in result.provenance
    # The request went out normalized, as a GET, bounded, asking for MODS.
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == "https://lccn.loc.gov/2001012345/mods"
    assert call["timeout"] == idlookup.TIMEOUT
    assert "mods" in call["headers"]["Accept"]


def test_lccn_normalizes_hyphen_and_slash_before_lookup():
    transport = FakeTransport([xml_response(MODS_FOUND)])
    idlookup.lookup_lccn(transport, "2001-12345/r842")
    assert transport.calls[0]["url"] == "https://lccn.loc.gov/2001012345/mods"


def test_lccn_record_for_a_different_number_is_a_mismatch():
    transport = FakeTransport([xml_response(MODS_MISMATCH)])
    result = idlookup.lookup_lccn(transport, VALID_LCCN)
    assert result.outcome is Outcome.MISMATCH
    assert not result.ok


def test_lccn_multiple_matching_records_are_ambiguous():
    transport = FakeTransport([xml_response(MODS_AMBIGUOUS)])
    result = idlookup.lookup_lccn(transport, VALID_LCCN)
    assert result.outcome is Outcome.AMBIGUOUS


def test_lccn_404_is_not_found():
    transport = FakeTransport([xml_response("", status=404)])
    result = idlookup.lookup_lccn(transport, VALID_LCCN)
    assert result.outcome is Outcome.NOT_FOUND


def test_lccn_empty_collection_is_not_found():
    transport = FakeTransport([xml_response(MODS_EMPTY)])
    result = idlookup.lookup_lccn(transport, VALID_LCCN)
    assert result.outcome is Outcome.NOT_FOUND


def test_lccn_invalid_input_never_touches_the_network():
    transport = FakeTransport([])  # any call would IndexError
    result = idlookup.lookup_lccn(transport, "not-an-lccn!!")
    assert result.outcome is Outcome.INVALID
    assert result.source_url == ""
    assert transport.calls == []


def test_lccn_malformed_xml_fails_closed_as_unavailable():
    transport = FakeTransport([xml_response("<mods><broken")])
    result = idlookup.lookup_lccn(transport, VALID_LCCN)
    assert result.outcome is Outcome.UNAVAILABLE


def test_lccn_document_declaring_entities_is_refused_unparsed():
    transport = FakeTransport([xml_response(MODS_DOCTYPE)])
    result = idlookup.lookup_lccn(transport, VALID_LCCN)
    assert result.outcome is Outcome.UNAVAILABLE
    assert "entities" in result.detail


def test_lccn_wrong_media_type_fails_closed():
    transport = FakeTransport([xml_response(MODS_FOUND, media="text/html")])
    result = idlookup.lookup_lccn(transport, VALID_LCCN)
    assert result.outcome is Outcome.UNAVAILABLE
    assert "media type" in result.detail


def test_lccn_oversized_declared_length_fails_closed():
    huge = str(idlookup.MAX_BYTES + 1)
    transport = FakeTransport(
        [xml_response(MODS_FOUND, headers={"Content-Length": huge})])
    result = idlookup.lookup_lccn(transport, VALID_LCCN)
    assert result.outcome is Outcome.UNAVAILABLE


def test_lccn_oversized_actual_body_fails_closed():
    body = "<mods xmlns='http://www.loc.gov/mods/v3'>" + "x" * (idlookup.MAX_BYTES + 10)
    transport = FakeTransport([xml_response(body)])
    result = idlookup.lookup_lccn(transport, VALID_LCCN)
    assert result.outcome is Outcome.UNAVAILABLE


def test_lccn_unexpected_status_is_unavailable():
    transport = FakeTransport([xml_response("", status=418)])
    result = idlookup.lookup_lccn(transport, VALID_LCCN)
    assert result.outcome is Outcome.UNAVAILABLE


# --------------------------------------------------------------------------
# Timeout, retry, connection loss.
# --------------------------------------------------------------------------


def test_a_timeout_is_retried_then_succeeds():
    transport = FakeTransport(
        [TransportTimeout("lost"), TransportTimeout("lost"), xml_response(MODS_FOUND)])
    result = idlookup.lookup_lccn(transport, VALID_LCCN)
    assert result.outcome is Outcome.FOUND
    assert len(transport.calls) == 3  # two retries, then the answer


def test_persistent_timeout_bounds_out_as_unavailable():
    transport = FakeTransport([TransportTimeout("lost")] * (idlookup.MAX_RETRIES + 1))
    result = idlookup.lookup_lccn(transport, VALID_LCCN)
    assert result.outcome is Outcome.UNAVAILABLE
    assert len(transport.calls) == idlookup.MAX_RETRIES + 1


def test_connection_failure_bounds_out_as_unavailable():
    transport = FakeTransport([TransportError("refused")] * (idlookup.MAX_RETRIES + 1))
    result = idlookup.lookup_lccn(transport, VALID_LCCN)
    assert result.outcome is Outcome.UNAVAILABLE


def test_server_error_is_retried_then_bounds_out():
    transport = FakeTransport(
        [xml_response("", status=503)] * (idlookup.MAX_RETRIES + 1))
    result = idlookup.lookup_lccn(transport, VALID_LCCN)
    assert result.outcome is Outcome.UNAVAILABLE
    assert len(transport.calls) == idlookup.MAX_RETRIES + 1


# --------------------------------------------------------------------------
# Redirects: followed to a bound, then failed closed.
# --------------------------------------------------------------------------


def test_a_redirect_is_followed_to_the_new_location():
    redirect = Response(301, b"", {"Location": "https://lccn.loc.gov/2001012345/mods"})
    transport = FakeTransport([redirect, xml_response(MODS_FOUND)])
    result = idlookup.lookup_lccn(transport, VALID_LCCN)
    assert result.outcome is Outcome.FOUND
    assert len(transport.calls) == 2
    assert transport.calls[1]["url"] == "https://lccn.loc.gov/2001012345/mods"


def test_a_relative_redirect_resolves_against_the_current_url():
    redirect = Response(302, b"", {"Location": "/2001012345/mods.xml"})
    transport = FakeTransport([redirect, xml_response(MODS_FOUND)])
    idlookup.lookup_lccn(transport, VALID_LCCN)
    assert transport.calls[1]["url"] == "https://lccn.loc.gov/2001012345/mods.xml"


def test_a_redirect_with_no_location_fails_closed():
    transport = FakeTransport([Response(301, b"", {})])
    result = idlookup.lookup_lccn(transport, VALID_LCCN)
    assert result.outcome is Outcome.UNAVAILABLE
    assert "Location" in result.detail


def test_redirect_chain_is_bounded():
    redirect = Response(301, b"", {"Location": "https://lccn.loc.gov/2001012345/mods"})
    transport = FakeTransport([redirect] * (idlookup.MAX_REDIRECTS + 1))
    result = idlookup.lookup_lccn(transport, VALID_LCCN)
    assert result.outcome is Outcome.UNAVAILABLE
    assert "redirect" in result.detail


# --------------------------------------------------------------------------
# ISSN.
# --------------------------------------------------------------------------


def test_issn_found_returns_record():
    transport = FakeTransport([json_response(ISSN_FOUND)])
    result = idlookup.lookup_issn(transport, "03785955")
    assert result.outcome is Outcome.FOUND
    assert result.identifier == VALID_ISSN
    assert result.title == "Ecology Letters"
    assert result.source_url == "https://portal.issn.org/resource/ISSN/0378-5955"
    assert transport.calls[0]["timeout"] == idlookup.TIMEOUT


def test_issn_fragment_subnodes_collapse_to_one_found_record():
    # The main resource node plus its #ISSN/#KeyTitle/#Record fragments all
    # reduce to the same digits; one issued ISSN must resolve, not read as
    # a false collision.
    transport = FakeTransport([json_response(ISSN_FOUND_WITH_FRAGMENTS)])
    result = idlookup.lookup_issn(transport, "03785955")
    assert result.outcome is Outcome.FOUND
    assert result.identifier == VALID_ISSN
    assert result.title == "Ecology Letters"


def test_issn_two_distinct_resources_are_ambiguous():
    transport = FakeTransport([json_response(ISSN_AMBIGUOUS)])
    result = idlookup.lookup_issn(transport, VALID_ISSN)
    assert result.outcome is Outcome.AMBIGUOUS
    assert "2 resources" in result.detail


def test_issn_invalid_check_digit_never_touches_the_network():
    transport = FakeTransport([])
    result = idlookup.lookup_issn(transport, "0378-5954")  # wrong check digit
    assert result.outcome is Outcome.INVALID
    assert transport.calls == []


def test_issn_record_for_a_different_number_is_a_mismatch():
    transport = FakeTransport([json_response(ISSN_MISMATCH)])
    result = idlookup.lookup_issn(transport, VALID_ISSN)
    assert result.outcome is Outcome.MISMATCH


def test_issn_empty_graph_is_not_found():
    transport = FakeTransport([json_response(ISSN_EMPTY)])
    result = idlookup.lookup_issn(transport, VALID_ISSN)
    assert result.outcome is Outcome.NOT_FOUND


def test_issn_malformed_json_fails_closed():
    transport = FakeTransport([json_response("{not json")])
    result = idlookup.lookup_issn(transport, VALID_ISSN)
    assert result.outcome is Outcome.UNAVAILABLE


def test_issn_wrong_media_type_fails_closed():
    transport = FakeTransport([json_response(ISSN_FOUND, media="text/plain")])
    result = idlookup.lookup_issn(transport, VALID_ISSN)
    assert result.outcome is Outcome.UNAVAILABLE


# --------------------------------------------------------------------------
# Property tests over normalization.
# --------------------------------------------------------------------------


@given(st.from_regex(r"[a-z]{0,3}[0-9]{2,4}-?[0-9]{1,6}(/[a-z0-9]{1,6})?", fullmatch=True))
def test_lccn_normalize_is_idempotent_on_wellformed_lccns(raw):
    once = registrations.lccn_normalize(raw)
    assert registrations.lccn_normalize(once) == once


@given(st.text(alphabet="0123456789Xx- ", min_size=0, max_size=16))
def test_issn_normalization_is_idempotent_and_bare(raw):
    once = idlookup._normalize_issn(raw)
    assert idlookup._normalize_issn(once) == once
    assert all(ch.isdigit() or ch == "X" for ch in once)


@given(st.text(min_size=0, max_size=40))
def test_a_normalized_lccn_never_makes_lookup_raise(raw):
    """However hostile the input, a lookup returns a typed result and
    never opens a socket for an implausible identifier."""

    transport = FakeTransport([xml_response(MODS_FOUND)] * 6)
    result = idlookup.lookup_lccn(transport, raw)
    assert isinstance(result, idlookup.LookupResult)
    if not registrations.lccn_plausible(registrations.lccn_normalize(raw.strip())):
        assert result.outcome is Outcome.INVALID
        assert transport.calls == []


# --------------------------------------------------------------------------
# Disabled-network law: the ordinary paths make zero lookups.
# --------------------------------------------------------------------------


class _ForbiddenTransport:
    """A transport that is a test failure the instant it is called."""

    def __init__(self):
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("an ordinary build path made a network call")


def test_press_check_makes_no_network_call(scaffolded_book, monkeypatch):
    """`press check` runs the editorial law with the network transport
    replaced by one that fails if touched -- proving the check path stays
    offline."""

    from press import __main__ as cli
    from press.adapters import http

    forbidden = _ForbiddenTransport()
    monkeypatch.setattr(http, "urlopen_transport", forbidden)
    cli.check()
    assert forbidden.calls == 0


def test_only_the_lookup_command_reaches_idlookup():
    """No module on an ordinary build path (check, all, generation) may
    reference the lookup module: the only referrers are idlookup itself
    and the deliberate `press lookup` CLI handler."""

    referrers = set()
    for path in PRESS_SRC.glob("*.py"):
        if path.stem == "idlookup":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [a.name for a in node.names]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            if any("idlookup" in name for name in names):
                referrers.add(path.stem)
    assert referrers == {"__main__"}, (
        f"unexpected modules import idlookup: {referrers - {'__main__'}}"
    )


# --------------------------------------------------------------------------
# Live endpoint check -- opt-in, never a release gate.
# --------------------------------------------------------------------------


@pytest.mark.live
def test_live_lccn_lookup_reaches_the_real_endpoint():
    if not os.environ.get("PRESS_LIVE_LOOKUP"):
        pytest.skip(
            "set PRESS_LIVE_LOOKUP=1 to exercise the live LC endpoint "
            "(opt-in, not a release gate)")
    from press.adapters import http

    result = idlookup.lookup_lccn(http.urlopen_transport, VALID_LCCN)
    assert result.outcome in {
        Outcome.FOUND, Outcome.NOT_FOUND, Outcome.MISMATCH, Outcome.UNAVAILABLE}
    assert result.source_url.startswith("https://lccn.loc.gov/")


# --- the size bound travels with the request (#209) --------------------------


def test_the_size_bound_is_passed_with_the_request():
    """The bound must reach the transport, not be applied to what it returns.
    A check on the way back has already taken an unbounded body into memory --
    the resource is spent by the time the size is known."""

    transport = FakeTransport([xml_response(MODS_FOUND)])
    idlookup.lookup_lccn(transport, VALID_LCCN)
    assert transport.calls[0]["max_bytes"] == idlookup.MAX_BYTES


def test_a_body_overrunning_the_bound_fails_closed_even_when_length_lies():
    """The dangerous case: a server that declares a small body (or none) and
    sends a large one. The declared-length check cannot catch it, so the
    overrun must still be refused rather than parsed."""

    oversized = MODS_FOUND + "<!--" + "a" * (idlookup.MAX_BYTES + 64) + "-->"
    lying = xml_response(oversized, headers={"Content-Length": "12"})
    result = idlookup.lookup_lccn(FakeTransport([lying]), VALID_LCCN)
    assert result.outcome is idlookup.Outcome.UNAVAILABLE
    assert "size bound" in (result.detail or "")


def test_a_body_exactly_at_the_bound_is_still_accepted():
    """The bound is inclusive: reading one byte past it is how an overrun is
    detected, and must not make a body that exactly fills the bound look like
    one that exceeded it."""

    pad = idlookup.MAX_BYTES - len(MODS_FOUND.encode()) - len("<!---->")
    body = MODS_FOUND + "<!--" + "a" * pad + "-->"
    assert len(body.encode("utf-8")) == idlookup.MAX_BYTES
    result = idlookup.lookup_lccn(FakeTransport([xml_response(body)]), VALID_LCCN)
    assert result.outcome is not idlookup.Outcome.UNAVAILABLE
