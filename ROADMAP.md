# Roadmap: press as the whole publisher

The idea, stated once: a book repository holds the manuscript, its
configuration, and its accepted art. The press holds the reusable publishing
system: builds, verification, editorial law, agent instruments, art direction,
front matter, retail preparation, and registration guidance.

Someone who understands press should be able to run `press new`, write a book,
and finish with every promised artifact—EPUB, HTML, website, print-ready
interior and cover wrap, and publication checklists—without copying publishing
machinery into the book repository.

## How this roadmap stays true

[`roadmap/milestones.json`](https://github.com/clintecker/press/blob/main/roadmap/milestones.json)
is the source of record for milestone identity, state, title, description, and
reader-facing presentation order. Git commits and reviewed pull
requests provide the durable history. GitHub milestones are the mutable
execution view: they own live issue assignment, progress, and discussion. This
page is the human-readable view and is published directly as the website's
roadmap.

The generated section below must never be edited by hand. Run
`python3 scripts/sync_roadmap.py --write` after changing the registry. CI checks
the projection and reconciles the same metadata to GitHub after changes reach
`main`. Every milestone links to its live issue list; every description links
back to the relevant repository contracts or successor work.

This direction is intentionally one-way:

1. Propose roadmap intent in the repository.
2. Review the registry and generated roadmap in a pull request.
3. Merge the immutable record.
4. Reconcile GitHub's milestone metadata from that record.
5. Build the website from the same commit.

Editing milestone metadata only in GitHub is detectable drift, not a second
source of truth. Issue titles, bodies, labels, and milestone assignments remain
native GitHub data; duplicating them here would create a noisy and fragile
shadow issue tracker.

## Delivery milestones

<!-- BEGIN GENERATED MILESTONES -->

## Future and breaking horizons

Work deliberately held beyond the current v1 delivery train because it is breaking, optional, or depends on a mature single-book contract.

### [v2 — Composable press](https://github.com/clintecker/press/milestone/4) · Open

Reserved for breaking design/extension work that cannot ship under the v1 rendering contract: configurable geometry/themes, vendor-neutral operator boundaries, and other explicitly breaking changes. Milestone: [milestone 4](https://github.com/clintecker/press/milestone/4). Breaking-change issues: [the tracked issues](https://github.com/clintecker/press/issues?q=is%3Aissue+is%3Aopen+label%3Abreaking-change). Versioning contract: [the architecture guide](https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md). Roadmap: [the roadmap](https://github.com/clintecker/press/blob/main/ROADMAP.md).

### [Later — Catalog](https://github.com/clintecker/press/milestone/5) · Open

Optional multi-book catalog after the single-book publishing contract is mature. Milestone: [milestone 5](https://github.com/clintecker/press/milestone/5). Scoped feature: [issue 6](https://github.com/clintecker/press/issues/6). Roadmap context: [the roadmap](https://github.com/clintecker/press/blob/main/ROADMAP.md). Artifact contract to preserve: [the architecture guide](https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md).

### [Delivery trust — live proofs](https://github.com/clintecker/press/milestone/13) · Open

The delivery-trust work that cannot be finished from a single identity or a single CI run: the live second-party proofs (#87, human-run, needs a second GitHub account/org), and assembling the release trust chain from receipts the individual CI jobs emit and upload (#150), rather than synthesizing the chain inside the release-contract job.

### [Custom MoR (deferred)](https://github.com/clintecker/press/milestone/14) · Open

The custom merchant-of-record commerce machinery, deferred from v1.16 when the publisher chose a provider seller-of-record model. Built only if the publisher ever becomes merchant of record: the order broker, hosted Stripe checkout, provider API adapters, payment/fulfillment state machines, verified webhooks, exactly-once outbox, reconciliation, artifact delivery, and the privacy/operator/observability infrastructure. Plan: [direct-ordering-plan](https://github.com/clintecker/press/blob/main/docs/DIRECT-ORDERING-PLAN.md).

## Completed foundations

Closed milestones retained as the historical foundation for the active work and as links to their shipped issue records.

### [v1.1.1 — Integrity hotfix](https://github.com/clintecker/press/milestone/1) · Complete

Historical integrity hotfix: correctness and release-safety failures where a command could succeed while public output was wrong or unsafe. Review the closed scope at [milestone 1](https://github.com/clintecker/press/milestone/1) and release history at [the changelog](https://github.com/clintecker/press/blob/main/CHANGELOG.md). The contract it established is documented at [the architecture guide](https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md).

### [v1.2 — Executable contracts](https://github.com/clintecker/press/milestone/2) · Complete

Historical executable-contract release: centralized configuration/artifact contracts, stronger verifiers, and real consumer-book integration. Closed scope: [milestone 2](https://github.com/clintecker/press/milestone/2). Architecture: [the architecture guide](https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md). Generated artifact reference: [the command reference](https://github.com/clintecker/press/blob/main/docs/REFERENCE.md). Successor integrity work: [milestone 6](https://github.com/clintecker/press/milestone/6).

### [v1.3 — Public readiness](https://github.com/clintecker/press/milestone/3) · Complete

Historical public-readiness release: licensing, installation, support/security guidance, portability, and repository-boundary evidence. Closed scope: [milestone 3](https://github.com/clintecker/press/milestone/3). Installation: [the installation guide](https://github.com/clintecker/press/blob/main/docs/INSTALL.md). Contribution policy: [the contributing guide](https://github.com/clintecker/press/blob/main/CONTRIBUTING.md). Remaining live second-party proof: [issue 87](https://github.com/clintecker/press/issues/87).

### [v1.10 — Boundary integrity](https://github.com/clintecker/press/milestone/6) · Complete

Completed boundary-integrity release: source/publication safety, archive and format verification, retail artifacts, workflow input containment, exact toolchain identity, and resumable releases. Release: [the v1.10.0 release](https://github.com/clintecker/press/releases/tag/v1.10.0). Closed scope: [milestone 6](https://github.com/clintecker/press/milestone/6). Architecture and artifact laws: [the architecture guide](https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md). Its verifiers become named accumulated-trust proofs in [milestone 9](https://github.com/clintecker/press/milestone/9); release/container outcomes feed [milestone 10](https://github.com/clintecker/press/milestone/10).

### [v1.11 — Workflow coherence](https://github.com/clintecker/press/milestone/7) · Complete

Workflow and public-contract coherence: durable editorial/research outcomes, domain-neutral instruments, aesthetic/config documentation, contributor guidance, package metadata, and complexity debt. Milestone/issues: [milestone 7](https://github.com/clintecker/press/milestone/7). Public architecture/reference issue: [issue 33](https://github.com/clintecker/press/issues/33). Contributor contract: [the contributing guide](https://github.com/clintecker/press/blob/main/CONTRIBUTING.md). Testing traceability is implemented separately in [milestone 8](https://github.com/clintecker/press/milestone/8).

### [v1.12 — Trust foundations](https://github.com/clintecker/press/milestone/8) · Complete

Accumulated-trust foundation: pytest/selftest structure, executable invariant and callable-surface ledgers, collection-time proof enforcement, typed deterministic adapters, composable book factories, fixture provenance, property tests, and bounded replayable fuzzing. Milestone/issues: [milestone 8](https://github.com/clintecker/press/milestone/8). Start at [issue 78](https://github.com/clintecker/press/issues/78), then invariant ledger [issue 79](https://github.com/clintecker/press/issues/79). Feeds adversarial artifact proof: [milestone 9](https://github.com/clintecker/press/milestone/9). Architecture: [the architecture guide](https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md).

### [v1.13 — Adversarial artifact proof](https://github.com/clintecker/press/milestone/9) · Complete

Adversarial artifact proof built on v1.12: named damage operators, fixture-specific negative diagnostics, deterministic build/mutate/verify state models, pairwise/high-risk scenarios, real-tool integrations, compatibility, and design-major visual regression. Milestone/issues: [milestone 9](https://github.com/clintecker/press/milestone/9). Prerequisite foundation: [milestone 8](https://github.com/clintecker/press/milestone/8). Damage harness: [issue 88](https://github.com/clintecker/press/issues/88). Real-tool runner: [issue 91](https://github.com/clintecker/press/issues/91). Feeds delivery trust: [milestone 10](https://github.com/clintecker/press/milestone/10).

### [v1.15.2 — Delivery trust completion](https://github.com/clintecker/press/milestone/10) · Complete

The delivery-trust work deferred from v1.14/v1.15.1, shipped in v1.15.2: the layered CI reorder and the complete accumulated-trust receipt chain (#94/#97 — a release must present every trust layer, contiguous and linked, not a placeholder standing in for them), the deterministic mutation-score ratchet over the pure-computation modules (#95), and the per-module branch-coverage floor ratchet (#96). The live second-party proofs (#87) and the per-job receipt assembly (#150) moved to the 'Delivery trust — live proofs' milestone, which needs a second identity and cross-job CI artifacts.

### [v1.15 — Operator desk](https://github.com/clintecker/press/milestone/11) · Complete

Post-v1.14 optional operator desk: a single typed command catalog, digest/receipt-backed artifact status (never mtimes), typed doctor findings, a versioned child-event protocol, deterministic single-child control, DESK/target-picker/RUN views, headless active-signal tests, installed-wheel proof, and public documentation. Milestone/issues: [milestone 11](https://github.com/clintecker/press/milestone/11). Start with command catalog [issue 100](https://github.com/clintecker/press/issues/100), events [issue 102](https://github.com/clintecker/press/issues/102), packaging boundary [issue 104](https://github.com/clintecker/press/issues/104), and test harness [issue 108](https://github.com/clintecker/press/issues/108). Evidence status [issue 101](https://github.com/clintecker/press/issues/101) depends on trust receipts [issue 93](https://github.com/clintecker/press/issues/93). Release gate: [issue 114](https://github.com/clintecker/press/issues/114). Durable plan: [the TUI plan](https://github.com/clintecker/press/blob/main/docs/TUI-PLAN.md). Architecture: [the architecture guide](https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md). Textual testing: [textual.textualize.io](https://textual.textualize.io/guide/testing/).

### [v1.16 — Direct print ordering](https://github.com/clintecker/press/milestone/12) · Complete

Post-v1.15 direct-to-reader print ordering on the seller-of-record model: the provider (Lulu first) is the legal seller and owns payment, tax, fulfillment, and support, so press ships no payment infrastructure. Remaining after the manifest (#118, done): provider qualification and physical sample protocol (#117), a generated accessible storefront CTA with a no-JS fallback (#123) linking to the provider-hosted checkout (#139), a capped golden-copy inspection (#143), documentation (#138), and the release gate (#144). The custom merchant-of-record machinery (broker, Stripe checkout, provider API adapters, state machines, webhooks, outbox, reconciliation) is deferred to the 'Custom MoR (deferred)' milestone. Plan: [direct-ordering-plan](https://github.com/clintecker/press/blob/main/docs/DIRECT-ORDERING-PLAN.md).

### [v1.18 — Public experience and adoption](https://github.com/clintecker/press/milestone/15) · Complete

Completed public-experience release: beginner onboarding, validated configuration UI, conventional CLI discovery, accessible/semantic documentation and reader surfaces, public CI/toolchain consumption, and contributor/discovery governance. Release: [the v1.18.0 release](https://github.com/clintecker/press/releases/tag/v1.18.0). Closed scope: [milestone 15](https://github.com/clintecker/press/milestone/15). Public site: [clintecker.github.io](https://clintecker.github.io/press/). Residual reader metadata and gallery render proof moved to [milestone 4](https://github.com/clintecker/press/milestone/4) as #158 and #190.

### [v1.19 — Maintenance and compatibility](https://github.com/clintecker/press/milestone/16) · Complete

Completed maintenance/compatibility release: contributor verification, print-safe interiors, registrations and printing guides, security controls, Python 3.14 qualification, warning-clean dependency compatibility, hook isolation, and supported Action pins. Latest patch: [the v1.19.1 release](https://github.com/clintecker/press/releases/tag/v1.19.1). Closed scope: [milestone 16](https://github.com/clintecker/press/milestone/16). Compatibility: [compatibility](https://github.com/clintecker/press/blob/main/docs/COMPATIBILITY.md). Registrations delivery: [issue 191](https://github.com/clintecker/press/issues/191). Optional read-only lookup moved to [issue 203](https://github.com/clintecker/press/issues/203).

<!-- END GENERATED MILESTONES -->

## Product laws carried through every milestone

- Facts are stated once and projected mechanically wherever possible.
- Generators establish structure; verifiers prove the generated artifacts as
  objects rather than trusting command exit status.
- A scar becomes an executable invariant, a named proof, or an explicit public
  contract—not merely a warning in prose.
- Valid output and behavior remain compatible within a major release. Changes
  to typography, layout, or other pinned design contracts wait for a new major.
- Book repositories contain book facts. Reusable publishing machinery belongs
  in press and must work from an installed distribution without a source
  checkout.
- Trust accumulates from deterministic functions through compositions, real
  tools, complete workflows, consumer repositories, and release identity. A
  higher layer cannot erase missing proof below it.

The detailed system and artifact invariants live in
[`docs/ARCHITECTURE.md`](https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md);
the public command and artifact surface lives in
[`docs/REFERENCE.md`](https://github.com/clintecker/press/blob/main/docs/REFERENCE.md);
shipped changes live in
[`CHANGELOG.md`](https://github.com/clintecker/press/blob/main/CHANGELOG.md).

## Long horizon

The v1 milestones strengthen correctness and completeness without changing the
rendering contract. [v2 — Composable press](https://github.com/clintecker/press/milestone/4)
holds breaking design and extension work such as configurable geometry, themes,
and vendor-neutral operator boundaries. [Later — Catalog](https://github.com/clintecker/press/milestone/5)
holds the optional multi-book catalog after the single-book publishing contract
is mature.

Ideas that are not scheduled remain issues until their dependencies, invariant
impact, and release compatibility are understood. A milestone is a delivery
claim, not an aspiration bucket.
