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

### Active v1 delivery

The current compatible release train, ordered by intended delivery. Each milestone accumulates proof from the milestones before it.

#### [v1.12 — Trust foundations](https://github.com/clintecker/press/milestone/8) · Open

Accumulated-trust foundation: pytest/selftest structure, executable invariant and callable-surface ledgers, collection-time proof enforcement, typed deterministic adapters, composable book factories, fixture provenance, property tests, and bounded replayable fuzzing. Milestone/issues: <https://github.com/clintecker/press/milestone/8>. Start at <https://github.com/clintecker/press/issues/78>, then invariant ledger <https://github.com/clintecker/press/issues/79>. Feeds adversarial artifact proof: <https://github.com/clintecker/press/milestone/9>. Architecture: <https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md>.

#### [v1.13 — Adversarial artifact proof](https://github.com/clintecker/press/milestone/9) · Open

Adversarial artifact proof built on v1.12: named damage operators, fixture-specific negative diagnostics, deterministic build/mutate/verify state models, pairwise/high-risk scenarios, real-tool integrations, compatibility, and design-major visual regression. Milestone/issues: <https://github.com/clintecker/press/milestone/9>. Prerequisite foundation: <https://github.com/clintecker/press/milestone/8>. Damage harness: <https://github.com/clintecker/press/issues/88>. Real-tool runner: <https://github.com/clintecker/press/issues/91>. Feeds delivery trust: <https://github.com/clintecker/press/milestone/10>.

#### [v1.14 — Accumulated delivery trust](https://github.com/clintecker/press/milestone/10) · Open

Accumulated delivery/release trust: clean installed distributions, chained machine-verifiable trust receipts, ordered CI gates, mutation/sabotage ratchets, invariant-aware test impact, live second-party boundaries, and release identity across commit/wheel/action/image/artifacts/tag. Milestone/issues: <https://github.com/clintecker/press/milestone/10>. Prerequisites: <https://github.com/clintecker/press/milestone/8> and <https://github.com/clintecker/press/milestone/9>. Receipt chain: <https://github.com/clintecker/press/issues/93>. Layered CI: <https://github.com/clintecker/press/issues/94>. Release gate: <https://github.com/clintecker/press/issues/97>.

#### [v1.15 — Operator desk](https://github.com/clintecker/press/milestone/11) · Open

Post-v1.14 optional operator desk: a single typed command catalog, digest/receipt-backed artifact status (never mtimes), typed doctor findings, a versioned child-event protocol, deterministic single-child control, DESK/target-picker/RUN views, headless active-signal tests, installed-wheel proof, and public documentation. Milestone/issues: <https://github.com/clintecker/press/milestone/11>. Start with command catalog <https://github.com/clintecker/press/issues/100>, events <https://github.com/clintecker/press/issues/102>, packaging boundary <https://github.com/clintecker/press/issues/104>, and test harness <https://github.com/clintecker/press/issues/108>. Evidence status <https://github.com/clintecker/press/issues/101> depends on trust receipts <https://github.com/clintecker/press/issues/93>. Release gate: <https://github.com/clintecker/press/issues/114>. Durable plan: <https://github.com/clintecker/press/blob/main/docs/TUI-PLAN.md>. Architecture: <https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md>. Textual testing: <https://textual.textualize.io/guide/testing/>.

### Future and breaking horizons

Work deliberately held beyond the current v1 delivery train because it is breaking, optional, or depends on a mature single-book contract.

#### [v2 — Composable press](https://github.com/clintecker/press/milestone/4) · Open

Reserved for breaking design/extension work that cannot ship under the v1 rendering contract: configurable geometry/themes, vendor-neutral operator boundaries, and other explicitly breaking changes. Milestone: <https://github.com/clintecker/press/milestone/4>. Breaking-change issues: <https://github.com/clintecker/press/issues?q=is%3Aissue+is%3Aopen+label%3Abreaking-change>. Versioning contract: <https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md>. Roadmap: <https://github.com/clintecker/press/blob/main/ROADMAP.md>.

#### [Later — Catalog](https://github.com/clintecker/press/milestone/5) · Open

Optional multi-book catalog after the single-book publishing contract is mature. Milestone: <https://github.com/clintecker/press/milestone/5>. Scoped feature: <https://github.com/clintecker/press/issues/6>. Roadmap context: <https://github.com/clintecker/press/blob/main/ROADMAP.md>. Artifact contract to preserve: <https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md>.

### Completed foundations

Closed milestones retained as the historical foundation for the active work and as links to their shipped issue records.

#### [v1.1.1 — Integrity hotfix](https://github.com/clintecker/press/milestone/1) · Complete

Historical integrity hotfix: correctness and release-safety failures where a command could succeed while public output was wrong or unsafe. Review the closed scope at <https://github.com/clintecker/press/milestone/1> and release history at <https://github.com/clintecker/press/blob/main/CHANGELOG.md>. The contract it established is documented at <https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md>.

#### [v1.2 — Executable contracts](https://github.com/clintecker/press/milestone/2) · Complete

Historical executable-contract release: centralized configuration/artifact contracts, stronger verifiers, and real consumer-book integration. Closed scope: <https://github.com/clintecker/press/milestone/2>. Architecture: <https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md>. Generated artifact reference: <https://github.com/clintecker/press/blob/main/docs/REFERENCE.md>. Successor integrity work: <https://github.com/clintecker/press/milestone/6>.

#### [v1.3 — Public readiness](https://github.com/clintecker/press/milestone/3) · Complete

Historical public-readiness release: licensing, installation, support/security guidance, portability, and repository-boundary evidence. Closed scope: <https://github.com/clintecker/press/milestone/3>. Installation: <https://github.com/clintecker/press/blob/main/docs/INSTALL.md>. Contribution policy: <https://github.com/clintecker/press/blob/main/CONTRIBUTING.md>. Remaining live second-party proof: <https://github.com/clintecker/press/issues/87>.

#### [v1.10 — Boundary integrity](https://github.com/clintecker/press/milestone/6) · Complete

Completed boundary-integrity release: source/publication safety, archive and format verification, retail artifacts, workflow input containment, exact toolchain identity, and resumable releases. Release: <https://github.com/clintecker/press/releases/tag/v1.10.0>. Closed scope: <https://github.com/clintecker/press/milestone/6>. Architecture and artifact laws: <https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md>. Its verifiers become named accumulated-trust proofs in <https://github.com/clintecker/press/milestone/9>; release/container outcomes feed <https://github.com/clintecker/press/milestone/10>.

#### [v1.11 — Workflow coherence](https://github.com/clintecker/press/milestone/7) · Complete

Workflow and public-contract coherence: durable editorial/research outcomes, domain-neutral instruments, aesthetic/config documentation, contributor guidance, package metadata, and complexity debt. Milestone/issues: <https://github.com/clintecker/press/milestone/7>. Public architecture/reference issue: <https://github.com/clintecker/press/issues/33>. Contributor contract: <https://github.com/clintecker/press/blob/main/CONTRIBUTING.md>. Testing traceability is implemented separately in <https://github.com/clintecker/press/milestone/8>.

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
