# System invariants

## INV-add-no-clobber

Adding a chapter refuses to overwrite an existing file.

- enforced by `add:main`
- proven by `tests/test_add.py::test_add_refuses_to_overwrite_an_existing_file`

## INV-archive-site-bytes

The reader zip is byte-for-byte the verified site directory.

- enforced by `verify_archives:verify_site_zip`
- proven by `tests/test_properties_policy.py::test_secret_named_file_is_never_admitted`
- does not cover: Compares to the on-disk site, which must itself have been verified first.

## INV-archive-source-policy **(critical)**

The source zip holds exactly what the publication policy admits: tracked files only, symlinks never dereferenced, secret files abort, no member escapes its prefix.

- enforced by `package_source:publication_members`
- proven by `tests/test_properties_policy.py::test_secret_named_file_is_never_admitted`
- does not cover: Secret and junk patterns are fixed lists; a novel secret filename is not caught.

## INV-art-key-never-stored

The image-model key is read from the environment on demand and its absence is refused, never stored.

- enforced by `art_commission:key_for`
- proven by `tests/test_adapters_routing.py::test_key_for_refuses_when_unset`

## INV-artifact-state-by-digest

Artifact state derives from content digests, not mtimes: touching a file without changing it stays verified.

- enforced by `artifact_status:artifact_state`
- proven by `tests/test_artifact_status.py::test_touch_without_change_stays_verified`

## INV-authorities-claims

Every authorities claim appears in the manuscript exactly once in its declared file; malformed, duplicate, missing, moved, and ambiguous entries are each named.

- enforced by `gen_authorities:generate`
- proven by `tests/test_selftest_checks.py::test_invariant_check_passes[check_authorities_ledger]`
- does not cover: Whitespace-normalized substring match; a coincidental duplicate counts as a hit.

## INV-authorities-printsafe

Researched source text is print-safe and TeX-safe.

- enforced by `gen_authorities:print_safe`
- proven by `src/press/selftest.py::check_honest_refusals`
- does not cover: Fixed replacement table.

## INV-catalog-route-parity

Every CLI route is a catalog command and every catalog command is dispatchable.

- enforced by `catalog:canonical_targets`
- proven by `tests/test_catalog.py::test_every_route_is_a_catalog_command`

## INV-check-source-fails-closed

The source checker exits nonzero on a malformed authorities ledger and its figure/print variants.

- enforced by `check_source:main`
- proven by `tests/test_config_shapes.py::test_check_source_rejects_a_malformed_authorities_ledger`

## INV-cli-exit-code

A failing tool's exit code passes through the console, never a traceback.

- enforced by `__main__:console`
- proven by `src/press/selftest.py::check_honest_refusals`
- does not cover: Only CalledProcessError is unwrapped.

## INV-commerce-config

The print-order CTA is generated only for an enabled, valid config; verification refuses a non-HTTPS storefront or policy link, an unnamed seller of record, an embedded secret, or an unknown key. A policy link the publisher omits is generated as an honest page on the site that discloses the seller of record; the rendered landing page carries the CTA exactly when ordering is enabled, every generated policy page exists, and no page leaks a secret.

- enforced by `commerce:validate`
- proven by `tests/test_commerce.py::test_an_embedded_secret_is_refused`
- does not cover: Validates the config's shape and safety and the rendered page's shape; it cannot confirm the storefront URL is reachable or that the linked product is the qualified edition (the release gate and physical qualification do that).

## INV-commerce-release-gate

A book that advertises print ordering may not ship a release unless its config is valid and its exact edition passed a physical qualification; a missing, invalid, or unqualified edition fails the release gate closed, while a book that sells nothing ships freely.

- enforced by `commerce:release_problems`
- proven by `tests/test_commerce.py::test_release_gate_refuses_an_unqualified_edition`
- does not cover: The pure gate decides on the config and whether the edition is qualified; the orchestrator that builds the edition identity from the print pack and matches inspections against it is proven by the pytest component test, and enforcement is release-gated (PRESS_RELEASE), advisory otherwise.

