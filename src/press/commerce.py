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

# The three policy pages an ordering-enabled book must link. Each maps to
# its config-url field, a heading, and the page filename press generates
# when the publisher supplies no url of their own.
POLICY_KINDS = {
    "support": ("support_url", "Support", "Support for print orders", "support.html"),
    "privacy": ("privacy_url", "Privacy", "Privacy for print orders", "privacy.html"),
    "refund": ("refund_url", "Returns & refunds", "Returns and refunds for print orders",
               "refunds.html"),
}
_POLICY_LINKS = tuple(spec[0] for spec in POLICY_KINDS.values())


@dataclass(frozen=True)
class CommerceConfig:
    enabled: bool
    edition: str
    storefront_url: str
    seller_of_record: str
    support_url: str
    privacy_url: str
    refund_url: str
    policies: dict[str, str] = field(default_factory=dict)
    extra_keys: tuple[str, ...] = field(default_factory=tuple)

    def policy_href(self, kind: str) -> str:
        """Where the CTA's policy link points: the publisher's own url when
        given, else the page press generates on the book site."""

        field_name, _, _, filename = POLICY_KINDS[kind]
        return getattr(self, field_name) or filename

    def policy_links(self) -> list[tuple[str, str]]:
        return [(spec[1], self.policy_href(kind))
                for kind, spec in POLICY_KINDS.items()]

    def generated_kinds(self) -> list[str]:
        """The policy pages press must generate: those with no external url."""

        return [kind for kind, spec in POLICY_KINDS.items()
                if not getattr(self, spec[0])]


_KNOWN_KEYS = {
    "enabled", "edition", "storefront-url", "seller-of-record", "support-url",
    "privacy-url", "refund-url", "policies",
}
_POLICY_TEXT_KEYS = set(POLICY_KINDS)


