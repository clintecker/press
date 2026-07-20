"""Direct print-ordering: the reader-facing "Order a print copy" control.

A book site needs a way for a reader to buy a physical copy, but a static
page must hold no secret, no trusted price, no mutable artifact URL, and
no provider workflow. Under the seller-of-record model the control is, by
design, the simplest safe thing: a marked-up link to the provider's
hosted checkout. It carries no JavaScript, so it works with a keyboard, a
screen reader, and no script at all; it is CSP-compatible; and returning
from checkout can never make it claim "paid", because it never tracks
payment -- the provider does.

Everything here is declarative and secret-free. A book declares a
``commerce.print-ordering`` block (whether ordering is enabled, which
edition, the HTTPS storefront URL, who the seller of record is, and the
policy links); provider accounts, credentials, and prices never enter the
book repository. The verifier refuses an enabled block that is missing a
policy link, points at a non-HTTPS origin, or carries anything that looks
like a secret.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

# Values that must never appear in a book's commerce config: the block
# holds URLs and a seller name, never a credential.
_SECRET_MARKERS = re.compile(
    r"(sk_live|sk_test|rk_live|bearer\s|api[_-]?key|secret|password|"
    r"[?&](token|key|apikey|password|secret)=)", re.IGNORECASE)

_POLICY_LINKS = ("support_url", "privacy_url", "refund_url")


@dataclass(frozen=True)
class CommerceConfig:
    enabled: bool
    edition: str
    storefront_url: str
    seller_of_record: str
    support_url: str
    privacy_url: str
    refund_url: str
    extra_keys: tuple[str, ...] = field(default_factory=tuple)

    def policy_links(self) -> list[tuple[str, str]]:
        return [("Support", self.support_url), ("Privacy", self.privacy_url),
                ("Refunds", self.refund_url)]


_KNOWN_KEYS = {
    "enabled", "edition", "storefront-url", "seller-of-record", "support-url",
    "privacy-url", "refund-url",
}


def load(metadata: dict | None) -> CommerceConfig | None:
    """The commerce config from a book's metadata, or None if the book
    declares no ``commerce.print-ordering`` block."""

    commerce = (metadata or {}).get("commerce")
    if not isinstance(commerce, dict):
        return None
    block = commerce.get("print-ordering")
    if not isinstance(block, dict):
        return None
    return CommerceConfig(
        enabled=bool(block.get("enabled", False)),
        edition=str(block.get("edition", "")),
        storefront_url=str(block.get("storefront-url", "")),
        seller_of_record=str(block.get("seller-of-record", "")),
        support_url=str(block.get("support-url", "")),
        privacy_url=str(block.get("privacy-url", "")),
        refund_url=str(block.get("refund-url", "")),
        extra_keys=tuple(sorted(set(block) - _KNOWN_KEYS)))


def _is_https(url: str) -> bool:
    return url.startswith("https://") and len(url) > len("https://")


def validate(config: CommerceConfig | None) -> list[str]:
    """Every defect in a commerce config. A disabled or absent block is
    silent (no CTA is emitted); an enabled block must name an HTTPS
    storefront, an explicit seller of record, and complete HTTPS policy
    links, and may carry no secret and no unknown key."""

    if config is None or not config.enabled:
        return []
    problems: list[str] = []
    if not config.edition:
        problems.append("commerce: enabled but no edition named")
    if not config.storefront_url:
        problems.append("commerce: enabled but no storefront-url")
    elif not _is_https(config.storefront_url):
        problems.append("commerce: storefront-url must be https")
    if not config.seller_of_record:
        problems.append(
            "commerce: seller-of-record must be named explicitly ("
            "a hosted checkout does not imply who the legal seller is)")
    for name in _POLICY_LINKS:
        value = getattr(config, name)
        label = name.replace("_", "-")
        if not value:
            problems.append(f"commerce: {label} is required when ordering is enabled")
        elif not _is_https(value):
            problems.append(f"commerce: {label} must be https")
    for name in ("storefront_url", "support_url", "privacy_url", "refund_url",
                 "seller_of_record"):
        if _SECRET_MARKERS.search(getattr(config, name)):
            problems.append(
                f"commerce: {name.replace('_', '-')} looks like it carries a "
                "secret; a book repository holds no credentials")
    if config.extra_keys:
        problems.append(f"commerce: unknown key(s) {list(config.extra_keys)}")
    return problems


def failures() -> list[str]:
    """The commerce config defects for ``press check``, read from the
    book's metadata. Empty when no block is declared or ordering is off."""

    from . import booklib

    return validate(load(booklib.metadata()))


def should_emit(config: CommerceConfig | None, *, sellable: bool) -> bool:
    """The release-gate predicate: an enabled, valid config may ship only
    for a verified sellable edition (from the edition manifest). The site
    build renders the configured link; this is the stricter gate the
    release check applies before a book advertises ordering."""

    return bool(config and config.enabled and not validate(config) and sellable)


def render_cta(config: CommerceConfig) -> str:
    """The accessible print-order control: a marked-up link to the hosted
    checkout, with the seller-of-record disclosed before the reader
    leaves the site, and the policy links. No script, CSP-safe."""

    e = html.escape
    seller = e(config.seller_of_record)
    links = " · ".join(
        f'<a href="{e(url)}">{e(label)}</a>' for label, url in config.policy_links())
    return (
        '<aside class="print-order" aria-labelledby="print-order-heading">\n'
        '  <h2 id="print-order-heading">Order a print copy</h2>\n'
        f'  <p class="print-order-lede">A print edition, sold and fulfilled by '
        f'{seller}.</p>\n'
        f'  <a class="print-order-cta" href="{e(config.storefront_url)}" '
        'rel="noopener noreferrer">Order a print copy</a>\n'
        f'  <p class="print-order-disclosure">You will complete your order on '
        f"{seller}'s secure checkout; they are the seller of record.</p>\n"
        f'  <p class="print-order-policy">{links}</p>\n'
        '</aside>'
    )


def render(config: CommerceConfig | None) -> str:
    """The commerce block for the site: the ordering CTA when ordering is
    enabled and the config is valid, else empty. A misconfigured block
    emits nothing rather than a broken link; ``press check`` reports the
    misconfiguration so it is never silent."""

    if config is None or not config.enabled or validate(config):
        return ""
    return render_cta(config)
