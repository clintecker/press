# Direct print ordering: product and technical plan

Status: proposed for
[`v1.16 — Direct print ordering`](https://github.com/clintecker/press/milestone/12).
Research last verified: 2026-07-18.

This document is the durable product requirements document (PRD), technical
requirements document (TRD), vendor decision record, and release plan for
letting a reader order a physical copy from a book site produced by press.
GitHub issues are the mutable execution view; this document states why the
feature exists and the invariants every implementation must preserve.

## Decision in one page

The feature is feasible, but it is not safe to implement as browser-only code
on a static GitHub Pages site. A production version needs a small order broker
outside the static site. The broker owns secrets, creates a hosted payment
session, verifies payment events, submits one immutable print job to a provider,
and exposes a privacy-safe order-status view. Card details never pass through
press, a book repository, or the broker.

The recommended first production route is:

1. A book release publishes a qualified, immutable **edition manifest** that
   identifies the interior PDF, cover-wrap PDF, trim/binding/paper choices,
   checksums, release identity, and trust receipts.
2. The generated book site shows an `Order a print copy` control only for a
   qualified edition and sends the edition identifier—not a price or file
   URL—to the order broker.
3. The broker obtains a fresh production and shipping quote and creates a
   [Stripe-hosted Checkout](https://docs.stripe.com/payments/checkout) session.
4. A verified payment webhook causes exactly one fulfillment submission through
   a provider-neutral adapter. The first adapter targets the
   [Lulu Print API](https://developers.lulu.com/home); Bookvault is the preferred
   second adapter.
5. The reader follows an opaque status link. Provider events or reconciliation
   update fulfillment state without exposing provider credentials or customer
   data to the static site.

Before that custom flow is ready, a generated site may use an explicitly
configured provider-hosted storefront link. Mixam PrintLink, Lulu Direct, a
Peecho checkout, or a commerce platform connected to Bookvault can provide this
bridge. The external-checkout fallback remains available as a kill switch.

Press supplies reusable contracts, release tooling, static-site integration,
provider adapters, a reference broker, tests, and deployment guidance. A book
repository supplies book facts and chooses whether to sell. The publisher—not
press—owns the payment account, print-provider account, prices, supported
destinations, customer policies, and any tax registrations.

### Execution map

The [native v1.16 milestone](https://github.com/clintecker/press/milestone/12)
is the live execution view. Its narrowly scoped issues are grouped by the trust
they establish:

- product and qualification: [merchant/policy ownership #116](https://github.com/clintecker/press/issues/116),
  [provider qualification #117](https://github.com/clintecker/press/issues/117),
  and [hosted fallback #139](https://github.com/clintecker/press/issues/139);
- immutable domain boundaries: [edition manifests #118](https://github.com/clintecker/press/issues/118),
  [state machines #119](https://github.com/clintecker/press/issues/119), and
  [provider contracts #120](https://github.com/clintecker/press/issues/120);
- commerce and fulfillment: [broker #121](https://github.com/clintecker/press/issues/121),
  [quotes #122](https://github.com/clintecker/press/issues/122),
  [Stripe #124](https://github.com/clintecker/press/issues/124),
  [Lulu #127](https://github.com/clintecker/press/issues/127), and
  [exactly-once outbox #128](https://github.com/clintecker/press/issues/128);
- reader and operator safety: [site CTA #123](https://github.com/clintecker/press/issues/123),
  [webhooks #125](https://github.com/clintecker/press/issues/125),
  [artifact delivery #126](https://github.com/clintecker/press/issues/126),
  [privacy #130](https://github.com/clintecker/press/issues/130), and
  [operator controls #134](https://github.com/clintecker/press/issues/134);
- accumulated proof: [deterministic harness #135](https://github.com/clintecker/press/issues/135),
  [sandbox/deployed E2E #136](https://github.com/clintecker/press/issues/136),
  [security review #141](https://github.com/clintecker/press/issues/141),
  [golden copy #143](https://github.com/clintecker/press/issues/143), and
  [release gate #144](https://github.com/clintecker/press/issues/144).

## Vendor research and recommendation

The comparison uses vendor-published documentation. Marketing claims and
unpublished commercial terms still require written confirmation and a physical
sample before launch.

| Provider | Direct-reader route | Automation evidence | Fit for press |
|---|---|---|---|
| **Lulu** | Lulu Direct for Shopify, Wix, or WooCommerce; custom API for our own checkout | The [Print API](https://developers.lulu.com/home) documents a REST/JSON sandbox and production service, one-copy POD, file validation, pricing, shipping, order creation, and worldwide fulfillment. Lulu says custom direct sales remain our sale: the reader pays us and we pay Lulu for print and shipping ([selling options](https://www.lulu.com/sell)). | **Primary custom-API adapter.** Strong public API and sandbox, broad book formats, white-label dropshipping. Qualify the exact press trim/paper/binding and destination set. |
| **Bookvault** | Shopify, WooCommerce, Wix, Payhip, or a custom website API | Bookvault documents [direct-sale fulfillment](https://help.bookvault.app/how-does-bookvaults-fulfilment-service-work), a [custom API with no integration fee](https://help.bookvault.app/how-much-does-it-cost-to-print-and-ship-my-book), and the payment split: the store receives reader funds while Bookvault charges production and shipping to the publisher ([order funding](https://help.bookvault.app/i-have-connected-my-store-to-bookvault-how-do-i-pay-for-the-orders)). | **Preferred second adapter** and a strong hosted-commerce route. Particularly interesting for special editions. Confirm API contract, sandbox, webhook, region, and account-funding behavior before committing. |
| **Mixam** | PrintLink share/embed URL and Shopify app; public API by approval | Mixam's official [book-printing guide](https://d1e8vjamx1ssze.cloudfront.net/support/how-to-print-a-book.pdf) describes product discovery, options, order submission, and status through its public API, with account approval required. Its [Shopify listing](https://apps.shopify.com/mixam) describes PrintLink POD, fulfillment, shipping, and no inventory. | **Good hosted-checkout candidate; qualified API candidate.** Public technical material is thinner and access is approval-gated. Do not make it the first custom adapter without sandbox and contract review. |
| **Peecho** | Brandable plug-and-print checkout or seller-of-record service; custom API | Peecho advertises a [REST print API and checkout](https://www.peecho.com/solutions/print-api), single-copy books, pricing/status/order operations, global routing, and a seller-of-record option. Its [self-publishing route](https://www.peecho.com/self-publishing) has no minimum and includes dropshipping. | **Best discovery candidate when avoiding merchant-of-record work matters.** Validate trade-book geometry, monochrome economics, data terms, checkout branding, support ownership, and API access. |
| **Cloudprinter** | Custom checkout plus print API or commerce integrations | Cloudprinter documents a [REST print API](https://www.cloudprinter.com/), sandbox, live pricing, webhooks/signals, textbooks and photobooks, and global local routing. | **Strong multi-provider/network candidate.** Useful for geographic routing and resilience, but variable production sites make physical consistency and qualification more complex. |
| **Prodigi** | Custom commerce plus API | Prodigi's [v4 API](https://www.prodigi.com/print-api/docs/) has sandbox/live environments and order APIs; its [book range](https://www.prodigi.com/products/books-and-magazines/) supports single-copy hardback, softcover, layflat, and magazines. | **Technically credible, product-fit uncertain.** Its range leans toward photo books and magazines. Qualify trade-book typography, black-only interiors, trim, cover handling, and unit cost. |
| **OnPress** | Custom API integration | OnPress announced a [book-printing API](https://www.onpressbookprinting.com/resources/book-printing-api) for automated printing and fulfillment, aimed at publishers, retailers, and platforms. | **Sales-qualified later adapter.** Public operational/API detail is insufficient for a release commitment; obtain auth, quote, idempotency, status, cancellation, sandbox, SLA, and privacy terms first. |
| **Print Bind Ship** | Shopify/WooCommerce, integrations, portal, or custom API | The company describes [book fulfillment](https://printbindship.com/book-fulfillment-services/) and [Shopify/API fulfillment](https://printbindship.com/shopify-fulfillment/). Its [terms](https://printbindship.com/terms-and-conditions/) describe setup, auto-payment, POD production targets, storage, returns, and integration. | **Later 3PL/volume route.** More sales- and contract-led than a self-service API. Useful if inventory, kitting, or mixed POD/stock fulfillment becomes important. |
| **48 Hour Books** | Manual short-run ordering and shipping | Its [FAQ](https://www.48hrbooks.com/faq) states a 10-copy minimum and shipping to the US and Canada. | **Not a one-reader/one-copy adapter.** Keep as a bulk proof, launch stock, or replenishment option, outside the automated POD contract. |

KDP and Ingram distribution can remain retail channels, but neither is the
reference white-label order API for this feature. They solve marketplace and
bookstore availability, not a provider-neutral transaction initiated on a
press-generated site.

### Vendor selection gate

A provider is `qualified` for an edition only when all of the following are
recorded:

- account/commercial terms, production regions, supported destinations,
  branding, returns, cancellation, privacy, content retention, and support
  escalation have named owners;
- API authentication, sandbox semantics, rate limits, idempotency behavior,
  status vocabulary, webhook or polling behavior, and error taxonomy have
  executable contract fixtures;
- the provider accepts the exact interior and cover artifacts without an
  undocumented rebuild or geometry change;
- an ordered physical copy passes the press print inspection checklist; and
- unit economics include print, shipping, payment fees, tax behavior, expected
  remakes/refunds, and a configured loss ceiling.

Provider availability is a capability, not an edition fact. An edition may be
qualified for zero, one, or several providers without changing its content
identity.

## Product requirements (PRD)

### Problem

Press can produce retail-ready files, but a reader cannot move from the book's
site to a verified physical copy without the publisher manually operating a
store, copying edition data, handling an order, or trusting an unrelated build.
That handoff loses the strongest property press already has: the artifact a
reader receives should be the exact artifact that passed the release gates.

### Product promise

For a qualified edition and supported destination, a reader can see an honest
landed price, pay on an accessible hosted checkout, receive one correctly
specified copy, and track or resolve the order. The publisher can prove which
release artifacts were ordered, reconcile money to fulfillment, stop sales
immediately, and switch providers without changing the book site contract.

### Personas and jobs

- **Reader:** buy the physical edition without learning the print provider or
  creating a publisher-specific account; know total cost, delivery expectations,
  and support path before payment.
- **Publisher/operator:** enable a qualified edition, set commercial policy,
  inspect exceptions, refund safely, reconcile provider charges, and stop new
  orders without redeploying code.
- **Book author/maintainer:** declare book facts once and never place secrets,
  prices, customer data, or provider implementation details in the book repo.
- **Press contributor:** add a provider behind one typed contract and prove it
  against the same deterministic conformance suite.
- **Support/privacy owner:** find an order from a reader-supplied reference,
  disclose only necessary state, and honor retention/deletion policy without
  corrupting the financial audit trail.

### Scope

The first supported product is one non-personalized, release-qualified print
edition per line item, quantity bounded by publisher policy. Scope includes:

- generated order CTA and no-JavaScript/external-checkout fallback;
- destination-aware print and shipping quote;
- hosted payment, tax calculation configuration, receipt, refund, and dispute
  hooks;
- immutable edition catalog and sellability gate;
- provider-neutral quote, validation, submission, and status contracts;
- Lulu sandbox and physically qualified production path;
- status page, email handoff, support reference, and operator controls;
- privacy, security, observability, reconciliation, and deterministic tests;
- public setup, policies, incident, refund, and provider qualification docs.

### Non-goals for v1.16

- storing or processing card data;
- building a general shopping cart, customer account system, marketplace, or
  warehouse-management system;
- personalized interiors/covers, subscriptions, bundles, coupons, preorders,
  wholesale, or multi-book baskets;
- promising every country, currency, format, or provider;
- silently substituting a printer, paper, binding, or release artifact;
- making press the legal seller, tax adviser, customer-support organization, or
  custodian of a publisher's production credentials.

### Functional requirements

`PR-01 Edition identity.` Every sellable SKU resolves server-side to one
immutable edition manifest. A browser cannot supply or override price, provider
product code, artifact URL, checksum, currency, or print specification.

`PR-02 Honest availability.` The CTA is absent or explicitly unavailable when
the edition is unqualified, sales are disabled, destination is unsupported, or
a fresh quote cannot be obtained. A stale hard-coded price is never presented
as final.

`PR-03 Landed quote.` Before payment the reader sees item, shipping, tax,
currency, quantity, destination constraints, expected production range, and the
publisher's refund/support links. Money uses integer minor units plus an ISO
currency; provider decimals are parsed without binary floating point.

`PR-04 Hosted payment.` Payment entry occurs on a PCI-oriented hosted page such
as Stripe Checkout. Stripe can calculate checkout tax from the collected
address, but the publisher must configure registrations and product tax codes;
the integration does not create legal registrations automatically
([Stripe Tax setup](https://docs.stripe.com/tax/set-up),
[Checkout tax](https://docs.stripe.com/tax/checkout)).

`PR-05 Exactly one paid fulfillment.` Duplicate clicks, webhook delivery,
retries, restarts, or reconciliation cannot create a second print job or charge.
An order records separate payment and fulfillment state; no single ambiguous
`status` field is authoritative for both.

`PR-06 Failure compensation.` A paid order that cannot be submitted enters a
visible exception queue and follows a documented retry/refund decision. It is
never dropped, reported as fulfilled, or retried without an idempotency key.

`PR-07 Reader status.` The reader receives an opaque, revocable status URL and
support reference. The page reveals only that order's safe projection and does
not permit enumeration. Tracking links are provider data and must be allowlisted
before rendering.

`PR-08 Operator control.` Authorized operators can disable sales globally, by
edition, destination, or provider; inspect redacted exceptions; retry safe
operations; request a refund; and reconcile payment and provider references.
Dangerous actions require explicit confirmation and an audit record.

`PR-09 Provider portability.` Site templates and domain logic do not import a
provider SDK. Provider-specific identifiers and statuses stop at the adapter.
Capabilities are explicit; unsupported cancellation or webhook behavior is not
simulated.

`PR-10 Accessible, resilient UX.` The generated control and status view meet the
site's accessibility standard, work on small screens and keyboards, preserve a
useful no-script path, distinguish recoverable from terminal failures, and do
not imply that returning from checkout proves payment.

`PR-11 Communication.` Payment receipt, fulfillment acceptance, shipment, delay,
refund, and support messages identify the publisher, edition, safe order
reference, and policy links. Email delivery failure does not alter order state.

`PR-12 Physical qualification.` Production cannot be enabled until a real copy
ordered through the production path passes content identity, pagination, trim,
bleed, spine, barcode, color, paper, binding, packaging, and destination-link
inspection.

### Commercial and policy requirements

The publisher must make an explicit merchant-of-record decision. In the custom
Lulu/Bookvault model the publisher receives the reader's payment and separately
pays the printer, so the publisher owns pricing, tax registration/filing,
refunds, chargebacks, customer support, and negative-margin risk. A
seller-of-record or vendor-hosted storefront can transfer some responsibilities,
but its actual contract—not the UI label—controls.

Launch configuration must name:

- legal seller and statement descriptor;
- supported countries, currencies, quantities, and edition;
- retail margin floor and maximum permitted loss;
- tax registrations and physical-goods/book tax code;
- refund, cancellation, replacement, privacy, and support policies;
- provider balance/card funding and alert threshold;
- production/shipping estimates and their source;
- data controller/processors, retention periods, and deletion procedure; and
- incident owner, provider escalation, and global kill-switch owner.

These are release-gate facts, not optional documentation polish. Professional
tax and legal review is required for the publisher's actual jurisdictions.

### Success measures

Before general availability:

- 100% of production orders reference a qualified manifest and matching
  artifact digests;
- zero duplicate provider submissions under the replay and crash test suite;
- 100% of provider charges reconcile to one internal order and payment outcome;
- all webhook fixtures reject bad signatures and accept safe duplicate replay;
- one physical golden copy passes for each enabled format/provider/production
  region that can materially change the object;
- no secrets or unredacted address/email data occur in repository content,
  client bundles, normal logs, metrics, traces, or test snapshots; and
- a staged incident drill proves sales can be disabled and paid exceptions can
  be enumerated without deploying new application code.

Business metrics include checkout conversion, quote failure rate, paid-to-submit
latency, provider rejection rate, on-time shipment, remake/refund/dispute rate,
support contacts per order, landed margin, and provider variance. Targets are
set only after sample traffic and written vendor service expectations; the plan
does not invent an SLA the provider has not promised.

## Technical requirements (TRD)

### System boundaries

```text
book repository --release--> immutable edition artifacts + trust receipts
       |                                      |
       +--build--> static book site            +--> private artifact delivery
                         |                                |
reader browser --edition id--> order broker --signed URL-+--> print provider
                               |       ^                       |
                               |       +--status/webhook-------+
                               v
                         hosted checkout
                               |
                               +--signed payment webhook--> order broker
```

The generated site is untrusted presentation. The broker is the policy and
transaction boundary. The payment processor is the card-data boundary. The
print adapter is the provider vocabulary boundary. Artifact storage is private
and immutable; the provider receives narrowly scoped, expiring access when its
API requires URLs.

GitHub Pages is a static publishing service
([GitHub Pages documentation](https://docs.github.com/en/pages)). It may host
the CTA and status shell, but it cannot safely hold provider/payment secrets or
be the authoritative order database.

### Components

1. **Edition manifest builder and verifier** in press: emits canonical JSON from
   release-approved print artifacts and proof receipts.
2. **Static order component** in book site templates: edition identifier,
   broker origin, policy links, progressive enhancement, external fallback.
3. **Order broker reference service**: quote/session endpoints, verified
   webhooks, order state machine, outbox, provider adapters, redacted operator
   surface, status projection, retention jobs, and audit events.
4. **Payment adapter**: hosted-session creation, signature verification,
   idempotent event ingestion, refund/dispute projection. Stripe is the
   reference implementation, not a domain import.
5. **Print-provider adapters**: Lulu first, Bookvault second. Each declares
   capabilities and maps provider errors/statuses into the domain taxonomy.
6. **Artifact delivery service**: immutable object key, digest verification,
   short-lived signed download, provider access audit, and deny-by-default
   content type/size policy.
7. **Reconciler**: consumes provider events when available and deterministic
   scheduled queries otherwise. Correctness depends on persisted cursors and
   idempotent observations, never wall-clock timing.

The reference broker should be deployable independently of a book and consume
only versioned manifests. No cloud provider is mandated in the domain package;
deployment examples may select one supported stack and pin it.

### Core data model

**EditionManifest**

- `schema_version`, `edition_id`, book slug, title, format/ISBN;
- release tag, commit, press/toolchain identity, trust-receipt references;
- interior and cover object identifiers, byte sizes, media types, SHA-256;
- normalized trim, binding, paper, color, page count, bleed and barcode facts;
- qualified provider products and qualification evidence digests;
- creation identity; no mutable retail price and no customer data.

**Quote**

- opaque quote ID, edition ID, provider, destination class, quantity;
- print, shipping, tax-estimate inputs, fees, margin, total, currency;
- provider quote/reference and capability snapshot;
- creation/expiry instants from an injected clock and a consumed/replaced flag.

**Order**

- opaque internal ID, public support reference, edition/manifest digest;
- quote snapshot and terms/policy version accepted;
- payment state/reference and fulfillment state/reference, stored separately;
- encrypted/minimized recipient fields or processor references;
- idempotency keys, correlation ID, audit sequence, version for compare-and-swap;
- retention class and terminal timestamps.

**OutboxEntry / ProviderObservation / AuditEvent**

- immutable event ID, aggregate ID/version, type, canonical payload digest;
- attempt/receipt information and redacted diagnostics;
- provider payload retained only when necessary and sanitized before fixtures.

### State and transition laws

Payment states:

```text
unpaid -> pending -> paid -> refund_pending -> refunded
                    |  +---------------------> disputed
                    +------------------------> partially_refunded (future-disabled)
```

Fulfillment states:

```text
not_requested -> queued -> submitting -> accepted -> in_production -> shipped
                     |          |            |             |
                     +----------+------------+-------------+-> exception
accepted -> cancellation_requested -> cancelled | exception
```

Transitions are append-only facts projected into current state. The transition
function is pure and rejects impossible moves. `paid` authorizes one fulfillment
intent; it does not mean submitted. `accepted` does not mean printed. A browser
redirect never transitions payment. Provider status can advance only through
the adapter's explicit mapping. Unknown statuses quarantine the observation and
alert rather than guessing.

### API surface

All endpoints are versioned, JSON, size-limited, content-type checked, and
rate-limited. Browser mutation endpoints require an origin policy and anti-abuse
token appropriate to the chosen deployment.

- `POST /v1/quotes`: edition ID, destination, quantity -> authoritative quote
  or typed unavailability.
- `POST /v1/checkouts`: unconsumed quote ID -> hosted checkout URL. Repeating
  with the same idempotency key returns the same safe result.
- `GET /v1/orders/{opaque_token}`: reader-safe status projection.
- `POST /v1/webhooks/payments/{adapter}`: raw signed processor event.
- `POST /v1/webhooks/fulfillment/{adapter}`: raw signed provider event where
  supported.
- operator endpoints/CLI: disable sales, list exceptions, show redacted order,
  reconcile, request refund/cancellation, rotate status token.

The API never accepts an artifact URL, provider SKU, unit amount, currency, tax
amount, or trusted order state from the browser.

### Provider adapter contract

Adapters implement typed operations and declare unsupported capabilities:

- `capabilities()` and `qualify(edition, destination)`;
- `quote(request)` with normalized money and shipping choices;
- `validate_files(edition, signed_assets)`;
- `submit(order, idempotency_key, signed_assets)`;
- `get_order(provider_reference)`;
- `cancel(provider_reference)` only when supported;
- `parse_event(raw_request)` with authenticity result;
- `normalize(observation)` to domain events and typed errors.

Every request carries a stable external order reference. Network timeouts are
`unknown outcome`, not failure: the broker queries by the stable reference
before any resubmission. Provider adapters own retry classification but cannot
perform hidden retries. Raw provider strings never drive domain transitions.

### Consistency and idempotency

The paid-to-print path is a transactional outbox/saga:

1. Verify the webhook signature against the raw body and reject stale/replayed
   events according to processor semantics.
2. Insert the processor event ID once. A duplicate returns success without new
   effects.
3. In one database transaction, project payment state and create one
   `submit_fulfillment` outbox entry guarded by an order uniqueness constraint.
4. A worker claims the entry, resolves the pinned manifest, verifies digests,
   creates expiring asset URLs, and submits using the stable external ID.
5. On timeout, reconcile by external ID. Only a provider-proven absence permits
   another submission attempt with the same idempotency identity.
6. Persist the provider receipt before acknowledging the outbox entry.
7. Permanent rejection creates an exception; policy decides corrected retry or
   refund. Compensation is itself idempotent and audited.

Database constraints, compare-and-swap versions, processor/provider idempotency
features, and reconciliation work together. None alone proves exactly-once
business effect.

### Artifact identity and delivery

Only release-gated artifacts may enter an edition manifest. The manifest is
canonicalized and digest-addressed. Submission re-verifies bytes against the
manifest before creating provider access. A new manuscript, cover, page count,
barcode, print spec, or production-affecting press/toolchain change creates a
new edition-manifest identity and requires requalification where the physical
object can change.

Signed URLs are short-lived, limited to one immutable object, served with the
expected content type, and never logged with query credentials. Provider-side
file validation results and accepted source checksums are captured when
available. A rebuild after payment is forbidden.

### Security, privacy, and compliance

- Use hosted payment UI; prohibit card fields and payment secrets in book/site
  code. This narrows but does not eliminate PCI responsibilities.
- Store all credentials in the deployment secret manager; use separate sandbox
  and production accounts, least privilege, rotation, and startup validation.
- Verify webhook signatures over exact raw bytes, bound body sizes, reject bad
  timestamps/signatures, deduplicate event IDs, and fuzz parsers.
- Treat recipient name, address, email, IP, tracking link, and order contents as
  personal data. Encrypt sensitive fields, restrict operator access, redact
  logs/traces/errors, and document processor transfers. Lulu's
  [API privacy policy](https://developers.lulu.com/privacy-policy) confirms that
  order contact/address and content are transferred for fulfillment.
- Retain the minimum fulfillment data for the shortest policy/legal period.
  Separate deletable operational PII from non-PII financial/audit facts.
- Use opaque high-entropy status tokens, constant-shape not-found responses,
  rotation, rate limits, and no search-engine indexing.
- Allowlist redirect, webhook, CORS, tracking, and signed-asset origins. Never
  render provider HTML or follow arbitrary URLs supplied by a provider payload.
- Enforce quantity, destination, quote frequency, margin, daily spend, and
  provider-charge limits. Alert and fail closed when funding or cost crosses
  policy.
- Threat-model account takeover, forged events, duplicate submissions, quote
  manipulation, SSRF, object substitution, PII leakage, refund abuse, provider
  compromise, supply-chain drift, and operator mistakes.

### Accumulated-trust test scaffold

The commerce path follows the repository's existing L0–L7 taxonomy. All clocks,
UUIDs, randomness, network clients, queues, storage, payment/provider gateways,
and notification sinks are injected. Tests assert active signals—return values,
typed errors, emitted events, persisted transitions, and external requests—not
sleeps or private implementation calls.

| Layer | Required proof |
|---|---|
| **L0 inventory** | Every public endpoint, state transition, adapter operation, invariant, policy decision, and failure class maps to a named test; collection fails on missing mappings. |
| **L1 pure** | Property tests cover money arithmetic, canonical manifests, quote bounds, transition laws, redaction, token parsing, capability matching, and provider-status normalization. No I/O. |
| **L2 component** | Smart fakes exercise payment and provider contracts, raw webhook verification, repository constraints, signed URL policy, and exact outgoing requests. Contract fixtures are sanitized, versioned, and provenance-stamped. |
| **L3 adversarial** | Mutators corrupt digests, prices, addresses, signatures, currencies, status order, provider IDs, URLs, and payload shapes; every mutation must produce the named diagnostic and no unsafe side effect. |
| **L4 scenario/state** | Model-based/property state machines explore duplicate/out-of-order events, crash points, unknown outcomes, refunds, cancellations, provider rejection, funding failure, and concurrent workers. Pairwise plus named high-risk combinations run deterministically from a replay seed. |
| **L5 real sandbox** | Stripe CLI/test environment plus provider sandbox prove auth, schemas, quote/submit/status behavior, and webhook compatibility without production fulfillment. Recorded fixtures cannot replace this gate. |
| **L6 installed/deployed** | Build the installed press distribution and reference broker image, scan it, deploy an ephemeral stack with production-shaped configuration, and prove migrations, secret absence, status UX, kill switch, backup/restore, and observability. |
| **L7 live boundary** | A release-qualified book site completes test checkout to provider sandbox, then a controlled production order yields a physically inspected golden copy. Receipt chain binds commit, distribution, broker image, manifest, payment event, provider job, and inspection. |
| **Meta** | Mutation testing and sabotage tests prove the suite fails if signature checks, uniqueness constraints, digest verification, state guards, redaction, spend limits, or release gates are removed. |

Fuzzing is bounded, seeded, replayable, and promoted: every discovered failure
becomes a minimal named regression fixture. Property tests assert invariants
rather than duplicating implementation. Sandbox tests are quarantined from fast
tests but remain required before release. Production tests never make an order
without an explicit cost cap and operator authorization.

### Observability and operations

Structured events use correlation/order references, adapter name, operation,
safe state, duration, attempt class, and error code—never raw recipient fields,
asset URLs, tokens, or provider payloads. Dashboards cover quote health,
checkout/payment mismatch, outbox age, submission unknowns, provider rejection,
orders stuck by state, funding/spend, refund/dispute, and reconciliation gaps.

Runbooks cover:

- global/edition/provider/destination sales disable;
- payment succeeded but no order, paid but not submitted, and unknown provider
  outcome;
- duplicate-suspected job, bad artifact, provider outage, funding failure, and
  unexpected cost;
- shipment delay/loss/damage, remake, cancellation, refund, and dispute;
- credential/webhook compromise and PII incident;
- provider status/schema change, failover, backup restore, and reconciliation;
- customer data access/deletion and retention expiry.

Every alert names an action and owner. Reconciliation reports are durable
artifacts. A status page may say `delivered` only when a trustworthy carrier or
provider signal supports it; otherwise `shipped` is the last claim.

### Repository and configuration contract

Proposed book metadata is declarative and contains no secret:

```yaml
commerce:
  print-ordering:
    enabled: true
    edition: paperback
    broker-url: https://orders.example.test
    fallback-url: https://provider.example.test/publication/example
    support-url: https://example.test/support
    privacy-url: https://example.test/privacy
    refund-url: https://example.test/refunds
```

Provider accounts, product mappings, retail policy, tax configuration, country
allowlists, kill switches, and credentials live in broker configuration. The
release process publishes the edition manifest to the configured broker only
after qualification and trust gates. `press verify` proves that an enabled site
has complete policy links, HTTPS origins, an immutable manifest, and no secret
fields. `press doctor` checks configuration reachability without printing PII or
secret material.

### Rollout

**Phase A — safe link.** Generate an accessible external storefront CTA with
complete policy/fallback behavior. Physically qualify the hosted provider. This
delivers value without custom payment infrastructure.

**Phase B — reference sandbox.** Land edition manifests, domain state machine,
fake adapters, Stripe test checkout, Lulu sandbox adapter, local harness, and
ephemeral deployment. No production money or printing.

**Phase C — controlled production.** Enable one edition, provider, currency,
quantity range, and destination cohort. Place the capped golden-copy order,
exercise refund/kill-switch/restore drills, then invite a small cohort.

**Phase D — general availability.** Publish support and policy ownership,
ratchet live-boundary receipts into release, monitor economics and failure
rates, and keep the external storefront fallback.

**Phase E — portability.** Qualify Bookvault, then select additional providers
only for a concrete format, geography, seller-of-record, quality, or resilience
need. Routing never substitutes an unqualified physical specification.

## Release acceptance

The milestone is complete only when:

- this PRD/TRD and all public/operator policies match the deployed behavior;
- one release-qualified edition can use hosted fallback and the reference
  broker without repository secrets;
- Stripe test checkout and Lulu sandbox pass the full deterministic scenario
  suite;
- payment, provider, artifact, and order audit references reconcile exactly;
- duplicate/out-of-order/crash/fuzz/mutation suites prove the critical
  invariants;
- the installed distribution and ephemeral deployment pass L6;
- a capped production order passes physical golden-copy inspection and the
  evidence joins the release receipt chain;
- kill switch, refund, restore, credential rotation, provider outage, and PII
  runbooks have been exercised; and
- every supported path is documented for readers, publishers, operators,
  contributors, and incident responders.

## Open decisions that must be closed before production

1. Is the publisher willing and prepared to be merchant of record, or should
   the first durable integration use a seller/provider-hosted checkout?
2. Which legal entity, home jurisdiction, launch destinations, currency, and
   tax registrations apply?
3. Which exact book format and production regions pass physical qualification?
4. Where will the reference broker, database, private artifacts, queues,
   secrets, and email/status domain run, and who operates them?
5. Is payment captured before submission or authorized then captured after
   provider acceptance? The answer depends on provider response guarantees,
   payment-method authorization windows, and customer disclosure.
6. Which recipient data must be retained, for how long, and which processor is
   the source of truth for receipts and tax records?
7. What replacement/refund promise applies after production begins, and who
   bears provider/carrier loss?
8. Does a second provider solve an observed need worth the added physical and
   contract qualification surface?

Until these are answered, sandbox implementation and a provider-hosted link may
proceed; production custom checkout may not.
