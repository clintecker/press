"""The provider-neutral print adapter contract.

Every print provider is reached through the same typed operations and the
same normalized domain types. Three rules keep the contract honest:

- Money is integer minor units plus an ISO currency, parsed from a
  provider's decimal strings without ever touching a binary float.
- An unrecognized provider status maps to ``UNKNOWN``: the domain
  quarantines it and alerts rather than guessing a transition.
- A network timeout is an ``UnknownOutcome``, not a failure. The caller
  looks the order up by its stable external reference before it dares
  resubmit, so a lost response never prints a second copy. Adapters
  perform no hidden retries.

Capabilities a provider lacks are declared, never simulated: calling an
unsupported operation returns a typed ``unsupported`` error.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Protocol, runtime_checkable


class Capability(str, Enum):
    QUOTE = "quote"
    FILE_VALIDATION = "file_validation"
    SUBMIT = "submit"
    LOOKUP = "lookup"
    CANCELLATION = "cancellation"
    WEBHOOKS = "webhooks"


class ProviderStatus(str, Enum):
    """A normalized, provider-neutral fulfillment status. Every adapter maps
    its own vocabulary onto this; anything it does not recognize becomes
    ``UNKNOWN`` so the caller quarantines the observation."""

    CREATED = "created"
    ACCEPTED = "accepted"
    IN_PRODUCTION = "in_production"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    REJECTED = "rejected"
    CANCELED = "canceled"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Money:
    """An amount as integer minor units plus an ISO 4217 currency. Provider
    decimals are parsed through Decimal, never binary float, so a cent is
    never lost to representation error."""

    currency: str
    minor_units: int

    @classmethod
    def parse(cls, currency: str, amount: str | int | Decimal, *, exponent: int = 2) -> Money:
        scaled = (Decimal(str(amount)) * (10 ** exponent)).to_integral_value()
        return cls(currency.upper(), int(scaled))

    def __add__(self, other: Money) -> Money:
        if other.currency != self.currency:
            raise ValueError(f"cannot add {self.currency} and {other.currency}")
        return Money(self.currency, self.minor_units + other.minor_units)


@dataclass(frozen=True)
class Address:
    name: str
    street1: str
    city: str
    region: str  # state/province code, required by many destinations
    postcode: str
    country: str  # ISO 3166-1 alpha-2
    phone: str


@dataclass(frozen=True)
class LineItem:
    product_id: str  # the provider's SKU (a pod_package_id for Lulu)
    page_count: int
    quantity: int
    interior_url: str
    cover_url: str
    external_id: str = ""


@dataclass(frozen=True)
class QuoteRequest:
    line_items: tuple[LineItem, ...]
    address: Address
    shipping_level: str


@dataclass(frozen=True)
class Quote:
    currency: str
    line_cost: Money
    shipping_cost: Money
    tax: Money
    total: Money
    provider_ref: str
    capabilities: frozenset[Capability]


@dataclass(frozen=True)
class Submission:
    external_id: str  # a stable reference the caller owns, for dedup and lookup
    contact_email: str
    line_items: tuple[LineItem, ...]
    address: Address
    shipping_level: str


@dataclass(frozen=True)
class ProviderOrder:
    provider_ref: str
    external_id: str
    status: ProviderStatus
    raw_status: str  # the provider's own string, retained for audit
    tracking_urls: tuple[str, ...] = ()


# ---- outcomes: typed active signals, never exceptions for control flow ----

@dataclass(frozen=True)
class Accepted:
    order: ProviderOrder


@dataclass(frozen=True)
class Rejected:
    code: str
    detail: str


@dataclass(frozen=True)
class UnknownOutcome:
    """A timeout or ambiguous response: the submission may or may not have
    landed. The caller must look up by external reference before resubmit."""

    detail: str


SubmitResult = Accepted | Rejected | UnknownOutcome


@dataclass(frozen=True)
class TypedError:
    code: str
    detail: str
    retryable: bool = False


@dataclass(frozen=True)
class ProviderEvent:
    """A parsed provider webhook. ``authentic`` is the signature-verification
    result over the raw body; an inauthentic event carries no order and the
    reason it failed."""

    authentic: bool
    topic: str
    order: ProviderOrder | None = None
    reason: str = ""


def unsupported(capability: Capability) -> TypedError:
    return TypedError("unsupported", f"provider does not support {capability.value}")


@runtime_checkable
class PrintProvider(Protocol):  # pragma: no cover - a typed contract, no runnable body
    """The typed operations every print provider adapter implements. An
    operation for an unsupported capability returns ``unsupported(...)``
    rather than pretending."""

    name: str

    def capabilities(self) -> frozenset[Capability]: ...

    def quote(self, request: QuoteRequest) -> Quote | TypedError: ...

    def validate_files(self, items: tuple[LineItem, ...]) -> dict[str, list[str]] | TypedError: ...

    def submit(self, submission: Submission) -> SubmitResult: ...

    def get_order(self, provider_ref: str) -> ProviderOrder | TypedError: ...

    def cancel(self, provider_ref: str) -> ProviderOrder | TypedError: ...

    def parse_event(self, body: bytes, headers: dict[str, str]) -> ProviderEvent: ...

    def normalize_status(self, raw: str) -> ProviderStatus: ...


def supports(provider: PrintProvider, capability: Capability) -> bool:
    return capability in provider.capabilities()
