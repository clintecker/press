"""A stateful smart fake print provider.

The fake is the reference against which the conformance suite is written,
and the substitute every other test uses in place of a real provider. It
is deterministic -- order references come from an injected counter, never
a clock or randomness -- and it can be scripted to produce the outcomes a
real provider produces: acceptance, rejection, a timeout (unknown
outcome), a duplicate submission, an out-of-order or unknown status, and
a signed or tampered webhook. It keeps real order state so a lookup after
a submit returns what was submitted.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from itertools import count
from typing import Iterator

from .contract import (
    Accepted,
    Address,
    Capability,
    LineItem,
    Money,
    ProviderEvent,
    ProviderOrder,
    ProviderStatus,
    Quote,
    QuoteRequest,
    Rejected,
    Submission,
    SubmitResult,
    TypedError,
    UnknownOutcome,
    unsupported,
)

_ALL = frozenset(Capability)

# The fake's own status words, and how they normalize. An unlisted word
# becomes UNKNOWN, exactly as a real adapter must quarantine one.
_STATUS = {
    "created": ProviderStatus.CREATED,
    "accepted": ProviderStatus.ACCEPTED,
    "in_production": ProviderStatus.IN_PRODUCTION,
    "shipped": ProviderStatus.SHIPPED,
    "delivered": ProviderStatus.DELIVERED,
    "rejected": ProviderStatus.REJECTED,
    "canceled": ProviderStatus.CANCELED,
    "error": ProviderStatus.ERROR,
}


class FakeProvider:
    name = "fake"

    def __init__(self, *, capabilities: frozenset[Capability] = _ALL,
                 refs: Iterator[str] | None = None, secret: bytes = b"fake-secret") -> None:
        self._caps = capabilities
        self._refs = refs or (f"fake-{n}" for n in count(1))
        self._secret = secret
        self._orders: dict[str, ProviderOrder] = {}
        self._raw_status: dict[str, str] = {}
        self._submit_script: list[str] = []  # queued outcomes: accept|reject|timeout|duplicate

    # ---- scripting hooks (test-facing) ----

    def script_submit(self, *outcomes: str) -> None:
        self._submit_script.extend(outcomes)

    def advance(self, provider_ref: str, raw_status: str) -> None:
        order = self._orders[provider_ref]
        self._raw_status[provider_ref] = raw_status
        self._orders[provider_ref] = ProviderOrder(
            provider_ref=order.provider_ref, external_id=order.external_id,
            status=self.normalize_status(raw_status), raw_status=raw_status,
            tracking_urls=order.tracking_urls)

    def sign(self, body: bytes) -> str:
        return hmac.new(self._secret, body, hashlib.sha256).hexdigest()

    # ---- the contract ----

    def capabilities(self) -> frozenset[Capability]:
        return self._caps

    def quote(self, request: QuoteRequest) -> Quote | TypedError:
        if Capability.QUOTE not in self._caps:
            return unsupported(Capability.QUOTE)
        units = sum(item.quantity for item in request.line_items)
        line = Money("USD", 1500 * units)
        shipping = Money("USD", 500)
        tax = Money("USD", (line.minor_units + shipping.minor_units) // 10)
        total = Money("USD", line.minor_units + shipping.minor_units + tax.minor_units)
        return Quote("USD", line, shipping, tax, total, "fake-quote", self._caps)

    def validate_files(self, items: tuple[LineItem, ...]) -> dict[str, list[str]] | TypedError:
        if Capability.FILE_VALIDATION not in self._caps:
            return unsupported(Capability.FILE_VALIDATION)
        problems: dict[str, list[str]] = {}
        for item in items:
            issues = []
            if not item.interior_url.startswith("https://"):
                issues.append("interior url is not https")
            if not item.cover_url.startswith("https://"):
                issues.append("cover url is not https")
            if issues:
                problems[item.external_id or item.product_id] = issues
        return problems

    def submit(self, submission: Submission) -> SubmitResult:
        if Capability.SUBMIT not in self._caps:
            return UnknownOutcome("submit is not supported")  # never fabricate an accept
        outcome = self._submit_script.pop(0) if self._submit_script else "accept"
        if outcome == "timeout":
            return UnknownOutcome("network timeout; look up by external reference")
        if outcome == "reject":
            return Rejected("rejected", "the fake was scripted to reject this submission")
        ref = next(self._refs)
        order = ProviderOrder(ref, submission.external_id, ProviderStatus.CREATED, "created")
        self._orders[ref] = order
        self._raw_status[ref] = "created"
        return Accepted(order)

    def get_order(self, provider_ref: str) -> ProviderOrder | TypedError:
        order = self._orders.get(provider_ref)
        if order is None:
            return TypedError("not_found", f"no order {provider_ref!r}")
        return order

    def find_by_external(self, external_id: str) -> ProviderOrder | None:
        for order in self._orders.values():
            if order.external_id == external_id:
                return order
        return None

    def cancel(self, provider_ref: str) -> ProviderOrder | TypedError:
        if Capability.CANCELLATION not in self._caps:
            return unsupported(Capability.CANCELLATION)
        order = self._orders.get(provider_ref)
        if order is None:
            return TypedError("not_found", f"no order {provider_ref!r}")
        if order.status in (ProviderStatus.IN_PRODUCTION, ProviderStatus.SHIPPED,
                            ProviderStatus.DELIVERED):
            return TypedError("not_cancelable", f"cannot cancel a {order.status.value} order")
        self.advance(provider_ref, "canceled")
        return self._orders[provider_ref]

    def parse_event(self, body: bytes, headers: dict[str, str]) -> ProviderEvent:
        if Capability.WEBHOOKS not in self._caps:
            return ProviderEvent(False, "", None, "provider does not support webhooks")
        signature = headers.get("X-Fake-Signature", "")
        if not hmac.compare_digest(signature, self.sign(body)):
            return ProviderEvent(False, "", None, "signature does not match the raw body")
        payload = json.loads(body.decode("utf-8"))
        ref = str(payload.get("provider_ref", ""))
        order = self._orders.get(ref)
        return ProviderEvent(True, str(payload.get("topic", "")), order)

    def normalize_status(self, raw: str) -> ProviderStatus:
        return _STATUS.get(raw.strip().lower(), ProviderStatus.UNKNOWN)


def sample_submission(external_id: str = "order-1") -> Submission:
    """A ready-made submission for tests and the conformance suite."""

    item = LineItem("SKU-6X9-BW", 120, 1,
                    "https://example.test/interior.pdf",
                    "https://example.test/cover.pdf", external_id="item-1")
    address = Address("A Reader", "1 Main St", "Springfield", "IL", "62704", "US",
                      "555-0100")
    return Submission(external_id, "owner@example.test", (item,), address, "GROUND")
