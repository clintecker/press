# Invariants

An **invariant** is a promise the press keeps about what it produces -- something that must be true of a finished book no matter which book it is. *Every page carries ink. A release ships the exact bytes the tests approved. A slug can't escape its directory.* This page is the whole list of those promises.

Each promise is kept by real code (**enforced by**). Because a guard you never test is a guard you can't trust, each promise also has a test that deliberately breaks it and confirms the guard catches the violation (**tested by**). And each states, honestly, what its guard does *not* cover (**known limit**), so a narrow check is never mistaken for a broad one.

The promises are declared in one file, `quality/invariants.yaml`, and validated on every build: a promise with no real test -- or a critical one with no way to prove it can fail -- fails the build. So this page cannot drift from what the code actually does; it is generated from that ledger. A few are marked **critical**: breaking one would let a corrupt or unsafe book through, so they must carry a test that proves the guard can fail.

See also the narrative matrix in the [architecture guide](https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md) and the artifact table in the [command reference](https://github.com/clintecker/press/blob/main/docs/REFERENCE.md).

## Reader archive matches the site

`INV-archive-site-bytes` · standard

The reader zip is byte-for-byte the verified site directory.

| | |
|---|---|
| **If it breaks** | The downloadable reader disagrees with the site that was verified. |
| **Enforced by** | `verify_archives.verify_site_zip` |
| **Tested by** | `check_source_policy` |
| **Known limit** | Compares to the on-disk site, which must itself have been verified first. |

## Policy-clean source archive

`INV-archive-source-policy` · critical

The source zip holds exactly what the publication policy admits: tracked files only, symlinks never dereferenced, secret files abort, no member escapes its prefix.

| | |
|---|---|
| **If it breaks** | A public source archive leaks a secret or a file outside the repo. |
| **Enforced by** | `package_source.publication_members` |
| **Tested by** | `check_source_policy` |
| **Known limit** | Secret and junk patterns are fixed lists; a novel secret filename is not caught. |

## Authorities claims exist

`INV-authorities-claims` · standard

Every authorities claim appears in the manuscript exactly once in its declared file; malformed, duplicate, missing, moved, and ambiguous entries are each named.

| | |
|---|---|
| **If it breaks** | A citation outlives the sentence it attributed, rotting silently. |
| **Enforced by** | `gen_authorities` |
| **Tested by** | `check_authorities_ledger` |
| **Known limit** | Whitespace-normalized substring match; a coincidental duplicate counts as a hit. |

## Print-safe sources

`INV-authorities-printsafe` · standard

Researched source text is print-safe and TeX-safe.

| | |
|---|---|
| **If it breaks** | A citation carrying a backslash reaches the TeX engine as a command. |
| **Enforced by** | `gen_authorities.print_safe` |
| **Tested by** | `check_honest_refusals` |
| **Known limit** | Fixed replacement table. |

## Honest exit codes

`INV-cli-exit-code` · standard

A failing tool's exit code passes through the console, never a traceback.

| | |
|---|---|
| **If it breaks** | A pandoc or TeX failure ends in a Python traceback, not the tool's message. |
| **Enforced by** | `__main__.console` |
| **Tested by** | `check_honest_refusals` |
| **Known limit** | Only CalledProcessError is unwrapped. |

## Safe ordering config

`INV-commerce-config` · standard

The print-order CTA is generated only for an enabled, valid config; verification refuses a non-HTTPS storefront or policy link, an unnamed seller of record, an embedded secret, or an unknown key. A policy link the publisher omits is generated as an honest page on the site that discloses the seller of record; the rendered landing page carries the CTA exactly when ordering is enabled, every generated policy page exists, and no page leaks a secret.

| | |
|---|---|
| **If it breaks** | A book site advertises ordering with an insecure or broken link, leaks a credential into a public page, or hides who the seller is. |
| **Enforced by** | `commerce.validate` |
| **Tested by** | `check_commerce_config` |
| **Known limit** | Validates the config's shape and safety and the rendered page's shape; it cannot confirm the storefront URL is reachable or that the linked product is the qualified edition (the release gate and physical qualification do that). |

## Qualified before sale

`INV-commerce-release-gate` · standard

A book that advertises print ordering may not ship a release unless its config is valid and its exact edition passed a physical qualification; a missing, invalid, or unqualified edition fails the release gate closed, while a book that sells nothing ships freely.

| | |
|---|---|
| **If it breaks** | A book publishes an "order a print copy" link for an edition no one has verified a provider can actually print. |
| **Enforced by** | `commerce.release_problems` |
| **Tested by** | `check_commerce_release_gate` |
| **Known limit** | The pure gate decides on the config and whether the edition is qualified; the orchestrator that builds the edition identity from the print pack and matches inspections against it is proven by the pytest component test, and enforcement is release-gated (PRESS_RELEASE), advisory otherwise. |

## Locatable config errors

`INV-config-locatable` · standard

Config defects are collected and reported with file and key; YAML errors are located; a non-mapping config file is refused.

| | |
|---|---|
| **If it breaks** | An author faces a parser traceback instead of a fixable diagnostic. |
| **Enforced by** | `booklib.load_config_mapping` |
| **Tested by** | `check_honest_refusals`, `check_book_model` |
| **Known limit** | Some YAML errors carry no line mark. |

## Computed check digits

`INV-config-registrations` · standard

ISBN and ISSN check digits are computed, never trusted; retail mode fails on a pending number.

| | |
|---|---|
| **If it breaks** | A malformed identifier reaches a retail channel or the barcode. |
| **Enforced by** | `barcode.validate` |
| **Tested by** | `check_arithmetic` |
| **Known limit** | LCCN is shape-checked only; the ISBN is not matched to the barcode edition. |

## No vacuous releases

`INV-config-release-witness` · standard

Release builds refuse vacuous witnesses (fewer than two sentinels, page floor under twenty-four) when PRESS_RELEASE is set.

| | |
|---|---|
| **If it breaks** | A release is cut that no rendered artifact can be proven to be. |
| **Enforced by** | `booklib.require_release_witnesses` |
| **Tested by** | `integration` |
| **Known limit** | Counts only; two trivial sentinels satisfy it; drafts skip it. |

## Safe slugs

`INV-config-slug` · critical

A slug is strict lowercase kebab, safe as an artifact basename.

| | |
|---|---|
| **If it breaks** | A crafted slug escapes the dist directory or breaks a filename. |
| **Enforced by** | `booklib.validate_slug` |
| **Tested by** | `check_slug_invariant` |
| **Known limit** | Fullmatch of a fixed pattern; no other basename hazard is modeled. |

## Fixed v1 trim

`INV-config-trim` · standard

Trim is exactly 6 by 9 inches in v1; any other geometry is refused.

| | |
|---|---|
| **If it breaks** | A book ships at a size the design was never proven against. |
| **Enforced by** | `bookmodel.load` |
| **Tested by** | `check_book_model` |
| **Known limit** | Hard-coded to the v1 design; v2 geometry is unsupported by design. |

## AGENTS mirrors CLAUDE

`INV-contract-mirror` · standard

AGENTS.md is a byte-for-byte mirror of CLAUDE.md below the heading.

| | |
|---|---|
| **If it breaks** | The two contributor contracts drift apart and disagree. |
| **Enforced by** | `selftest.check_contract_mirror` |
| **Tested by** | `check_contract_mirror` |
| **Known limit** | Only the body below the first line is compared. |

## Scannable barcode panel

`INV-coverwrap-barcode` · standard

The barcode panel has its white card, enough bar transitions, and clean quiet zones.

| | |
|---|---|
| **If it breaks** | An unscannable or ink-fouled barcode ships on the retail cover. |
| **Enforced by** | `verify_coverwrap.scanline` |
| **Tested by** | `check_coverwrap_detectors` |
| **Known limit** | Twenty-five transitions against EAN-13's real fifty-nine; it proves a symbol, not the right symbol. |

## Cover-wrap geometry

`INV-coverwrap-geometry` · standard

The wrap is one page at exactly trim plus bleed plus spine, the spine recomputed from the built interior, never restated.

| | |
|---|---|
| **If it breaks** | A wrong-sized retail cover is produced and blessed. |
| **Enforced by** | `verify_coverwrap` |
| **Tested by** | `integration` |
| **Known limit** | Spine trusts the declared paper stock; a wrong stock yields a self-consistent wrong spine. |

## Docs never drift

`INV-docs-no-drift` · standard

Usage and README name every target, REFERENCE.md and INVARIANTS.md equal their generated text, and the aesthetics skill documents every consumed key.

| | |
|---|---|
| **If it breaks** | The documentation quietly diverges from what the code does. |
| **Enforced by** | `selftest.check_docs` |
| **Tested by** | `check_docs`, `check_aesthetic_schema` |
| **Known limit** | Presence tests, not semantic ones. |

## Immutable edition identity

`INV-edition-manifest` · critical

An edition manifest is immutable identity: any production-affecting fact mints a new edition_id, and verification refuses a forged identity, an interior or cover byte or page mismatch, an ill-formed or mutable reference, a forbidden price/secret/customer field, a manifest with no receipt chain or built from a dirty tree, and a provider qualification proven against a different edition.

| | |
|---|---|
| **If it breaks** | An order ships bytes that differ from the release-approved edition, or a manifest leaks a price, secret, or customer datum. |
| **Enforced by** | `edition.verify_facts` |
| **Tested by** | `check_edition_manifest` |
| **Known limit** | Verifies content identity against the artifacts on disk and the well-formedness of qualification evidence; it does not re-run a provider's physical qualification, only reject a qualification whose named edition is not this one. |

## Guarded banned patterns

`INV-editorial-banned-regex` · standard

A malformed book-supplied banned regex is refused by name.

| | |
|---|---|
| **If it breaks** | An author's regex slip becomes a parser traceback mid-audit. |
| **Enforced by** | `style_audit.banned_book_patterns` |
| **Tested by** | `check_honest_refusals` |
| **Known limit** | Only regex-compile errors are caught. |

## The prose battery

`INV-editorial-battery` · standard

The universal prose battery refuses dashes, curly quotes, out-of-font glyphs, throat-clearing, bad headings, and long paragraphs.

| | |
|---|---|
| **If it breaks** | Synthetic or print-unsafe prose reaches a published book. |
| **Enforced by** | `style_audit` |
| **Tested by** | `fixture:em-dash.md`, `fixture:curly-quotes.md`, `fixture:emoji.md`, `fixture:title-case.md`, `fixture:numbered-heading.md`, `fixture:long-paragraph.md` |
| **Known limit** | The glyph law flags legitimate Greek or math; short title-case headings slip. |

## Checkers proven by fixtures

`INV-editorial-checkers` · critical

Every known-bad fixture trips its declared rule; known-good passes clean.

| | |
|---|---|
| **If it breaks** | A checker silently stops catching what it was built to catch. |
| **Enforced by** | `check_the_checkers` |
| **Tested by** | `integration` |
| **Known limit** | A book fixture with no expect comment falls back to any-rejection. |

## Jargon watchlist

`INV-editorial-jargon` · standard

Watchlist terms at rewrite severity fail the run.

| | |
|---|---|
| **If it breaks** | Overused jargon the author outlawed survives into the book. |
| **Enforced by** | `jargon_lint` |
| **Tested by** | `fixture:jargon.md` |
| **Known limit** | Exact matches only; a per-book allow list can silence any term. |

## One witness per chapter

`INV-format-site-identity` · standard

Each chapter's witness appears exactly once across the reader site.

| | |
|---|---|
| **If it breaks** | A duplicated or missing chapter page passes on file count alone. |
| **Enforced by** | `verify_formats.verify_site` |
| **Tested by** | `check_site_identity` |
| **Known limit** | A chapter with no qualifying line contributes no witness. |

## A witness in every format

`INV-format-witness` · critical

Title and a derived manuscript witness appear in every format; a book yielding no witness is refused, not passed.

| | |
|---|---|
| **If it breaks** | A format silently drops the manuscript and still verifies. |
| **Enforced by** | `verify_formats.require_witnesses` |
| **Tested by** | `check_format_witnesses` |
| **Known limit** | One longest line per document; a format dropping every other line still passes. |

## Acyclic artifact graph

`INV-graph-acyclic` · standard

The artifact graph is acyclic, outputs unique, every published artifact a concrete filename.

| | |
|---|---|
| **If it breaks** | A build order cycles or an artifact has no real output. |
| **Enforced by** | `registry.build_order` |
| **Tested by** | `check_registry` |
| **Known limit** | Proves graph shape, not that each builder produces its declared output. |

## Escaped interpolation

`INV-graph-escaping` · standard

Metadata interpolated into HTML and TeX is escaped.

| | |
|---|---|
| **If it breaks** | A title with markup corrupts the single-file HTML or injects TeX. |
| **Enforced by** | `build.cover_fragment_html` |
| **Tested by** | `check_honest_refusals` |
| **Known limit** | The proof covers the cover fragment; sibling sites share the pattern unproven. |

## No stale artifact is blessed

`INV-graph-no-stale` · critical

Verify targets rebuild before verifying; a stale artifact cannot be blessed.

| | |
|---|---|
| **If it breaks** | A verifier passes an old artifact that no longer matches the source. |
| **Enforced by** | `__main__` |
| **Tested by** | `integration` |
| **Known limit** | CLI-path only; importing a verifier module directly skips the rebuild. |

## Every reference resolves

`INV-pages-refs` · standard

Every local reference and stylesheet url resolves; fragments resolve to real anchors.

| | |
|---|---|
| **If it breaks** | The public site ships dead links or a stylesheet pointing at nothing. |
| **Enforced by** | `verify_pages.check_refs` |
| **Tested by** | `check_pages_verifier` |
| **Known limit** | External links are skipped; a dead external URL is never caught. |

## Proven blank-page detector

`INV-pdf-detector` · critical

The blank-page detector is proven against fixtures before it judges.

| | |
|---|---|
| **If it breaks** | A miscalibrated detector passes blank pages or fails inked ones. |
| **Enforced by** | `verify_pdf.self_test_detector` |
| **Tested by** | `check_coverwrap_detectors` |
| **Known limit** | Two synthetic extremes; a faint hairline can still read as blank. |

## Every page carries ink

`INV-pdf-ink` · standard

Every rendered page carries ink and keeps it off the edge.

| | |
|---|---|
| **If it breaks** | A blank or clipped page ships in the interior. |
| **Enforced by** | `verify_pdf.verify_page_ink` |
| **Tested by** | `integration` |
| **Known limit** | Tolerates one structural blank verso in the print profile. |

## Provider-neutral contract

`INV-provider-contract` · critical

Every print-provider adapter maps its own vocabulary to the neutral contract: money is integer minor units parsed without binary float, an unrecognized status quarantines to UNKNOWN, a submission timeout is an unknown outcome that forces a lookup before any resubmission (never a hidden retry or a fabricated acceptance), an unsupported capability is a typed refusal rather than a simulation, and a webhook is authentic only when its signature matches the raw body.

| | |
|---|---|
| **If it breaks** | A provider coupling leaks SDK types into the domain, a lost response prints a second copy, an unknown status is guessed, or a forged webhook is trusted. |
| **Enforced by** | `providers.contract` |
| **Tested by** | `check_provider_contract` |
| **Known limit** | The contract and the conformance suite are proven against the smart fake and the Lulu adapter under a canned transport; the live Lulu sandbox exchange awaits credentials (the deferred end-to-end proof). |

## Honest provider record

`INV-provider-qualification` · standard

The provider record declares every capability explicitly (an omitted capability is a forbidden implicit claim) and the full physical checklist; a provider is qualified for an edition only by a physical inspection with every checklist point passed, scoped to that edition's identity, so a marketing claim, a failed point, a not-fit provider, and an inspection of a different edition are all refused.

| | |
|---|---|
| **If it breaks** | A book is sold as printable by a provider that cannot produce the exact object, or a qualification survives a production-affecting change to the edition. |
| **Enforced by** | `qualification.qualify` |
| **Tested by** | `check_provider_qualification` |
| **Known limit** | Validates the record's shape and the physical-gate logic; it cannot confirm a claimed inspection actually happened, only that a qualification carries a passed, edition-scoped inspection digest. |

## Immutable release contract

`INV-release-contract` · standard

A three-part tag pins its own action ref and an existing immutable toolchain image, proven before the major floats.

| | |
|---|---|
| **If it breaks** | A pinned book resolves a different pipeline than the tag promises. |
| **Enforced by** | `selftest.check_release_grammar` |
| **Tested by** | `none` |
| **Known limit** | The pin grep is an exact string; it does not prove the tag's tree. |

## Complete release chain

`INV-release-receipt-chain` · critical

A release chain refuses a missing, tampered, reordered, or input-mismatched prerequisite, a dirty-tree receipt, a terminal receipt whose package or toolchain does not match the built and pinned objects, an incomplete chain that skips any trust layer or breaks a layer's extension of its predecessor, and, when assembled from per-job receipts, a missing CI tier (a job that did not run leaves no receipt) or receipts that disagree on the source commit.

| | |
|---|---|
| **If it breaks** | A release ships objects that differ from the ones the tests proved. |
| **Enforced by** | `receipts.verify_release` |
| **Tested by** | `check_receipt_chain` |
| **Known limit** | The per-job assembly makes the chain reflect the CI jobs that actually ran and uploaded a receipt; it trusts that an uploaded tier receipt attests real work, and the cross-workflow artifact download is proven only by a live release, not the fast suite. |

## Strict release tags

`INV-release-tag-grammar` · critical

A release tag is strict SemVer and the composite action refuses shell syntax in its command input.

| | |
|---|---|
| **If it breaks** | A malformed tag or an injected command reaches the release path. |
| **Enforced by** | `selftest.check_release_grammar` |
| **Tested by** | `check_release_grammar` |
| **Known limit** | The action grammar is proven by unit test, not by a live workflow run. |

## Neutral scaffold

`INV-scaffold-neutral` · standard

No original-book identity leaks into a clean scaffold.

| | |
|---|---|
| **If it breaks** | A new book inherits another book's name, person, or imprint. |
| **Enforced by** | `selftest.check_scaffold_neutrality` |
| **Tested by** | `check_scaffold_neutrality` |
| **Known limit** | Pattern-based; a novel identifying string is not caught. |
