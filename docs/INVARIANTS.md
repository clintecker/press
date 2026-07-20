# Invariants

Generated from quality/invariants.yaml; do not edit by hand. Run
`python3 -m press selftest --write-docs` after changing the ledger.
Each entry traces an invariant to where it is enforced, the proof it
can fail, and the honest limit of that proof.

See also the narrative matrix in [docs/ARCHITECTURE.md](https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md) and the artifact table in [docs/REFERENCE.md](https://github.com/clintecker/press/blob/main/docs/REFERENCE.md).

## INV-archive-site-bytes

The reader zip is byte-for-byte the verified site directory.

> Enforced by `verify_archives.verify_site_zip` · fails via `check_source_policy` · standard. **Limit:** Compares to the on-disk site, which must itself have been verified first.

## INV-archive-source-policy

The source zip holds exactly what the publication policy admits: tracked files only, symlinks never dereferenced, secret files abort, no member escapes its prefix.

> Enforced by `package_source.publication_members` · fails via `check_source_policy` · **critical**. **Limit:** Secret and junk patterns are fixed lists; a novel secret filename is not caught.

## INV-authorities-claims

Every authorities claim appears in the manuscript exactly once in its declared file; malformed, duplicate, missing, moved, and ambiguous entries are each named.

> Enforced by `gen_authorities` · fails via `check_authorities_ledger` · standard. **Limit:** Whitespace-normalized substring match; a coincidental duplicate counts as a hit.

## INV-authorities-printsafe

Researched source text is print-safe and TeX-safe.

> Enforced by `gen_authorities.print_safe` · fails via `check_honest_refusals` · standard. **Limit:** Fixed replacement table.

## INV-cli-exit-code

A failing tool's exit code passes through the console, never a traceback.

> Enforced by `__main__.console` · fails via `check_honest_refusals` · standard. **Limit:** Only CalledProcessError is unwrapped.

## INV-commerce-config

The print-order CTA is generated only for an enabled, valid config; verification refuses an enabled block with a non-HTTPS storefront or policy link, an unnamed seller of record, an embedded secret, or an unknown key, and the rendered landing page carries the CTA (with the storefront, seller, and every policy link) exactly when ordering is enabled, and no page leaks a secret.

> Enforced by `commerce.validate` · fails via `check_commerce_config` · standard. **Limit:** Validates the config's shape and safety and the rendered page's shape; it cannot confirm the storefront URL is reachable or that the linked product is the qualified edition (the release gate and physical qualification do that).

## INV-commerce-release-gate

A book that advertises print ordering may not ship a release unless its config is valid and its exact edition passed a physical qualification; a missing, invalid, or unqualified edition fails the release gate closed, while a book that sells nothing ships freely.

> Enforced by `commerce.release_problems` · fails via `check_commerce_release_gate` · standard. **Limit:** The pure gate decides on the config and whether the edition is qualified; the orchestrator that builds the edition identity from the print pack and matches inspections against it is proven by the pytest component test, and enforcement is release-gated (PRESS_RELEASE), advisory otherwise.

## INV-config-locatable

Config defects are collected and reported with file and key; YAML errors are located; a non-mapping config file is refused.

> Enforced by `booklib.load_config_mapping` · fails via `check_honest_refusals`, `check_book_model` · standard. **Limit:** Some YAML errors carry no line mark.

## INV-config-registrations

ISBN and ISSN check digits are computed, never trusted; retail mode fails on a pending number.

> Enforced by `barcode.validate` · fails via `check_arithmetic` · standard. **Limit:** LCCN is shape-checked only; the ISBN is not matched to the barcode edition.

## INV-config-release-witness

Release builds refuse vacuous witnesses (fewer than two sentinels, page floor under twenty-four) when PRESS_RELEASE is set.

> Enforced by `booklib.require_release_witnesses` · fails via `integration` · standard. **Limit:** Counts only; two trivial sentinels satisfy it; drafts skip it.

## INV-config-slug

A slug is strict lowercase kebab, safe as an artifact basename.

> Enforced by `booklib.validate_slug` · fails via `check_slug_invariant` · **critical**. **Limit:** Fullmatch of a fixed pattern; no other basename hazard is modeled.

## INV-config-trim

Trim is exactly 6 by 9 inches in v1; any other geometry is refused.

> Enforced by `bookmodel.load` · fails via `check_book_model` · standard. **Limit:** Hard-coded to the v1 design; v2 geometry is unsupported by design.

## INV-contract-mirror

AGENTS.md is a byte-for-byte mirror of CLAUDE.md below the heading.

> Enforced by `selftest.check_contract_mirror` · fails via `check_contract_mirror` · standard. **Limit:** Only the body below the first line is compared.

## INV-coverwrap-barcode

The barcode panel has its white card, enough bar transitions, and clean quiet zones.

> Enforced by `verify_coverwrap.scanline` · fails via `check_coverwrap_detectors` · standard. **Limit:** Twenty-five transitions against EAN-13's real fifty-nine; it proves a symbol, not the right symbol.

## INV-coverwrap-geometry

The wrap is one page at exactly trim plus bleed plus spine, the spine recomputed from the built interior, never restated.

> Enforced by `verify_coverwrap` · fails via `integration` · standard. **Limit:** Spine trusts the declared paper stock; a wrong stock yields a self-consistent wrong spine.

## INV-docs-no-drift

Usage and README name every target, REFERENCE.md and INVARIANTS.md equal their generated text, and the aesthetics skill documents every consumed key.

> Enforced by `selftest.check_docs` · fails via `check_docs`, `check_aesthetic_schema` · standard. **Limit:** Presence tests, not semantic ones.

## INV-edition-manifest

An edition manifest is immutable identity: any production-affecting fact mints a new edition_id, and verification refuses a forged identity, an interior or cover byte or page mismatch, an ill-formed or mutable reference, a forbidden price/secret/customer field, a manifest with no receipt chain or built from a dirty tree, and a provider qualification proven against a different edition.

> Enforced by `edition.verify_facts` · fails via `check_edition_manifest` · **critical**. **Limit:** Verifies content identity against the artifacts on disk and the well-formedness of qualification evidence; it does not re-run a provider's physical qualification, only reject a qualification whose named edition is not this one.

## INV-editorial-banned-regex

A malformed book-supplied banned regex is refused by name.

> Enforced by `style_audit.banned_book_patterns` · fails via `check_honest_refusals` · standard. **Limit:** Only regex-compile errors are caught.

## INV-editorial-battery

The universal prose battery refuses dashes, curly quotes, out-of-font glyphs, throat-clearing, bad headings, and long paragraphs.

> Enforced by `style_audit` · fails via `fixture:em-dash.md`, `fixture:curly-quotes.md`, `fixture:emoji.md`, `fixture:title-case.md`, `fixture:numbered-heading.md`, `fixture:long-paragraph.md` · standard. **Limit:** The glyph law flags legitimate Greek or math; short title-case headings slip.

## INV-editorial-checkers

Every known-bad fixture trips its declared rule; known-good passes clean.

> Enforced by `check_the_checkers` · fails via `integration` · **critical**. **Limit:** A book fixture with no expect comment falls back to any-rejection.

## INV-editorial-jargon

Watchlist terms at rewrite severity fail the run.

> Enforced by `jargon_lint` · fails via `fixture:jargon.md` · standard. **Limit:** Exact matches only; a per-book allow list can silence any term.

## INV-format-site-identity

Each chapter's witness appears exactly once across the reader site.

> Enforced by `verify_formats.verify_site` · fails via `check_site_identity` · standard. **Limit:** A chapter with no qualifying line contributes no witness.

## INV-format-witness

Title and a derived manuscript witness appear in every format; a book yielding no witness is refused, not passed.

> Enforced by `verify_formats.require_witnesses` · fails via `check_format_witnesses` · **critical**. **Limit:** One longest line per document; a format dropping every other line still passes.

## INV-graph-acyclic

The artifact graph is acyclic, outputs unique, every published artifact a concrete filename.

> Enforced by `registry.build_order` · fails via `check_registry` · standard. **Limit:** Proves graph shape, not that each builder produces its declared output.

## INV-graph-escaping

Metadata interpolated into HTML and TeX is escaped.

> Enforced by `build.cover_fragment_html` · fails via `check_honest_refusals` · standard. **Limit:** The proof covers the cover fragment; sibling sites share the pattern unproven.

## INV-graph-no-stale

Verify targets rebuild before verifying; a stale artifact cannot be blessed.

> Enforced by `__main__` · fails via `integration` · **critical**. **Limit:** CLI-path only; importing a verifier module directly skips the rebuild.

## INV-pages-refs

Every local reference and stylesheet url resolves; fragments resolve to real anchors.

> Enforced by `verify_pages.check_refs` · fails via `check_pages_verifier` · standard. **Limit:** External links are skipped; a dead external URL is never caught.

## INV-pdf-detector

The blank-page detector is proven against fixtures before it judges.

> Enforced by `verify_pdf.self_test_detector` · fails via `check_coverwrap_detectors` · **critical**. **Limit:** Two synthetic extremes; a faint hairline can still read as blank.

## INV-pdf-ink

Every rendered page carries ink and keeps it off the edge.

> Enforced by `verify_pdf.verify_page_ink` · fails via `integration` · standard. **Limit:** Tolerates one structural blank verso in the print profile.

## INV-provider-contract

Every print-provider adapter maps its own vocabulary to the neutral contract: money is integer minor units parsed without binary float, an unrecognized status quarantines to UNKNOWN, a submission timeout is an unknown outcome that forces a lookup before any resubmission (never a hidden retry or a fabricated acceptance), an unsupported capability is a typed refusal rather than a simulation, and a webhook is authentic only when its signature matches the raw body.

> Enforced by `providers.contract` · fails via `check_provider_contract` · **critical**. **Limit:** The contract and the conformance suite are proven against the smart fake and the Lulu adapter under a canned transport; the live Lulu sandbox exchange awaits credentials (the deferred end-to-end proof).

## INV-provider-qualification

The provider record declares every capability explicitly (an omitted capability is a forbidden implicit claim) and the full physical checklist; a provider is qualified for an edition only by a physical inspection with every checklist point passed, scoped to that edition's identity, so a marketing claim, a failed point, a not-fit provider, and an inspection of a different edition are all refused.

> Enforced by `qualification.qualify` · fails via `check_provider_qualification` · standard. **Limit:** Validates the record's shape and the physical-gate logic; it cannot confirm a claimed inspection actually happened, only that a qualification carries a passed, edition-scoped inspection digest.

## INV-release-contract

A three-part tag pins its own action ref and an existing immutable toolchain image, proven before the major floats.

> Enforced by `selftest.check_release_grammar` · fails via `none` · standard. **Limit:** The pin grep is an exact string; it does not prove the tag's tree.

## INV-release-receipt-chain

A release chain refuses a missing, tampered, reordered, or input-mismatched prerequisite, a dirty-tree receipt, a terminal receipt whose package or toolchain does not match the built and pinned objects, an incomplete chain that skips any trust layer or breaks a layer's extension of its predecessor, and, when assembled from per-job receipts, a missing CI tier (a job that did not run leaves no receipt) or receipts that disagree on the source commit.

> Enforced by `receipts.verify_release` · fails via `check_receipt_chain` · **critical**. **Limit:** The per-job assembly makes the chain reflect the CI jobs that actually ran and uploaded a receipt; it trusts that an uploaded tier receipt attests real work, and the cross-workflow artifact download is proven only by a live release, not the fast suite.

## INV-release-tag-grammar

A release tag is strict SemVer and the composite action refuses shell syntax in its command input.

> Enforced by `selftest.check_release_grammar` · fails via `check_release_grammar` · **critical**. **Limit:** The action grammar is proven by unit test, not by a live workflow run.

## INV-scaffold-neutral

No original-book identity leaks into a clean scaffold.

> Enforced by `selftest.check_scaffold_neutrality` · fails via `check_scaffold_neutrality` · standard. **Limit:** Pattern-based; a novel identifying string is not caught.