## INV-config-locatable

Config defects are collected and reported with file and key; YAML errors are located; a non-mapping config file is refused.

- enforced by `booklib:load_config_mapping`
- proven by `src/press/selftest.py::check_honest_refusals`
- proven by `src/press/selftest.py::check_book_model`
- does not cover: Some YAML errors carry no line mark.

## INV-config-registrations

ISBN and ISSN check digits are computed, never trusted; retail mode fails on a pending number.

- enforced by `barcode:validate`
- proven by `src/press/selftest.py::check_arithmetic`
- does not cover: LCCN is shape-checked only; the ISBN is not matched to the barcode edition.

## INV-config-release-witness

Release builds refuse vacuous witnesses (fewer than two sentinels, page floor under twenty-four) when PRESS_RELEASE is set.

- enforced by `booklib:require_release_witnesses`
- proven by `tests/test_sabotage.py::test_sabotage_removed_graph_edge_reddens_state_model`
- does not cover: Counts only; two trivial sentinels satisfy it; drafts skip it.

## INV-config-schema-shape

Config validation returns problems for a wrong-shaped file, and enforcement fails closed.

- enforced by `config_schema:validate_file`
- proven by `tests/test_config_shapes.py::test_index_terms_terms_wrapper_is_refused_by_shape`

## INV-config-slug **(critical)**

A slug is strict lowercase kebab, safe as an artifact basename.

- enforced by `booklib:validate_slug`
- proven by `tests/test_selftest_checks.py::test_slug_invariant_rejects_bad`
- does not cover: Fullmatch of a fixed pattern; no other basename hazard is modeled.

## INV-config-store-never-guess

Config coercion never guesses a collection type: a collection field requires explicit JSON.

- enforced by `config_store:coerce`
- proven by `tests/test_config_store.py::test_a_collection_field_requires_explicit_json`

## INV-config-trim

Trim comes from the selected design profile, never a hand-entered number; a metadata trim that disagrees with the profile is refused.

- enforced by `bookmodel:load`
- proven by `src/press/selftest.py::check_book_model`
- does not cover: The house profile is 6 by 9, so a book selecting no profile keeps the v1 trim; non-house profiles owe visual qualification.

## INV-contract-mirror

AGENTS.md is a byte-for-byte mirror of CLAUDE.md below the heading.

- enforced by `selftest_release:check_contract_mirror`
- proven by `tests/test_selftest_checks.py::test_contract_mirror_names_drift_between_agent_instructions`
- does not cover: Only the body below the first line is compared.

## INV-cover-baked-guard

A baked cover style fills every placeholder and carries the exact-text guardrail.

- enforced by `cover:build_prompt`
- proven by `tests/test_cover.py::test_build_prompt_fills_and_guards_baked_style`

## INV-coverwrap-barcode

The barcode panel has its white card, enough bar transitions, and clean quiet zones.

- enforced by `verify_coverwrap:scanline`
- proven by `src/press/selftest.py::check_coverwrap_detectors`
- does not cover: Twenty-five transitions against EAN-13's real fifty-nine; it proves a symbol, not the right symbol.

## INV-coverwrap-composer-geometry

The cover-wrap geometry composer reproduces the sealed v1 perfect-bound geometry exactly.

- enforced by `gen_coverwrap:wrap_geometry`
- proven by `tests/test_coverwrap_layout.py::test_perfect_bound_reproduces_v1_geometry`

## INV-coverwrap-geometry

The wrap is one page at exactly trim plus bleed plus spine, the spine recomputed from the built interior, never restated.

- enforced by `verify_coverwrap:main`
- proven by `tests/test_sabotage.py::test_sabotage_removed_graph_edge_reddens_state_model`
- does not cover: Spine trusts the declared paper stock; a wrong stock yields a self-consistent wrong spine.

## INV-design-layout-stable

