"""The provider conformance suite: one set of behaviours every print
adapter must satisfy, run against both the smart fake and the Lulu
adapter driven by a canned transport. Plus adapter-specific proofs (the
fake's scripting, Lulu's SKU/status/HMAC/error mapping and its
timeout-is-unknown rule) and fuzz over hostile provider strings.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from press.providers import contract, fake as fake_mod, lulu as lulu_mod
from press.providers.transport import (
    CannedTransport,
    Response,
    TransportTimeout,
)

C = contract.Capability


# ---- adapter factories for the shared suite ----

def _make_fake():
    return fake_mod.FakeProvider()


_JOB = {
    "id": 42776, "external_id": "order-1", "status": {"name": "CREATED"},
    "line_items": [{"id": 1, "tracking_urls": []}],
}


def _lulu_routes():
    return {
        ("POST", "/openid-connect/token"): Response(
            200, json.dumps({"access_token": "tok", "expires_in": 3600}).encode()),
        ("POST", "/print-job-cost-calculations/"): Response(201, json.dumps({
            "currency": "USD",
            "line_item_costs": [{"total_cost_incl_tax": "15.00"}],
            "shipping_cost": {"total_cost_incl_tax": "5.00"},
            "total_tax": "2.00", "total_cost_incl_tax": "22.00"}).encode()),
        ("POST", "/print-jobs/"): Response(201, json.dumps(_JOB).encode()),
        ("GET", "/print-jobs/42776/"): Response(200, json.dumps(_JOB).encode()),
        ("POST", "/print-jobs/42776/status/"): Response(
            200, json.dumps({"name": "CANCELED"}).encode()),
        ("POST", "/validate-interior/"): Response(
            201, json.dumps({"id": 1, "errors": []}).encode()),
    }


def _make_lulu(transport=None):
    return lulu_mod.LuluProvider(
        transport or CannedTransport(_lulu_routes()),
        client_key="k", client_secret="s", sandbox=True, webhook_secret="whsec")


ADAPTERS = [("fake", _make_fake), ("lulu", _make_lulu)]


@pytest.fixture(params=ADAPTERS, ids=[name for name, _ in ADAPTERS])
def provider(request):
    return request.param[1]()


# ---- the shared contract ----

def test_capabilities_are_a_frozenset_of_capabilities(provider):
    caps = provider.capabilities()
    assert isinstance(caps, frozenset)
    assert all(isinstance(c, contract.Capability) for c in caps)


def test_quote_returns_integer_minor_units(provider):
    quote = provider.quote(_quote_request())
    assert isinstance(quote, contract.Quote)
    assert isinstance(quote.total.minor_units, int)
    assert quote.total.minor_units > 0
    # The total is at least the item plus shipping (no float drift).
    assert quote.total.minor_units >= quote.line_cost.minor_units + quote.shipping_cost.minor_units


def test_submit_then_lookup_round_trips(provider):
    result = provider.submit(fake_mod.sample_submission())
    assert isinstance(result, contract.Accepted)
    assert result.order.provider_ref
    fetched = provider.get_order(result.order.provider_ref)
    assert isinstance(fetched, contract.ProviderOrder)
    assert fetched.provider_ref == result.order.provider_ref


def test_an_unknown_status_string_quarantines(provider):
    assert provider.normalize_status("a-status-no-one-defined") == contract.ProviderStatus.UNKNOWN


def test_a_valid_event_is_authentic_a_tampered_one_is_not(provider):
    body = json.dumps({"topic": "PRINT_JOB_STATUS_CHANGED",
                       "provider_ref": "x", "data": _JOB}).encode()
    headers = _sign(provider, body)
    assert provider.parse_event(body, headers).authentic
    assert not provider.parse_event(body + b"tampered", headers).authentic


def _sign(provider, body: bytes) -> dict[str, str]:
    if provider.name == "fake":
        return {"X-Fake-Signature": provider.sign(body)}
    sig = hmac.new(b"whsec", body, hashlib.sha256).hexdigest()
    return {"Lulu-HMAC-SHA256": sig}


def _quote_request():
    return contract.QuoteRequest(
        line_items=(contract.LineItem("SKU", 120, 2,
                                      "https://e.test/i.pdf", "https://e.test/c.pdf"),),
        address=contract.Address("R", "1 St", "City", "IL", "62704", "US", "555"),
        shipping_level="GROUND")


# ---- the fake's scripting ----

def test_fake_scripts_rejection_and_timeout():
    provider = fake_mod.FakeProvider()
    provider.script_submit("reject", "timeout")
    assert isinstance(provider.submit(fake_mod.sample_submission()), contract.Rejected)
    assert isinstance(provider.submit(fake_mod.sample_submission()), contract.UnknownOutcome)


def test_fake_validates_files_and_declares_unsupported_validation():
    item = contract.LineItem(
        "SKU", 120, 1, "http://unsafe/interior.pdf", "relative-cover.pdf",
        external_id="line-1")
    provider = fake_mod.FakeProvider()
    assert provider.validate_files((item,)) == {
        "line-1": ["interior url is not https", "cover url is not https"]}

    without_validation = fake_mod.FakeProvider(
        capabilities=frozenset({C.SUBMIT}))
    result = without_validation.validate_files((item,))
    assert isinstance(result, contract.TypedError)
    assert result.code == "unsupported"


def test_fake_lookup_progression_and_cancellation_are_stateful():
    provider = fake_mod.FakeProvider()
    accepted = provider.submit(fake_mod.sample_submission("external-7"))
    assert isinstance(accepted, contract.Accepted)
    ref = accepted.order.provider_ref

    assert provider.find_by_external("external-7") == accepted.order
    assert provider.find_by_external("absent") is None
    assert isinstance(provider.get_order("absent"), contract.TypedError)

    provider.advance(ref, "accepted")
    canceled = provider.cancel(ref)
    assert isinstance(canceled, contract.ProviderOrder)
    assert canceled.status is contract.ProviderStatus.CANCELED


def test_fake_refuses_late_cancellation_and_unsupported_boundaries():
    provider = fake_mod.FakeProvider()
    accepted = provider.submit(fake_mod.sample_submission())
    assert isinstance(accepted, contract.Accepted)
    provider.advance(accepted.order.provider_ref, "in_production")
    late = provider.cancel(accepted.order.provider_ref)
    assert isinstance(late, contract.TypedError)
    assert late.code == "not_cancelable"
    assert isinstance(provider.cancel("absent"), contract.TypedError)

    lookup_only = fake_mod.FakeProvider(
        capabilities=frozenset({C.LOOKUP}))
    assert isinstance(
        lookup_only.submit(fake_mod.sample_submission()), contract.UnknownOutcome)
    event = lookup_only.parse_event(b"{}", {})
    assert event.authentic is False
    assert "does not support webhooks" in event.reason


@pytest.mark.invariant("INV-provider-contract")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_an_unsupported_capability_is_declared_not_simulated():
    provider = fake_mod.FakeProvider(capabilities=frozenset({C.SUBMIT, C.LOOKUP}))
    result = provider.cancel("fake-1")
    assert isinstance(result, contract.TypedError)
    assert result.code == "unsupported"


# ---- Lulu specifics ----

def test_lulu_pod_package_id_for_6x9_bw_paperback():
    assert lulu_mod.pod_package_id(6.0, 9.0) == "0600X0900.BW.STD.PB.060UW444.MXX"
    assert lulu_mod.pod_package_id(6.0, 9.0, paper="060UC444") == "0600X0900.BW.STD.PB.060UC444.MXX"


@pytest.mark.parametrize("raw,expected", [
    ("CREATED", contract.ProviderStatus.CREATED),
    ("UNPAID", contract.ProviderStatus.CREATED),
    ("PRODUCTION_DELAYED", contract.ProviderStatus.ACCEPTED),
    ("IN_PRODUCTION", contract.ProviderStatus.IN_PRODUCTION),
    ("SHIPPED", contract.ProviderStatus.SHIPPED),
    ("REJECTED", contract.ProviderStatus.REJECTED),
    ("CANCELED", contract.ProviderStatus.CANCELED),
    ("SOMETHING_NEW", contract.ProviderStatus.UNKNOWN),
])
def test_lulu_status_normalization(raw, expected):
    assert _make_lulu().normalize_status(raw) == expected


def test_lulu_submit_sends_the_documented_request_shape():
    transport = CannedTransport(_lulu_routes())
    provider = _make_lulu(transport)
    provider.submit(fake_mod.sample_submission("order-9"))
    submit_call = next(c for c in transport.calls if c["url"].endswith("/print-jobs/"))
    body = json.loads(submit_call["body"])
    assert body["external_id"] == "order-9"
    assert body["contact_email"]
    assert body["shipping_level"] == "GROUND"
    item = body["line_items"][0]
    assert item["printable_normalization"]["pod_package_id"]
    assert item["printable_normalization"]["interior"]["source_url"].startswith("https://")


@pytest.mark.invariant("INV-provider-contract")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_lulu_submit_timeout_is_an_unknown_outcome():
    transport = CannedTransport(_lulu_routes())
    # Auth succeeds, then the submit POST times out.
    provider = _make_lulu(transport)
    provider._access_token()  # prime the token so the timeout hits the submit
    transport.fail_next = TransportTimeout("connection timed out")
    result = provider.submit(fake_mod.sample_submission())
    assert isinstance(result, contract.UnknownOutcome)
    assert "look up by external reference" in result.detail


def test_lulu_parses_both_drf_error_shapes():
    detail = lulu_mod.LuluProvider._error_detail(
        Response(401, json.dumps({"detail": "Authentication credentials were not provided."}).encode()))
    assert "Authentication" in detail
    field = lulu_mod.LuluProvider._error_detail(
        Response(400, json.dumps({"url": ["Enter a valid URL."]}).encode()))
    assert "url" in field and "valid URL" in field


def test_lulu_rejected_submission_is_a_typed_rejection():
    routes = _lulu_routes()
    routes[("POST", "/print-jobs/")] = Response(
        400, json.dumps({"line_items": ["This field is required."]}).encode())
    result = _make_lulu(CannedTransport(routes)).submit(fake_mod.sample_submission())
    assert isinstance(result, contract.Rejected)
    assert "required" in result.detail


# ---- money and fuzz ----

@pytest.mark.invariant("INV-provider-contract")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_money_refuses_mixed_currencies():
    with pytest.raises(ValueError, match="cannot add"):
        contract.Money("USD", 100) + contract.Money("EUR", 100)


def test_supports_reports_capability_membership():
    provider = fake_mod.FakeProvider(capabilities=frozenset({C.QUOTE}))
    assert contract.supports(provider, C.QUOTE)
    assert not contract.supports(provider, C.SUBMIT)


@pytest.mark.invariant("INV-provider-contract")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_money_parses_decimals_without_float_error():
    assert contract.Money.parse("USD", "19.99").minor_units == 1999
    assert contract.Money.parse("USD", "0.10").minor_units == 10
    # The classic float trap: 0.1 + 0.2 in cents is exactly 30.
    assert (contract.Money.parse("USD", "0.1") + contract.Money.parse("USD", "0.2")).minor_units == 30


@given(raw=st.text(max_size=40))
@pytest.mark.invariant("INV-provider-contract")
@pytest.mark.layer("property")
@pytest.mark.proof("positive")
def test_normalize_status_never_raises_on_hostile_input(raw):
    assert isinstance(_make_lulu().normalize_status(raw), contract.ProviderStatus)


@given(body=st.binary(max_size=200))
@pytest.mark.invariant("INV-provider-contract")
@pytest.mark.layer("property")
@pytest.mark.proof("negative")
def test_parse_event_never_crashes_on_hostile_body(body):
    # A hostile or unsigned body is inauthentic, never an exception.
    event = _make_lulu().parse_event(body, {"Lulu-HMAC-SHA256": "deadbeef"})
    assert event.authentic is False
