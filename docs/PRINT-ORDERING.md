# Print ordering

How a reader orders a physical copy from a book site press produces, and
how a publisher sets that up safely. This is the task-focused guide; the
full product and technical rationale is in
[the direct-ordering plan](https://github.com/clintecker/press/blob/main/docs/DIRECT-ORDERING-PLAN.md), the config schema is
in [configuration](https://github.com/clintecker/press/blob/main/docs/CONFIGURATION.md), and the researched providers and the
physical checklist are in
[provider qualification](https://github.com/clintecker/press/blob/main/docs/PROVIDER-QUALIFICATION.md).

## What it is

A book site can show an **Order a print copy** control that links to a
print provider's own hosted checkout. The provider — Lulu first — is the
**seller of record**: they take the reader's payment, calculate tax, print
the book, ship it, and own customer support. Press does not run a store,
hold a payment credential, see a reader's address, or track an order. The
control is a plain link: no JavaScript, so it works with a keyboard, a
screen reader, and no script at all, and it can never claim a reader
"paid", because it never handles payment.

This is deliberately the smaller half of the plan. A publisher who wants
to be the merchant of record — taking payment directly and paying the
printer — needs the custom order broker, which is deferred to the
[Custom MoR milestone](https://github.com/clintecker/press/milestone/14).

## For readers

When a book offers it, the landing page shows an "Order a print copy"
link. Following it takes you to the named seller's secure checkout, which
is disclosed before you leave the book site. That seller — not the
author or press — handles your payment, shipping, and any support,
refunds, or privacy requests; their support, privacy, and refund links
sit beside the order button.

## For publishers

Ordering is **off by default**. Turning it on is four steps.

1. **Choose and set up a provider.** Pick a provider that can print your
   exact edition (see [provider qualification](https://github.com/clintecker/press/blob/main/docs/PROVIDER-QUALIFICATION.md);
   Lulu is the primary). Create your account with them, list your book,
   and get the public product URL a reader will buy from. Prices, tax
   settings, and account credentials live with the provider — never in
   your book repository.

2. **Enable ordering.** Add a `commerce.print-ordering` block to
   `config/metadata.yaml` with the HTTPS storefront URL, who the seller of
   record is, and your policy links:

   ```yaml
   commerce:
     print-ordering:
       enabled: true
       edition: paperback
       storefront-url: "https://www.lulu.com/shop/..."
       seller-of-record: "Lulu"
       support-url: "https://example.test/support"
       privacy-url: "https://example.test/privacy"
       refund-url: "https://example.test/refunds"
   ```

   `press check` refuses a non-HTTPS link, a missing policy link, an
   unnamed seller, an unknown key, or anything that looks like a secret.

3. **Qualify the edition.** Marketing does not prove a provider can print
   *your* object. Order one real copy through the route above and inspect
   it against the eleven-point checklist (content, pagination, trim,
   bleed, spine, barcode, color, paper, binding, packaging, tracking).
   Record the result in `config/qualification.yaml`, scoped to the exact
   edition it was ordered against (its `edition_id`); every point must be
   `pass`. A single failure does not qualify.

4. **Release.** `press all` runs the release gate. In a development build
   it is advisory; in a release build (`PRESS_RELEASE=1`) it is
   fail-closed: an ordering-enabled book cannot ship unless its config is
   valid and its exact edition passed qualification. Change the manuscript,
   cover, or print spec and the edition identity changes, the old
   inspection goes stale, and the gate reopens until you inspect a new
   copy — so a reader is never sent to buy a copy that differs from the
   one that was checked.

To pause sales, set `enabled: false` and rebuild: the CTA disappears and
`press verify` refuses any stray control that does not match the config.

## What press does and does not do

- **Does:** generate the accessible CTA, verify the config is safe and
  secret-free, verify the rendered page matches the config, and gate a
  release on a qualified edition bound to the exact release artifacts.
- **Does not:** process or store payment, calculate tax, hold provider
  credentials, receive a reader's name or address, or operate a store.
  Those belong to the provider, who is the seller of record.

## For contributors

Three pure modules carry this feature, each with a critical or standard
invariant in [the ledger](https://github.com/clintecker/press/blob/main/docs/INVARIANTS.md):

- `press.edition` — the immutable `EditionManifest`: a digest-addressed
  record of one edition whose identity is the production-affecting facts
  alone. Any change that could alter the physical object mints a new
  edition.
- `press.qualification` — the provider record (`quality/providers.yaml`)
  and the gate that only a passed, edition-scoped physical inspection can
  satisfy.
- `press.commerce` — the config, the generated CTA, and the fail-closed
  release gate.

The verifiers are `press check` (static config), `press verify` (the
rendered page), and the release gate in `press all`. A new provider is
added to the record with its capabilities recorded explicitly.

For the custom merchant-of-record path (deferred, but the adapter layer
is built), `press.providers` is the provider-neutral print contract: one
set of typed operations (quote, file validation, submission, lookup,
cancellation, event verification, status normalization), a stateful smart
fake, and a shared conformance suite every adapter passes. `press.providers.lulu`
is the Lulu Print API adapter, built to Lulu's public API and proven
against a canned transport; it stops Lulu's own vocabulary (its
`pod_package_id` SKUs, status words, webhook HMAC) at the boundary and
records what Lulu does not document (no order-creation idempotency) as
unknown rather than guessing. The live sandbox exchange awaits
credentials. HTTP is injected, so the adapter is boundary-clean and the
real transport lives in `press.adapters`.

## Security and privacy

Because the provider is the seller of record, the reader's payment,
address, and contact details are handled by the provider under their
privacy policy, not by press or the book. The book repository holds no
credential — the config verifier fails a build that embeds one. The only
reader-facing personal-data flow press generates is the outbound link;
the provider's own privacy and support pages, linked beside the order
button, govern the rest.