A valid v1 book renders at the committed house geometry -- page count, embedded fonts, and per-page trim and ink bounds within tolerance -- so the house typography and layout cannot change within a major without a deliberate, reasoned baseline decision.

- enforced by `build:build_target`
- proven by `tests/test_sabotage.py::test_sabotage_removed_graph_edge_reddens_state_model`
- does not cover: requires capability: pandoc
- does not cover: Toolchain-gated: the rendered comparison runs only where pandoc, LuaLaTeX, and the poppler tools are present, and the reviewed baseline is regenerated in the pinned toolchain, never silently. The comparison's bite (a font swap, a margin shift, a page-count change are each drift) is proven against the committed baseline without the toolchain. Two chapters and pages one and two are sampled; geometry is toolchain-stable only to the declared tolerance, so a sub-tolerance shift is not caught.

## INV-desk-blocks-unrunnable

The operator desk grays out a blocked command so it cannot launch into a guaranteed failure.

- enforced by `desk.app:PickerScreen.compose`
- proven by `tests/test_desk_polish.py::test_picker_grays_out_a_blocked_command`
- does not cover: Proven only where the tui extra (textual) is installed.

## INV-desk-model-blocks-build

Build commands are blocked when the required toolchain is missing, while toolchain-free commands stay runnable.

- enforced by `desk_model:DeskModel.blocked_reason`
- proven by `tests/test_desk_model.py::test_missing_toolchain_blocks_build_commands`

## INV-docs-no-drift

Usage and README name every target, REFERENCE.md and INVARIANTS.md equal their generated text, and the aesthetics skill documents every consumed key.

- enforced by `selftest_release:check_docs`
- proven by `tests/test_selftest_checks.py::test_docs_check_names_a_drifted_provider_qualification_page`
- proven by `src/press/selftest.py::check_aesthetic_schema`
- does not cover: Presence tests, not semantic ones.

## INV-doctor-denies-broken

A missing required tool denies the machine; the verdict derives from the findings.

- enforced by `doctor:examine`
- proven by `tests/test_doctor_findings.py::test_required_tool_missing_denies_machine`

## INV-dropcap-opening

