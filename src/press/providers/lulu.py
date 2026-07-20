"""The Lulu Print API adapter.

Maps the provider-neutral contract onto Lulu's public Print API
(developers.lulu.com): OAuth2 client-credentials auth, a landed cost
quote, a print-job submission, status lookup, cancellation, async
interior validation, and webhook verification. Lulu's own vocabulary --
its ``pod_package_id`` SKUs, its status words, its DRF error shapes --
stops here; the domain sees only normalized types.

Two Lulu facts are load-bearing and handled honestly. Lulu documents no
idempotency guarantee on order creation, so submit carries the caller's
``external_id`` and a lost response is an ``UnknownOutcome`` the caller
must resolve by lookup before resubmit -- the adapter never retries a
submission on its own. And Lulu signs webhooks with an
``Lulu-HMAC-SHA256`` header over the raw body keyed by the API secret,
which the adapter verifies against the exact bytes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

from .contract import (
    Accepted,
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
)
from .transport import Response, Transport, TransportError, TransportTimeout

PROD_BASE = "https://api.lulu.com"
SANDBOX_BASE = "https://api.sandbox.lulu.com"
_TOKEN_PATH = "/auth/realms/glasstree/protocol/openid-connect/token"

_CAPABILITIES = frozenset({
    Capability.QUOTE, Capability.FILE_VALIDATION, Capability.SUBMIT,
    Capability.LOOKUP, Capability.CANCELLATION, Capability.WEBHOOKS,
})

# Lulu's print-job status vocabulary, normalized. UNPAID and
# PAYMENT_IN_PROGRESS are pre-acceptance bookkeeping, so they map to
# CREATED; the two production-delay states mean the job is accepted and
# waiting out its cancellation window. Anything unlisted quarantines.
_STATUS = {
    "CREATED": ProviderStatus.CREATED,
    "UNPAID": ProviderStatus.CREATED,
    "PAYMENT_IN_PROGRESS": ProviderStatus.CREATED,
    "PRODUCTION_DELAYED": ProviderStatus.ACCEPTED,
    "PRODUCTION_READY": ProviderStatus.ACCEPTED,
    "IN_PRODUCTION": ProviderStatus.IN_PRODUCTION,
    "SHIPPED": ProviderStatus.SHIPPED,
    "DELIVERED": ProviderStatus.DELIVERED,
    "REJECTED": ProviderStatus.REJECTED,
    "CANCELED": ProviderStatus.CANCELED,
    "ERROR": ProviderStatus.ERROR,
}


def pod_package_id(trim_width_in: float, trim_height_in: float, *, color: str = "BW",
                   quality: str = "STD", binding: str = "PB", paper: str = "060UW444",
                   finish: str = "MXX") -> str:
    """A Lulu SKU in the dotted form (live since 2026-03-31). The six
    segments are trim, ink, print quality, binding, paper, and cover
    finish. The trim is width x height in hundredths of an inch, so a 6x9
    is ``0600X0900``. The exhaustive value tables are Lulu's product
    spec sheet; validate a constructed SKU against the API rather than
    trusting a hand-built one for an unusual book."""

    trim = f"{round(trim_width_in * 100):04d}X{round(trim_height_in * 100):04d}"
    return ".".join((trim, color, quality, binding, paper, finish))


class LuluProvider:
    name = "lulu"

    def __init__(self, transport: Transport, *, client_key: str, client_secret: str,
                 sandbox: bool = True, webhook_secret: str = "") -> None:
        self._t = transport
        self._base = SANDBOX_BASE if sandbox else PROD_BASE
        self._basic = base64.b64encode(
            f"{client_key}:{client_secret}".encode("utf-8")).decode("ascii")
        self._webhook_secret = webhook_secret.encode("utf-8")
        self._token: str | None = None

    # ---- auth + request plumbing ----

    def _access_token(self) -> str:
        if self._token is not None:
            return self._token
        response = self._t(
            "POST", self._base + _TOKEN_PATH,
            headers={"Authorization": f"Basic {self._basic}",
                     "Content-Type": "application/x-www-form-urlencoded"},
            body=b"grant_type=client_credentials")
        self._token = str(response.json()["access_token"])
        return self._token

    def _request(self, method: str, path: str, payload: dict | None = None) -> Response:
        response = self._t(
            method, self._base + path,
            headers={"Authorization": f"Bearer {self._access_token()}",
                     "Content-Type": "application/json"},
            body=json.dumps(payload).encode("utf-8") if payload is not None else None)
        if response.status == 401:
            # The token expired; fetch a fresh one once and retry (this is
            # token renewal, not a hidden business retry).
            self._token = None
            response = self._t(
                method, self._base + path,
                headers={"Authorization": f"Bearer {self._access_token()}",
                         "Content-Type": "application/json"},
                body=json.dumps(payload).encode("utf-8") if payload is not None else None)
        return response

    @staticmethod
    def _error_detail(response: Response) -> str:
        try:
            body = response.json()
        except (ValueError, KeyError):
            return f"HTTP {response.status}"
        if isinstance(body, dict) and "detail" in body:
            return str(body["detail"])
        if isinstance(body, dict):
            return "; ".join(f"{k}: {', '.join(v) if isinstance(v, list) else v}"
                             for k, v in body.items())
        if isinstance(body, list):
            return "; ".join(str(x) for x in body)
        return f"HTTP {response.status}"

    # ---- the contract ----

    def capabilities(self) -> frozenset[Capability]:
        return _CAPABILITIES

    def _line_payload(self, item: LineItem) -> dict:
        return {
            "external_id": item.external_id,
            "quantity": item.quantity,
            "printable_normalization": {
                "pod_package_id": item.product_id,
                "interior": {"source_url": item.interior_url},
                "cover": {"source_url": item.cover_url},
            },
        }

    def _address_payload(self, address, *, with_name: bool) -> dict:
        data = {
            "street1": address.street1, "city": address.city,
            "country_code": address.country, "postcode": address.postcode,
            "state_code": address.region, "phone_number": address.phone,
        }
        if with_name:
            data["name"] = address.name
        return data

    def quote(self, request: QuoteRequest) -> Quote | TypedError:
        payload = {
            "line_items": [{"page_count": i.page_count, "pod_package_id": i.product_id,
                            "quantity": i.quantity} for i in request.line_items],
            "shipping_address": self._address_payload(request.address, with_name=False),
            "shipping_option": request.shipping_level,
        }
        try:
            response = self._request("POST", "/print-job-cost-calculations/", payload)
        except (TransportTimeout, TransportError) as exc:
            return TypedError("transport", str(exc), retryable=True)
        if response.status not in (200, 201):
            return TypedError("quote_failed", self._error_detail(response))
        body = response.json()
        currency = str(body.get("currency", "USD"))
        line = Money.parse(currency, _sum_decimal(body.get("line_item_costs", []),
                                                  "total_cost_incl_tax"))
        shipping = Money.parse(currency, body.get("shipping_cost", {}).get("total_cost_incl_tax", "0"))
        tax = Money.parse(currency, body.get("total_tax", "0"))
        total = Money.parse(currency, body.get("total_cost_incl_tax", "0"))
        return Quote(currency, line, shipping, tax, total, "lulu-cost-calc", _CAPABILITIES)

    def validate_files(self, items: tuple[LineItem, ...]) -> dict[str, list[str]] | TypedError:
        problems: dict[str, list[str]] = {}
        for item in items:
            payload = {"source_url": item.interior_url, "pod_package_id": item.product_id}
            try:
                response = self._request("POST", "/validate-interior/", payload)
            except (TransportTimeout, TransportError) as exc:
                return TypedError("transport", str(exc), retryable=True)
            if response.status not in (200, 201):
                problems[item.external_id or item.product_id] = [self._error_detail(response)]
                continue
            errors = response.json().get("errors") or []
            if errors:
                problems[item.external_id or item.product_id] = [str(e) for e in errors]
        return problems

    def submit(self, submission: Submission) -> SubmitResult:
        payload = {
            "contact_email": submission.contact_email,
            "external_id": submission.external_id,
            "shipping_level": submission.shipping_level,
            "line_items": [self._line_payload(i) for i in submission.line_items],
            "shipping_address": self._address_payload(submission.address, with_name=True),
        }
        try:
            response = self._request("POST", "/print-jobs/", payload)
        except TransportTimeout:
            # The job may have been created; the caller must look up by
            # external_id before any resubmission. Never assume it failed.
            return UnknownOutcome(
                f"timeout submitting {submission.external_id!r}; "
                "look up by external reference before resubmitting")
        except TransportError as exc:
            return UnknownOutcome(f"transport error, outcome unknown: {exc}")
        if response.status not in (200, 201):
            return Rejected(f"http_{response.status}", self._error_detail(response))
        return Accepted(self._order_from(response.json()))

    def get_order(self, provider_ref: str) -> ProviderOrder | TypedError:
        try:
            response = self._request("GET", f"/print-jobs/{provider_ref}/")
        except (TransportTimeout, TransportError) as exc:
            return TypedError("transport", str(exc), retryable=True)
        if response.status == 404:
            return TypedError("not_found", f"no print job {provider_ref!r}")
        if response.status != 200:
            return TypedError("lookup_failed", self._error_detail(response))
        return self._order_from(response.json())

    def cancel(self, provider_ref: str) -> ProviderOrder | TypedError:
        # The spec declares PUT but every code sample uses POST; POST is the
        # safer bet. Cancellation is only valid pre-production.
        try:
            response = self._request("POST", f"/print-jobs/{provider_ref}/status/",
                                     {"name": "CANCELED"})
        except (TransportTimeout, TransportError) as exc:
            return TypedError("transport", str(exc), retryable=True)
        if response.status not in (200, 201):
            return TypedError("not_cancelable", self._error_detail(response))
        return self.get_order(provider_ref)

    def parse_event(self, body: bytes, headers: dict[str, str]) -> ProviderEvent:
        signature = headers.get("Lulu-HMAC-SHA256", "")
        expected = hmac.new(self._webhook_secret, body, hashlib.sha256).hexdigest()
        if not signature or not hmac.compare_digest(signature, expected):
            return ProviderEvent(False, "", None, "Lulu-HMAC-SHA256 does not match the raw body")
        payload = json.loads(body.decode("utf-8"))
        job = payload.get("data") or {}
        return ProviderEvent(True, str(payload.get("topic", "")), self._order_from(job))

    def normalize_status(self, raw: str) -> ProviderStatus:
        return _STATUS.get(raw.strip().upper(), ProviderStatus.UNKNOWN)

    def _order_from(self, job: dict) -> ProviderOrder:
        raw = str((job.get("status") or {}).get("name", ""))
        tracking: list[str] = []
        for line in job.get("line_items", []):
            tracking.extend(line.get("tracking_urls") or [])
        return ProviderOrder(
            provider_ref=str(job.get("id", "")),
            external_id=str(job.get("external_id", "")),
            status=self.normalize_status(raw), raw_status=raw,
            tracking_urls=tuple(tracking))


def _sum_decimal(rows: list[dict], key: str) -> str:
    from decimal import Decimal

    total = Decimal("0")
    for row in rows:
        total += Decimal(str(row.get(key, "0")))
    return str(total)
