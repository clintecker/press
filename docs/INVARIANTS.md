# Invariants

Generated from quality/invariants.yaml; do not edit by hand.
Run `python3 -m press selftest --write-docs` after changing the
ledger. Each row traces an invariant to where it is enforced, the
proof it can fail, and the honest limit of that proof.

See also the narrative matrix in [docs/ARCHITECTURE.md](https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md) and the artifact table in [docs/REFERENCE.md](https://github.com/clintecker/press/blob/main/docs/REFERENCE.md).

| id | invariant | enforced at | proof it can fail | limitation |
|---|---|---|---|---|
| INV-archive-site-bytes | The reader zip is byte-for-byte the verified site directory. | `verify_archives.verify_site_zip` | check_source_policy | Compares to the on-disk site, which must itself have been verified first. |
| INV-archive-source-policy (critical) | The source zip holds exactly what the publication policy admits: tracked files only, symlinks never dereferenced, secret files abort, no member escapes its prefix. | `package_source.publication_members` | check_source_policy | Secret and junk patterns are fixed lists; a novel secret filename is not caught. |
| INV-authorities-claims | Every authorities claim appears in the manuscript exactly once in its declared file; malformed, duplicate, missing, moved, and ambiguous entries are each named. | `gen_authorities` | check_authorities_ledger | Whitespace-normalized substring match; a coincidental duplicate counts as a hit. |
| INV-authorities-printsafe | Researched source text is print-safe and TeX-safe. | `gen_authorities.print_safe` | check_honest_refusals | Fixed replacement table. |
| INV-cli-exit-code | A failing tool's exit code passes through the console, never a traceback. | `__main__.console` | check_honest_refusals | Only CalledProcessError is unwrapped. |
| INV-config-locatable | Config defects are collected and reported with file and key; YAML errors are located; a non-mapping config file is refused. | `booklib.load_config_mapping` | check_honest_refusals, check_book_model | Some YAML errors carry no line mark. |
| INV-config-registrations | ISBN and ISSN check digits are computed, never trusted; retail mode fails on a pending number. | `barcode.validate` | check_arithmetic | LCCN is shape-checked only; the ISBN is not matched to the barcode edition. |
| INV-config-release-witness | Release builds refuse vacuous witnesses (fewer than two sentinels, page floor under twenty-four) when PRESS_RELEASE is set. | `booklib.require_release_witnesses` | integration | Counts only; two trivial sentinels satisfy it; drafts skip it. |
| INV-config-slug (critical) | A slug is strict lowercase kebab, safe as an artifact basename. | `booklib.validate_slug` | check_slug_invariant | Fullmatch of a fixed pattern; no other basename hazard is modeled. |
| INV-config-trim | Trim is exactly 6 by 9 inches in v1; any other geometry is refused. | `bookmodel.load` | check_book_model | Hard-coded to the v1 design; v2 geometry is unsupported by design. |
| INV-contract-mirror | AGENTS.md is a byte-for-byte mirror of CLAUDE.md below the heading. | `selftest.check_contract_mirror` | check_contract_mirror | Only the body below the first line is compared. |
| INV-coverwrap-barcode | The barcode panel has its white card, enough bar transitions, and clean quiet zones. | `verify_coverwrap.scanline` | check_coverwrap_detectors | Twenty-five transitions against EAN-13's real fifty-nine; it proves a symbol, not the right symbol. |
| INV-coverwrap-geometry | The wrap is one page at exactly trim plus bleed plus spine, the spine recomputed from the built interior, never restated. | `verify_coverwrap` | integration | Spine trusts the declared paper stock; a wrong stock yields a self-consistent wrong spine. |
| INV-docs-no-drift | Usage and README name every target, REFERENCE.md and INVARIANTS.md equal their generated text, and the aesthetics skill documents every consumed key. | `selftest.check_docs` | check_docs, check_aesthetic_schema | Presence tests, not semantic ones. |
| INV-editorial-banned-regex | A malformed book-supplied banned regex is refused by name. | `style_audit.banned_book_patterns` | check_honest_refusals | Only regex-compile errors are caught. |
| INV-editorial-battery | The universal prose battery refuses dashes, curly quotes, out-of-font glyphs, throat-clearing, bad headings, and long paragraphs. | `style_audit` | fixture:em-dash.md, fixture:curly-quotes.md, fixture:emoji.md, fixture:title-case.md, fixture:numbered-heading.md, fixture:long-paragraph.md | The glyph law flags legitimate Greek or math; short title-case headings slip. |
| INV-editorial-checkers (critical) | Every known-bad fixture trips its declared rule; known-good passes clean. | `check_the_checkers` | integration | A book fixture with no expect comment falls back to any-rejection. |
| INV-editorial-jargon | Watchlist terms at rewrite severity fail the run. | `jargon_lint` | fixture:jargon.md | Exact matches only; a per-book allow list can silence any term. |
| INV-format-site-identity | Each chapter's witness appears exactly once across the reader site. | `verify_formats.verify_site` | check_site_identity | A chapter with no qualifying line contributes no witness. |
| INV-format-witness (critical) | Title and a derived manuscript witness appear in every format; a book yielding no witness is refused, not passed. | `verify_formats.require_witnesses` | check_format_witnesses | One longest line per document; a format dropping every other line still passes. |
| INV-graph-acyclic | The artifact graph is acyclic, outputs unique, every published artifact a concrete filename. | `registry.build_order` | check_registry | Proves graph shape, not that each builder produces its declared output. |
| INV-graph-escaping | Metadata interpolated into HTML and TeX is escaped. | `build.cover_fragment_html` | check_honest_refusals | The proof covers the cover fragment; sibling sites share the pattern unproven. |
| INV-graph-no-stale (critical) | Verify targets rebuild before verifying; a stale artifact cannot be blessed. | `__main__` | integration | CLI-path only; importing a verifier module directly skips the rebuild. |
| INV-pages-refs | Every local reference and stylesheet url resolves; fragments resolve to real anchors. | `verify_pages.check_refs` | check_pages_verifier | External links are skipped; a dead external URL is never caught. |
| INV-pdf-detector (critical) | The blank-page detector is proven against fixtures before it judges. | `verify_pdf.self_test_detector` | check_coverwrap_detectors | Two synthetic extremes; a faint hairline can still read as blank. |
| INV-pdf-ink | Every rendered page carries ink and keeps it off the edge. | `verify_pdf.verify_page_ink` | integration | Tolerates one structural blank verso in the print profile. |
| INV-release-contract | A three-part tag pins its own action ref and an existing immutable toolchain image, proven before the major floats. | `selftest.check_release_grammar` | none | The pin grep is an exact string; it does not prove the tag's tree. |
| INV-release-receipt-chain (critical) | A release chain refuses a missing, tampered, reordered, or input-mismatched prerequisite, a dirty-tree receipt, and a terminal receipt whose package or toolchain does not match the built and pinned objects. | `receipts.verify_release` | check_receipt_chain | The per-layer prerequisite chain awaits the layered-CI change; the release identity (commit, package, toolchain, manifests) is proven now. |
| INV-release-tag-grammar (critical) | A release tag is strict SemVer and the composite action refuses shell syntax in its command input. | `selftest.check_release_grammar` | check_release_grammar | The action grammar is proven by unit test, not by a live workflow run. |
| INV-scaffold-neutral | No original-book identity leaks into a clean scaffold. | `selftest.check_scaffold_neutrality` | check_scaffold_neutrality | Pattern-based; a novel identifying string is not caught. |