When a design enables a chapter-opening drop cap, the initial is placed on the first eligible prose paragraph after each chapter heading and nowhere else: an epigraph or other non-prose opener is skipped to the real opening paragraph, only the first paragraph is capped, and the manuscript carries no renderer markup. Any leading punctuation a chapter opening on dialogue carries -- an opening quote or a dash -- is set beside the initial at its size (through lettrine's ante, or its own floated span on the web), never scaled up into the initial and stranded above it. When the style is off, the filter changes nothing, so a book that does not opt in renders unchanged; and a book whose chapters open on ordinary words compiles to the same lettrine call whatever style it uses.

- enforced by `dropcaps:split_initial`
- proven by `tests/test_sabotage.py::test_sabotage_removed_graph_edge_reddens_state_model`
- does not cover: requires capability: pandoc
- does not cover: The eligibility and emission are proven by running the Lua filter through pandoc; the rendered PDF (which needs the lettrine package from the toolchain image) is proven where that toolchain is present. The grapheme and punctuation split is proven exhaustively in test_dropcaps.

## INV-edition-manifest **(critical)**

An edition manifest is immutable identity: any production-affecting fact mints a new edition_id, and verification refuses a forged identity, an interior or cover byte or page mismatch, an ill-formed or mutable reference, a forbidden price/secret/customer field, a manifest with no receipt chain or built from a dirty tree, and a provider qualification proven against a different edition.

- enforced by `edition:verify_facts`
- proven by `tests/test_edition.py::test_forged_identity_is_refused`
- does not cover: Verifies content identity against the artifacts on disk and the well-formedness of qualification evidence; it does not re-run a provider's physical qualification, only reject a qualification whose named edition is not this one.

## INV-editorial-banned-regex

A malformed book-supplied banned regex is refused by name.

- enforced by `style_audit:banned_book_patterns`
- proven by `src/press/selftest.py::check_honest_refusals`
- does not cover: Only regex-compile errors are caught.

## INV-editorial-battery

The universal prose battery refuses dashes, curly quotes, out-of-font glyphs, throat-clearing, bad headings, and long paragraphs.

- enforced by `style_audit:main`
- proven by `src/press/data/known-bad/em-dash.md`
- proven by `src/press/data/known-bad/en-dash.md`
- proven by `src/press/data/known-bad/curly-quotes.md`
- proven by `src/press/data/known-bad/emoji.md`
- proven by `src/press/data/known-bad/title-case.md`
- proven by `src/press/data/known-bad/numbered-heading.md`
- proven by `src/press/data/known-bad/long-paragraph.md`
- proven by `src/press/data/known-bad/trailing-whitespace.md`
- proven by `src/press/data/known-bad/in-conclusion.md`
- proven by `src/press/data/known-bad/throat-clearing-important.md`
- proven by `src/press/data/known-bad/throat-clearing-worth.md`
- proven by `src/press/data/known-bad/at-its-core.md`
- proven by `src/press/data/known-bad/real-question.md`
- proven by `src/press/data/known-bad/lets-dive.md`
- proven by `src/press/data/known-bad/without-further-ado.md`
- proven by `src/press/data/known-bad/testament.md`
- proven by `src/press/data/known-bad/vibrant-tapestry.md`
- proven by `src/press/data/known-bad/negative-parallelism.md`
- does not cover: The glyph law flags legitimate Greek or math; short title-case headings slip.

## INV-editorial-checkers **(critical)**

Every known-bad fixture trips its declared rule; known-good passes clean.

- enforced by `check_the_checkers:main`
- proven by `src/press/data/known-bad/em-dash.md`
- proven by `tests/test_sabotage.py::test_sabotage_removed_graph_edge_reddens_state_model`
- does not cover: A book fixture with no expect comment falls back to any-rejection.

## INV-editorial-jargon

Watchlist terms at rewrite severity fail the run.

- enforced by `jargon_lint:main`
- proven by `src/press/data/known-bad/jargon.md`
- does not cover: Exact matches only; a per-book allow list can silence any term.

## INV-editorial-jargon-parity

The package jargon checker and the portable skill copy return equivalent findings and refusals for the same text and watchlist, and default to the same watchlist.

- enforced by `selftest_book:check_jargon_parity`
- proven by `tests/test_jargon_parity.py::test_shared_logic_is_byte_identical`
- does not cover: A shared-source and fixture/property contract, not a single shared engine; the watchlist data is shared by construction.

## INV-events-protocol-failure

A malformed or unknown-version event line surfaces a ProtocolError with the raw output preserved.

- enforced by `events:parse_line`
- proven by `tests/test_events.py::test_unknown_version_is_a_protocol_failure`

## INV-extension-conformance **(critical)**

An extension declaration is refused before execution when it collides with a core name, targets an extension-contract major this press does not implement, is structurally malformed, or names an unknown dependency. Discovery is declarative and deterministic; nothing runs on the strength of import order or an ambient entry point.

- enforced by `extensions:conformance`
- proven by `src/press/data/extensions/hostile/collision.yaml`
- does not cover: Conformance decides on the declared manifest -- the names, contract major, dependencies, invariants, and capabilities an extension states; it does not sandbox arbitrary code, because the contract admits no code extension, only declarative registry entries.

## INV-extension-seal **(critical)**

An extension may depend on the mandatory verification, path containment, artifact graph, config validation, and release gate, but it may never declare that it provides or replaces one, and it may not carry an invariant it does not prove. A manifest that claims a sealed capability or an unproven obligation is refused.

- enforced by `extensions:conformance`
- proven by `src/press/data/extensions/hostile/collision.yaml`
- does not cover: The seal is a fixed set of capability tokens and the rule that every declared invariant names a proof; it governs what a manifest may claim, not the runtime behavior of a code extension, which the contract does not admit.

## INV-fakes-routing

The process fake answers by command name first, then from its queue, and records every invocation.

- enforced by `adapters.fakes:FakeProcessRunner.run`
- proven by `tests/test_adapters.py::test_fake_runner_answers_by_command_and_from_queue`

## INV-figures-refuse-illegal

Figure validation refuses left/right placement with absolute width and a bad outset.

- enforced by `figures:validate`
- proven by `tests/test_figures.py::test_validate_refuses_left_right_absolute_and_bad_outset`

## INV-format-agreement

Every chapter's content appears in every built edition; an edition that silently drops a chapter (or most of it) disagrees with the editions that kept it and is refused, not passed.

- enforced by `verify_formats:verify_editions_agree`
- proven by `tests/test_verify_editions.py::test_an_edition_that_drops_a_chapter_is_named_and_refused`
- does not cover: Presence of a distinctive multi-word fragment per chapter, not a full diff: an edition that keeps each chapter's witness fragment but scrambles or truncates the surrounding prose is not caught. The PDF joins the agreement set only where pdftotext is present (the toolchain tier); the other editions are checked with no external tool.

## INV-format-site-identity

Each chapter's witness appears exactly once across the reader site.

- enforced by `verify_formats:verify_site`
- proven by `tests/test_selftest_checks.py::test_invariant_check_passes[check_site_identity]`
- does not cover: A chapter with no qualifying line contributes no witness.

## INV-format-structure

A valid v1 book's non-PDF editions keep their committed structural shape: the EPUB's chapter-document count exactly, its spine and nav and the reader site's pages and links no smaller than the reviewed baseline, and the DOCX still declaring every house style.

- enforced by `build:build_target`
- proven by `tests/test_sabotage.py::test_sabotage_removed_graph_edge_reddens_state_model`
- does not cover: requires capability: pandoc
- does not cover: Toolchain-gated: the rendered comparison runs only where pandoc is present, and the reviewed baseline is regenerated deliberately, never silently. Book-determined counts are matched exactly; version-sensitive shapes are matched in the regression direction only, so a benign pandoc upgrade that adds a spine item or a token style is not caught, by design.

## INV-format-witness **(critical)**

Title and a derived manuscript witness appear in every format; a book yielding no witness is refused, not passed.

- enforced by `verify_formats:require_witnesses`
- proven by `tests/test_selftest_checks.py::test_invariant_check_passes[check_format_witnesses]`
- does not cover: One longest line per document; a format dropping every other line is not caught here -- INV-format-agreement holds the full per-chapter witness set against every edition to close that gap.

## INV-front-matter-golden

Generated front-matter TeX matches its golden byte-for-byte.

- enforced by `gen_front_matter:generate`
- proven by `tests/test_gen_front_matter_golden.py::test_generated_front_matter_matches_the_golden`

## INV-gen-index-hits-and-zero-hit

Each curated index term resolves to the chapters it appears in, and a zero-hit term fails the build.

- enforced by `gen_index:generate`
- proven by `tests/test_config_shapes.py::test_gen_index_resolves_hits_to_chapters_and_fails_on_a_zero_hit`

## INV-graph-acyclic

The artifact graph is acyclic, outputs unique, every published artifact a concrete filename.

- enforced by `registry:build_order`
- proven by `tests/test_sabotage.py::test_sabotage_removed_graph_edge_reddens_state_model`
- does not cover: Proves graph shape, not that each builder produces its declared output.

## INV-graph-escaping

Metadata interpolated into HTML and TeX is escaped.

- enforced by `build:cover_fragment_html`
- proven by `src/press/selftest.py::check_honest_refusals`
- does not cover: The HTML cover fragment and the front-matter TeX escaper (gen_front_matter.escape) are proven; other sibling sites share the pattern unproven.

## INV-graph-no-stale **(critical)**

Verify targets rebuild before verifying; a stale artifact cannot be blessed.

- enforced by `__main__:main`
- proven by `tests/test_sabotage.py::test_sabotage_removed_graph_edge_reddens_state_model`
- does not cover: CLI-path only; importing a verifier module directly skips the rebuild.

## INV-http-transport-signals

The urllib transport translates a timeout to TransportTimeout and other network failures to TransportError, and bounds the read.

- enforced by `adapters.http:urlopen_transport`
- proven by `tests/test_provider_http_transport.py::test_network_failures_are_translated_to_typed_transport_signals`

## INV-idlookup-fails-closed

An LCCN record for a different number is a mismatch, and lookups fail closed on entities, size, and media.

- enforced by `idlookup:lookup_lccn`
- proven by `tests/test_idlookup.py::test_lccn_record_for_a_different_number_is_a_mismatch`

## INV-illustrate-subject

An illustration's subject is the figure's art description, never its caption (#225).

- enforced by `illustrate:subject_from_figure`
- proven by `tests/test_illustrate.py::test_subject_is_the_figures_art_description_not_its_caption`

## INV-lulu-timeout-unknown

A submit timeout is an UnknownOutcome that forces a lookup, never a retry or an assumed success.

- enforced by `providers.lulu:LuluProvider.submit`
- proven by `tests/test_provider_conformance.py::test_lulu_submit_timeout_is_an_unknown_outcome`

## INV-migration-preview

A migration dry run reports every change it would make and every design consequence to weigh, and writes nothing; a book learns exactly what moving majors does before a byte changes.

- enforced by `migrate:plan`
- proven by `tests/test_migrate.py::test_apply_then_rollback_is_exact`
- does not cover: The preview enumerates the pin changes and the house-profile design verdict; a book that has already selected a non-house profile carries that design choice independently of the migration.

## INV-migration-safe **(critical)**

Migrating a book between press majors moves only the pin, in requirements.txt and the CI workflow; the manuscript, config, and accepted art come out byte-for-byte identical, and rollback restores the exact pre-migration pin from a backup written before any file is changed.

- enforced by `migrate:apply`
- proven by `tests/test_migrate.py::test_apply_then_rollback_is_exact`
- does not cover: Proven on a scaffolded book (the two pin sites the template writes); a book that pins the press somewhere exotic is diagnosed and refused rather than rewritten, not migrated.

## INV-money-exact-cents

Money parses decimal strings as exact cents, never through binary float.

- enforced by `providers.contract:Money.parse`
- proven by `tests/test_provider_conformance.py::test_money_parses_decimals_without_float_error`

## INV-mutation-deterministic

The mutation engine enumerates every mutable operator in a pure module exactly once and applies exactly one edit per mutant.

- enforced by `mutation:survivors`
- proven by `tests/test_mutation.py::test_apply_mutates_exactly_one_site_and_leaves_the_rest`

## INV-operator-counsel-touches-nothing

A counsel-mode run (no --apply) leaves the manuscript and config byte-identical, aborting if anything changed.

- enforced by `operator:improve`
- proven by `tests/test_operator_counsel.py::test_improve_counsel_aborts_when_workflow_touches_manuscript`

## INV-pages-refs

Every local reference and stylesheet url resolves; fragments resolve to real anchors.

- enforced by `verify_pages:check_refs`
- proven by `src/press/selftest.py::check_pages_verifier`
- does not cover: External links are skipped; a dead external URL is never caught.

## INV-pdf-detector **(critical)**

The blank-page detector is proven against fixtures before it judges.

- enforced by `verify_pdf:self_test_detector`
- proven by `src/press/selftest.py::check_coverwrap_detectors`
- does not cover: Two synthetic extremes; a faint hairline can still read as blank.

## INV-pdf-ink

Every rendered page carries ink and keeps it off the edge.

- enforced by `verify_pdf:verify_page_ink`
- proven by `tests/test_sabotage.py::test_sabotage_removed_graph_edge_reddens_state_model`
- does not cover: Tolerates one structural blank verso in the print profile.

## INV-plate-alpha-preserved

Enhancing a plate master preserves its alpha (ink on transparency); it is never baked onto white.

- enforced by `art_enhance:enhance`
- proven by `tests/test_art_enhance.py::test_enhance_preserves_a_plate_masters_alpha`

## INV-print-safe-flatten

Print sanitization flattens transparency onto white, caps resolution without upscaling, and preserves grayscale.

- enforced by `print_safe:sanitize`
- proven by `tests/test_print_safe.py::test_sanitize_flattens_transparency_onto_white`

## INV-process-cancel-not-success

A process that exits zero after cancellation is still not a success.

- enforced by `process_control:ProcessController.finish`
- proven by `tests/test_process_control.py::test_cancel_race_a_zero_exit_after_cancel_is_still_not_success`

## INV-profile-geometry

Selecting a design profile renders the interior at that profile's declared trim, and an unknown profile is refused before any rendering. A profile's design-affecting data has a stable digest, so a sealed value cannot change without the key that scopes its visual baseline moving too.

- enforced by `profiles:geometry_tex`
- proven by `tests/test_sabotage.py::test_sabotage_removed_graph_edge_reddens_state_model`
- does not cover: requires capability: pandoc
- does not cover: The rendered-trim proof runs where the toolchain is present (the integration tier); locally, the projection-string and digest proofs stand in. Typography and web tokens are projected and proven at the fragment level; their rendered baselines are generated in the pinned toolchain.

## INV-profile-seal-refuses-drift

The print-profile seal gate refuses a drifted, unsealed, or missing profile.

- enforced by `profile_lifecycle:validate`
- proven by `tests/test_profile_lifecycle.py::test_digest_drift_is_refused`

## INV-provider-contract **(critical)**

Every print-provider adapter maps its own vocabulary to the neutral contract: money is integer minor units parsed without binary float, an unrecognized status quarantines to UNKNOWN, a submission timeout is an unknown outcome that forces a lookup before any resubmission (never a hidden retry or a fabricated acceptance), an unsupported capability is a typed refusal rather than a simulation, and a webhook is authentic only when its signature matches the raw body.

- enforced by `selftest_release:check_provider_contract`
- proven by `tests/test_provider_conformance.py::test_an_unsupported_capability_is_declared_not_simulated`
- does not cover: The contract and the conformance suite are proven against the smart fake and the Lulu adapter under a canned transport; the live Lulu sandbox exchange awaits credentials (the deferred end-to-end proof).

## INV-provider-legality

The provider legality gate refuses an uncut trim, illegal binding, out-of-range page count, or unsupported color.

- enforced by `provider_specs:ProviderSpec.check_selection`
- proven by `tests/test_provider_specs.py::test_legality_refuses_an_uncut_trim`

## INV-provider-qualification

The provider record declares every capability explicitly (an omitted capability is a forbidden implicit claim) and the full physical checklist; a provider is qualified for an edition only by a physical inspection with every checklist point passed, scoped to that edition's identity, so a marketing claim, a failed point, a not-fit provider, and an inspection of a different edition are all refused.

- enforced by `qualification:qualify`
- proven by `tests/test_qualification.py::test_a_failed_point_cannot_qualify`
- does not cover: Validates the record's shape and the physical-gate logic; it cannot confirm a claimed inspection actually happened, only that a qualification carries a passed, edition-scoped inspection digest.

## INV-publish-rebuild-before-bless

Retail verification rebuilds each artifact through the registry before verifying, so a stale or corrupt file is never blessed, and a failing verifier yields a nonzero exit.

- enforced by `publish:verify_retail`
- proven by `tests/test_publish_rebuild.py::test_verify_retail_rebuilds_before_bless_and_main_fails_on_a_bad_verifier`

## INV-reader-no-phantom-canonical

Without a configured site-url, the reader landing claims no canonical URL or image (#158).

- enforced by `reader_meta:landing_head_metadata`
- proven by `tests/test_landing_metadata.py::test_without_a_site_url_no_canonical_or_url_is_claimed`

## INV-registrations-malformed-fails

A malformed ISBN/registration block surfaces as a check failure.

- enforced by `registrations:failures`
- proven by `tests/test_registrations_isbn.py::test_a_malformed_block_is_a_check_failure`

## INV-release-contract

A three-part tag pins its own action ref and an existing immutable toolchain image, proven before the major floats.

- enforced by `selftest_release:check_release_grammar`
- proven by `tests/test_sabotage.py::test_sabotage_removed_graph_edge_reddens_state_model`
- does not cover: The pin grep is an exact string; it does not prove the tag's tree.

## INV-release-receipt-chain **(critical)**

A release chain refuses a missing, tampered, reordered, or input-mismatched prerequisite, a dirty-tree receipt, a terminal receipt whose package or toolchain does not match the built and pinned objects, an incomplete chain that skips any trust layer or breaks a layer's extension of its predecessor, and, when assembled from per-job receipts, a missing CI tier (a job that did not run leaves no receipt) or receipts that disagree on the source commit.

- enforced by `receipts:verify_release`
- proven by `tests/test_receipts.py::test_release_refuses_dirty_tree_receipt`
- does not cover: The per-job assembly makes the chain reflect the CI jobs that actually ran and uploaded a receipt; it trusts that an uploaded tier receipt attests real work, and the cross-workflow artifact download is proven only by a live release, not the fast suite.

## INV-release-tag-grammar **(critical)**

A release tag is strict SemVer and the composite action refuses shell syntax in its command input.

- enforced by `selftest_release:check_release_grammar`
- proven by `scripts/release.sh`
- does not cover: The action grammar is proven by unit test, not by a live workflow run.

## INV-scaffold-neutral

No original-book identity leaks into a clean scaffold.

- enforced by `selftest_book:check_scaffold_neutrality`
- proven by `src/press/data/template/config/metadata.yaml`
- does not cover: Pattern-based; a novel identifying string is not caught.

## INV-scaffold-no-leak

A scaffolded book carries no identity from the press or any prior book.

- enforced by `scaffold:main`
- proven by `tests/test_scaffold_book.py::test_scaffold_carries_no_original_identity`

## INV-scenarios-cover-pairs

The pairwise generator's selection covers every pair of parameter values.

- enforced by `scenarios:pairwise`
- proven by `tests/test_scenarios.py::test_pairwise_covers_every_pair`

## INV-selftest-orchestrates-all

Every registered check is orchestrated by the one ordered CHECKS list the CLI and pytest both run.

- enforced by `selftest:main`
- proven by `tests/test_selftest_checks.py::test_every_check_is_orchestrated`

## INV-subprocess-git-isolation

The subprocess runner strips ambient GIT_* repo-binding vars for git commands so a nested repo observes only itself.

- enforced by `adapters.production:SubprocessRunner.run`
- proven by `tests/test_git_isolation.py::test_ambient_git_index_does_not_hide_a_nested_repos_files`

## INV-transport-empty-body-and-signals

An empty response body parses as an empty mapping, and the transport's timeout and error signals stay distinct types.

- enforced by `providers.transport:Response.json`
- proven by `tests/test_provider_http_transport.py::test_response_json_guards_empty_body_parses_and_types_are_distinct`

## INV-webhook-authenticity

A valid webhook event is authentic and a tampered body is not.

- enforced by `providers.fake:FakeProvider.parse_event`
- proven by `tests/test_provider_conformance.py::test_a_valid_event_is_authentic_a_tampered_one_is_not`

## INV-wizard-preview-only

The setup wizard writes only a clean preview; an invalid edit is previewed but never written.

- enforced by `desk.wizard:ReviewScreen.action_apply`
- proven by `tests/test_desk_wizard.py::test_an_invalid_edit_is_previewed_but_never_written`
- does not cover: Proven only where the tui extra (textual) is installed.