def load(metadata: dict | None) -> CommerceConfig | None:
    """The commerce config from a book's metadata, or None if the book
    declares no ``commerce.print-ordering`` block."""

    commerce = (metadata or {}).get("commerce")
    if not isinstance(commerce, dict):
        return None
    block = commerce.get("print-ordering")
    if not isinstance(block, dict):
        return None
    policies = block.get("policies")
    return CommerceConfig(
        enabled=bool(block.get("enabled", False)),
        edition=str(block.get("edition", "")),
        storefront_url=str(block.get("storefront-url", "")),
        seller_of_record=str(block.get("seller-of-record", "")),
        support_url=str(block.get("support-url", "")),
        privacy_url=str(block.get("privacy-url", "")),
        refund_url=str(block.get("refund-url", "")),
        policies={str(k): str(v) for k, v in policies.items()}
        if isinstance(policies, dict) else {},
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
    # A policy url is optional: supply one to link your own hosted page, or
    # omit it and press generates the page. When supplied it must be https.
    for name in _POLICY_LINKS:
        value = getattr(config, name)
        if value and not _is_https(value):
            problems.append(f"commerce: {name.replace('_', '-')} must be https")
    unknown_policies = set(config.policies) - _POLICY_TEXT_KEYS
    if unknown_policies:
        problems.append(
            f"commerce: policies has unknown key(s) {sorted(unknown_policies)}; "
            f"expected {sorted(_POLICY_TEXT_KEYS)}")
    secret_fields = ["storefront_url", "support_url", "privacy_url", "refund_url",
                     "seller_of_record"]
    for name in secret_fields:
        if _SECRET_MARKERS.search(getattr(config, name)):
            problems.append(
                f"commerce: {name.replace('_', '-')} looks like it carries a "
                "secret; a book repository holds no credentials")
    for kind, text in config.policies.items():
        if _SECRET_MARKERS.search(text):
            problems.append(f"commerce: policies.{kind} looks like it carries a secret")
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


def render_policy_body(config: CommerceConfig, publisher: str, kind: str) -> str:
    """The body of a generated policy page: honest facts press can state --
    who the seller of record is and what they handle -- plus the
    publisher's own text, never invented legal terms."""

    e = html.escape
    seller = e(config.seller_of_record)
    pub = e(publisher) or "the publisher"
    heading = POLICY_KINDS[kind][2]
    paras = [f"<h1>{e(heading)}</h1>"]
    if kind == "support":
        paras.append(
            f"<p>This edition is printed, sold, and fulfilled by {seller}. For a "
            f"question about an order -- payment, shipping, or delivery -- contact "
            f"{seller} through their support channels. For a question about the "
            f"book itself, contact {pub}.</p>")
    elif kind == "privacy":
        paras.append(
            f"<p>When you order a print copy, {seller} is the seller of record and "
            f"processes your payment, shipping address, and contact details under "
            f"their own privacy policy. This book site collects no personal data "
            f"from your order: the &ldquo;Order a print copy&rdquo; link takes you "
            f"to {seller}&rsquo;s checkout, where their terms apply.</p>")
    else:  # refund
        paras.append(
            f"<p>Orders are fulfilled by {seller}, and any returns, replacements, "
            f"or refunds are handled by {seller} under their return policy. Contact "
            f"{seller} about an order, or {pub} about the book.</p>")
    extra = config.policies.get(kind, "").strip()
    if extra:
        paras.append(f"<p>{e(extra)}</p>")
    paras.append(
        f'<p class="policy-note">{pub} is responsible for this policy; this page '
        f"was generated from the print-ordering configuration. {seller} is a third "
        f"party with its own policies.</p>")
    return "\n".join(paras)


def release_problems(config: CommerceConfig | None, *, edition_qualified: bool) -> list[str]:
    """The fail-closed release decision for print ordering, pure so it is
    exhaustively testable. A disabled or absent block ships freely; an
    enabled one may ship only with a valid config and a passed physical
    qualification for this exact edition. Missing or unqualified evidence
    fails closed."""

    if config is None or not config.enabled:
        return []
    problems = validate(config)
    if not edition_qualified:
        problems.append(
            "commerce is enabled but no passed physical qualification exists "
            "for this edition; order and inspect a copy and record it in "
            "config/qualification.yaml before advertising ordering")
    return problems


def release_gate(root, book) -> tuple[list[str], str]:
    """The release-time gate: when a book advertises print ordering, refuse
    to ship unless the config is safe and the exact edition being sold has
    passed a physical inspection. Returns (problems, a human-readable proof
    summary). Engages only when ordering is enabled, so a book that sells
    nothing is unaffected."""

    from . import booklib, edition, qualification, registry

    config = load(booklib.metadata())
    if config is None or not config.enabled:
        return [], "print ordering is not enabled; no commerce release gate"

    # The print pack is what a reader would receive; build it so the edition
    # identity is computed from the real artifacts.
    registry.build("print")
    registry.build("coverwrap")
    try:
        # The chain is empty here: only the edition identity is needed, and
        # identity excludes the receipt chain by construction.
        manifest = edition.build([], root=root, book=book, fmt=config.edition)
    except FileNotFoundError:
        return (["commerce is enabled but the print pack is not built "
                 "(no interior/cover in dist); run press print"],
                "print pack missing")

    qualified: list[str] = []
    diagnostics: list[str] = []
    for inspection in qualification.book_inspections(root):
        qual, probs = qualification.qualify(inspection, manifest.edition_id)
        if qual is not None:
            qualified.append(qual.provider)
        else:
            diagnostics.extend(probs)

    problems = release_problems(config, edition_qualified=bool(qualified))
    if not qualified and diagnostics:
        problems.extend(diagnostics)
    summary = (
        f"edition {manifest.edition_id[:12]} ({config.edition}); "
        f"seller of record {config.seller_of_record}; "
        f"{len(qualified)} passed qualification(s)"
        + (f" ({', '.join(qualified)})" if qualified else "")
        + f"; config {'valid' if not validate(config) else 'INVALID'}")
    return problems, summary


def main(argv: list[str] | None = None) -> int:
    """Run the print-ordering release gate for the current book:

        python3 -m press.commerce

    Prints a proof summary; exits non-zero when an enabled book is not
    releasable (invalid config or an unqualified edition).
    """

    from . import booklib

    problems, summary = release_gate(booklib.root(), booklib.book())
    print(f"commerce release gate: {summary}")
    if problems:
        print("commerce release gate failed:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    return 0


def render(config: CommerceConfig | None) -> str:
    """The commerce block for the site: the ordering CTA when ordering is
    enabled and the config is valid, else empty. A misconfigured block
    emits nothing rather than a broken link; ``press check`` reports the
    misconfiguration so it is never silent."""

    if config is None or not config.enabled or validate(config):
        return ""
    return render_cta(config)


if __name__ == "__main__":
    raise SystemExit(main())
