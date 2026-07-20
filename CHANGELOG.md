# Changelog

The press records its own releases here from v1.7.0 onward; earlier
history lives in the tags and their messages (v1.0.0 through v1.6.0,
2026-07-18: the packaged instruments, the art department, generated
front matter, the print pack, registrations, the operator, the
aesthetic system, and the public-readiness hardening of the P0/P1
audit).

## [Unreleased]

Nothing yet.

## [1.17.0] - 2026-07-20

A public-experience and maintenance pass: accessibility landmarks and
declared metadata on every docs page, community scaffolding and governance,
one contributor verify command, every Action off the deprecated Node 20
runtime, and the code deprecation warnings cleared.

### Added

- Public-project scaffolding: structured GitHub issue forms (defect,
  proposal, documentation) that ask for the diagnostics a report needs and
  route security privately, a pull-request template tied to the project's
  actual contracts (#163); a Contributor Covenant Code of Conduct and an
  honest single-maintainer `GOVERNANCE.md` covering decision/release/security
  authority and bus-factor (#164); and `scripts/verify.sh`, one fast-to-
  complete command that runs the local half of CI's quality gate
  (lint/type/selftest/pytest, then the coverage and mutation ratchets and
  the site build), documented in CONTRIBUTING (#162). The repository's
  discovery metadata (homepage, topics) and auxiliary-surface flags are set
  (#165).
- The documentation site declares its metadata instead of leaving search
  engines and link previews to infer it: every page carries a canonical URL,
  a meta description derived from its own first paragraph, and Open
  Graph/Twitter-card tags, and the build emits a deterministic `sitemap.xml`
  and `robots.txt`. The build fails if a page lacks a canonical URL or
  description (part of #158; book-page structured data is separate).
- Every documentation-site page declares its language (`<html lang="en">`),
  exposes one `main` landmark, and leads with a skip-to-content link as the
  first focusable element; the build fails if a page lacks any of them
  (#157). The CSS-only mobile menu shows a focus ring on its toggle so it is
  operable and visible by keyboard (#156). (Internal doc links already stay
  on the site rather than bouncing to GitHub, #159.)

### Changed

- Every pinned GitHub Action moved off the deprecated Node 20 runtime to its
  current Node 24 release (checkout, setup-python, upload/download-artifact,
  deploy-pages, upload-pages-artifact), each pinned by full commit SHA with
  the reviewed version in a comment; the artifact inputs we use are
  unchanged across the bump. A posture test fails if any action is ever
  left unpinned by SHA (#179).

### Fixed

- Deprecation cleanup. `verify_coverwrap` reads pixels with `Image.tobytes()`
  instead of the deprecated `Image.getdata()` (removed in Pillow 14), with a
  press-scoped warning-to-error filter so it cannot creep back (#167); the
  async fixture loop scope is pinned to `function` explicitly, matching the
  suite's isolation law and ending the pytest-asyncio default-drift warning,
  proven by a loop-identity and task-leak test (#169). The site's Pandoc
  `--no-highlight` deprecation is already gone: the redesign turned
  highlighting on and colors the tokens in CSS, so no deprecated flag is
  passed (#170).

## [1.16.4] - 2026-07-20

Seller-of-record print ordering plus a public-experience pass: a validated
configuration CLI and desk wizard, conventional CLI discovery, one YAML
library and version, an independently consumable public toolchain image, an
executable beginner quickstart, and a redesigned documentation site.
(Earlier 1.16.0-1.16.3 tags did not release: the release contract, which
only floats the major and publishes after every trust gate proves, surfaced
CI-only issues fixed here before any Release existed.)

### Fixed

- The invariant ledger resolves from the working directory when the
  packaged `__file__`-relative path is absent, so the desk end-to-end proof
  (which runs the suite against an installed wheel) can load it instead of
  breaking collection.
- The per-module coverage baselines are restored to the values CI measures.
  A local `--update` had re-measured them on a machine where the ratchet's
  integration-deselection and toolchain-hiding did not take effect the same
  way, inflating many baselines above the deterministic floor CI enforces.
- The quality job's `build.log` is ignored, so it no longer dirties the
  working tree before that tier emits its trust receipt; a release requires
  clean-tree receipts, and an untracked log was failing the chain.

### Added

- A guided setup wizard in the operator desk (`w`), a keyboard-driven flow
  for a book's identity that projects the typed configuration boundary
  (#155) onto the desk rather than being a second YAML editor. It reads and
  writes only through `config_cli`/`config_store`, shows an edit as an exact
  deterministic diff with the real validator's verdict before writing, and
  applies only a clean preview; cancel, back, or a validation failure
  leaves the file byte-for-byte unchanged. A secret-looking value is
  refused before it can reach a book's config, and a completed wizard hands
  back a runnable next step rather than a readiness claim. A bare install
  stays Textual-free; the `tui` extra proves the flow with headless
  active-signal tests (first run, edit-and-apply, invalid value, cancel,
  secret refusal) (#166).
- Conventional CLI discovery (#175). `press --help`/`-h` prints every
  command grouped with its summary; `press <command> --help` explains one
  command; `press --version` reports the installed version. All exit 0 and
  never execute a handler, build, mutate, or need a book, a TTY, or the
  toolchain, so `press doctor --help` no longer runs the diagnostic and
  `press desk --help` no longer tries to launch the TUI. An unknown command
  exits 2 with the nearest valid suggestion and a pointer to `press --help`.
  Help is rendered from the one command catalog, so it cannot describe a
  command the CLI does not dispatch or omit one it does.

- `press config get|set|unset|list|validate`: a validated command surface
  over every book-configuration field, so ordinary configuration no longer
  depends on hand-editing YAML. A write is checked by the same typed model
  that validates a build (`bookmodel`, `commerce`, `registrations`, the
  house-rules regex compiler) against the proposed document *before* a byte
  is touched, so a rejected edit changes nothing; the edit is applied to a
  comment-preserving round-trip and written atomically. A value the
  build's YAML 1.1 loader would misread (a bare `no`/`yes`/`on`/`2026`) is
  written quoted, so the writer and the build agree on the document. Types
  are never guessed from a shell string (a list or mapping must arrive as
  `--json`);
  a value that looks like a secret is refused and never echoed; and every
  field is either writable or carries an explicit classification (the v1
  trim is immutable, the authorities and index lists are structured). A
  drift test walks the configuration reference and fails if a documented
  field has neither classification, and the quickstart's `press config`
  commands are executed against the installed package. Direct YAML editing
  remains documented for experts (#155).

- A task-first beginner quickstart (`docs/QUICKSTART.md`): one copyable
  path from a blank machine to a built, verified book, naming which steps
  are the publisher's decisions and which are mechanical defaults, with a
  table of the common first-run refusals and their fixes. It is the
  canonical first-run path README, install, configuration, and support
  now point to, and it is executable documentation: a doc-test extracts
  the guide's own commands, proves the anchor commands are present and
  ordered, and runs the toolchain-free spine (`press new` -> `press
  check`) against the installed package so the guide cannot drift out
  from under a beginner (#152).
- When print ordering is enabled, a policy link the publisher does not
  host is now generated as an honest page on the book site rather than
  refused. Each generated support, privacy, or returns page discloses the
  seller of record and what they handle, and appends the publisher's own
  words from an optional `policies` block; `press verify` fails closed if
  a generated page is missing or omits the seller disclosure (#151).

### Changed

- The documentation site is redesigned: a cool-graphite, one-cinnabar-ink
  system (Literata, Hanken Grotesk, JetBrains Mono, self-hosted), a
  left-sidebar nav, theme-aware syntax highlighting, a copy button on code
  blocks, and a first-time-author landing. Internal links stay on the site,
  and a "made with press" section links real books.
- The toolchain image is public, so press is independently consumable
  (#161). A book repository under any account or org now builds the
  advertised CI path with no owner-granted package permission and no
  configured secret: the pull is authenticated with the workflow's own
  `GITHUB_TOKEN`, which works for a public image on fork and Dependabot
  pull requests too. The build still pins the exact toolchain image and the
  release contract still proves the pin is immutable, so every build runs
  against the toolchain bytes the release was proven on. Installation,
  compatibility, README, and the quickstart drop the per-repo grant step;
  a posture test guards that they cannot silently ask for one again. The
  owner's private-image workflow is retired, not merely hidden.

- One YAML library, one version. Press read config with PyYAML (YAML 1.1,
  where a bare `no`/`yes`/`on`/`off` is a boolean) while the `press config`
  writer used ruamel (YAML 1.2, where they are strings); the two disagreed
  about the document itself. The package now reads and writes all YAML
  through `press.yamlio` (ruamel at YAML 1.2, pure parser), so a bare `no`
  is the string "no" everywhere and the writer and reader can never drift
  apart. A boundary test forbids a raw `import yaml` outside the one door,
  and PyYAML is dropped as a dependency. No book's valid config changes
  meaning under 1.2 except a value a book explicitly wrote as a bare
  `yes`/`no`/`on`/`off` and relied on being a boolean; write it as
  `true`/`false` instead.

## [1.15.2] - 2026-07-19

Completes the accumulated-delivery-trust work deferred from v1.14: the
release chain now proves every layer, and two new ratchets guard the
tests that do the proving.

### Added

- The release trust chain is complete, not a placeholder. A release used
  to be witnessed by a two-layer chain in which one "collection" receipt
  stood in for every CI proof, and the verifier checked ordering and
  linkage but not completeness — so the stand-in passed and the release
  proved nothing about the layers between. Verification now requires the
  chain to be complete: every trust layer present, contiguous, and each
  extending its immediate predecessor. The release contract builds the
  full per-layer chain only after asserting that every trust-layer check
  (the whole test suite, the container gauntlet, the operator surface) is
  green on the tagged commit, so each layer's receipt is backed by a
  proof that actually ran. Closes the per-layer prerequisite chain (#97)
  and the layered-CI trust ordering (#94).
- A per-module branch-coverage floor gate. Repository-wide coverage can
  stay green while one module's branches rot; the ratchet holds each
  module to the minimum coverage it shows when the rendering toolchain is
  absent. It hides that toolchain internally before measuring, so the
  gate is deterministic whether or not the machine has pandoc or
  LuaLaTeX, and because ambient coverage is always at or above the floor,
  no toolchain posture can push a module below baseline — the gate goes
  red only on a real regression (#96).
- A deterministic mutation-score ratchet over the pure-computation
  modules. It mutates the EAN-13 checksum and bar encoding and the
  artifact-state derivation one edit at a time and runs each module's
  example-based tests against the mutant; a surviving mutant is a
  missing proof. Each mutant runs once with no retry, against a shadow
  source tree with bytecode caching forbidden so no mutant is ever
  measured against another's compiled code (#95).
- The change-impact mapper: on a pull request, changed policy code that
  maps to no classified surface or no invariant fails the build, so a new
  verifier or parser cannot land ungated (#96).

### Changed

- The operator desk is a usable tool: a run can be cancelled and reports
  the child's exact verdict; the target picker prompts for a command's
  arguments before launching and grays out a command a missing toolchain
  would only let fail (#147, #148, #149).

## [1.15.1] - 2026-07-19

### Added

- The release boundary verifies accumulated provenance, not just a
  green workflow name. A release receipt names the source commit, the
  built wheel digest, the pinned toolchain image, and the quality
  manifest digests; the release contract builds the wheel on the clean
  tagged checkout, assembles the receipt, and refuses a chain that is
  not clean-tree or whose package or toolchain does not match the
  objects actually built and pinned, so a deliberate commit, wheel, or
  image substitution turns the release gate red. Because the contract
  must be green before the floating major moves, the identity gate is
  enforced before the tag floats. Part of the accumulated-delivery-trust
  work (#97); the full per-layer receipt chain follows with the
  layered-CI change.

## [1.15.0] - 2026-07-19

### Added

- The operator desk: `press desk`, an optional Textual interface over
  the command line. It is genuinely optional, behind a `tui` extra: a
  bare install builds books untouched and the entry refuses cleanly
  with the install hint when the extra or a terminal is absent.
- Its foundations are pure Python, provable without the UI. One typed
  command catalog is the single source the CLI usage text and the desk
  surface both read, so they cannot drift (#100). doctor.examine
  returns the machine's capabilities as typed findings and main()
  renders them byte-identically (#103). Artifact status is projected
  from content digests and recorded verification, never mtimes: a
  touched-but-unchanged file is not stale and a rebuild to identical
  bytes is not new (#101). A versioned structured event protocol lets
  a child emit stage and diagnostic events without a consumer scraping
  text, and a malformed event is a surfaced failure that never hides
  raw output (#102). A single-child process controller streams a
  child's output and reports its exact exit code as the verdict, with
  cancellation and the single-child invariant proven against a fake
  process (#105). The DESK read model assembles the desk's facts from
  those registries and reads only (#106).
- The desk itself: the DESK dashboard renders the read model with the
  digest-based evidence vocabulary and grays out actions a missing
  toolchain blocks (#112); a RUN view streams a press child and shows
  its exact verdict (#109); a picker generated from the catalog offers
  exactly the CLI's targets (#111); the app shell carries a house
  theme (#104, #107). A headless Pilot harness drives the real app
  against a scaffolded book (#108), and a bare-and-tui wheel matrix
  plus an installed end-to-end proof gate the milestone
  (#110, #114). docs/DESK.md documents it (#113).

## [1.14.0] - 2026-07-19

This release ships the completed, self-contained portion of the
accumulated-delivery-trust milestone. The receipt library is the
foundation; the remaining CI-workflow integration (layered CI, the
release receipt gate, coverage impact selection, mutation-score
ratchets) and the live second-party proofs are tracked for a
follow-up point release.

### Fixed

- The distributions are clean and reproducible: the broad data glob
  used to ship __pycache__ and bytecode from running the packaged
  scripts, so the wheel's contents depended on prior execution and the
  interpreter version. exclude-package-data and a pruning MANIFEST.in
  drop bytecode from both wheel and sdist; a build emits no warnings,
  passes twine --strict, and CI installs the wheel into a fresh
  environment to run its selftest. That fresh-install run surfaced two
  real defects, now fixed: the pytest collection plugin (pure test
  infrastructure) was shipping in the runtime package, and several
  selftest checks read repo files a wheel does not carry; the plugin
  moved to tests/ and the repo-only checks skip cleanly from an
  install (#73).

### Added

- Chained trust receipts: a receipt records the source commit and
  tree-clean state, the digests of the source, toolchain, and quality
  manifests a layer consumed, the proofs it executed, and the digests
  of the prerequisite receipts it extends. Receipts are deterministic
  and independently verifiable (`python3 -m press.receipts verify`),
  and verify_chain refuses a missing or tampered prerequisite, layers
  out of accumulated-trust order, a changed input, and a dirty-tree
  receipt in a release chain, each with a negative test (#93).
- A consolidated sabotage suite proves each trust gate reddens when
  its protection is removed (unclassified callable, dangling proof
  reference, orphan fixture, removed graph edge, dirty release
  receipt, wrong fake command), indexed so a gate cannot lose its
  sabotage case unnoticed (part of #95).
- The CI privilege posture the second-party proofs would exercise is
  proven mechanically: no pull_request_target and every workflow
  least-privilege, so a regression is caught without a second account
  (part of #87, whose live runs are documented for a second party).

## [1.13.0] - 2026-07-19

### Added

- Adversarial artifact proof: the verifiers are now proven to fail, not
  just to pass. A library of named single-purpose damage operators
  (archive member add, remove, escaping-path, uncompressed-store,
  byte-flip; reader-site chapter duplication, dead stylesheet url, dead
  fragment) each records source and result digests and asserts the
  invariant-specific diagnostic, with a coverage gate so no
  deliberate-damage invariant loses its negative proof (#88). The
  artifact graph is modeled as deterministic build-mutate-verify state
  transitions over the git-only source archive, proving a mutated or
  missing output cannot be blessed, rebuild restores validity, and
  clean removes every declared output, in both cwd and BOOK_ROOT modes
  (#89).
- Mechanical configuration coverage: quality/scenarios.yaml declares
  ten optional-configuration dimensions, press.scenarios generates a
  deterministic eleven-combination pairwise covering set plus five
  named high-risk interactions, and gates fail on an untested surface
  or an unrealizable high-risk scenario (#90).
- Real-tool integration runners for every artifact family (PDF/print,
  EPUB, HTML and site and Pages, Markdown and text and DOCX, archives
  and the sources companion, cover wrap) build source-only factory
  books through the actual toolchain and inspect them with their real
  verifiers, capability-gated so a missing tool skips cleanly, each
  recording tool versions and input and output digests (#91).
- Design-major visual regression: a fixture book's built PDF is
  measured for toolchain-stable geometry (page count, embedded fonts,
  trim, per-page ink bounds) against a committed v1 baseline, so a
  margin shift, font swap, or displaced plate is a drift while an
  encoder patch is not; baselines update only with a recorded reason
  (#92).
- docs/COMPATIBILITY.md states the supported Python range (3.10 to
  3.13, tested), the pinned Ubuntu 24.04 toolchain image as the
  contract, and the OS families, and press doctor warns outside the
  tested Python range (#35).

## [1.12.0] - 2026-07-19

### Added

- Trust foundations: a test-quality architecture the press proves
  itself against. A pytest harness runs the selftest's invariant
  checks as individual cases from one ordered CHECKS list both runners
  consume (#78). An executable invariant ledger, quality/invariants.yaml,
  is the single source of what the press promises: its validator proves
  every enforcer and proof it names resolves to a real function or
  fixture, it generates docs/INVARIANTS.md, and the narrative matrix in
  ARCHITECTURE.md now points at it rather than duplicating it (#79). The
  public surface is classified in quality/surfaces.yaml with a
  mechanical AST inventory that fails on an unclassified new callable
  (#81). Every regression fixture has a provenance entry reconciled
  against its inline expect comment (#84). Twenty-two hypothesis
  properties cover the pure policy, parsing, graph, and normalization
  code (#85). A deterministic fuzz corpus proves the hostile parsers
  refuse locatably instead of crashing (#86). A typed BookFactory with
  named presets builds isolated source-only books whose facts are
  inspectable and whose scenarios cannot contaminate one another (#83).
- Typed boundary adapters: subprocess, environment, credential, and
  image-HTTP calls move behind protocols with production and recording
  fake pairs; build, doctor, operator, art_commission, and
  package_source drive them through injected singletons with behavior
  preserved, domain results and exceptions give the layer a vocabulary,
  retry is deterministic, and a boundary lint keeps raw calls out of
  every module but the adapters, its legacy allowlist able only to
  shrink (#82).
- A pytest collection plugin enforces the invariant, layer, and proof
  markers where present, rejects an assertionless marked test, requires
  an xfail to cite a declared limitation and a skip to name a toolchain
  capability, and writes a test-to-invariant index before execution
  (#80).

### Fixed

- docx_visible_text returned the empty string on unparseable bytes
  instead of raising an XML traceback, so a corrupt DOCX now surfaces
  as its caller's locatable witness failure (found by the new fuzz
  corpus).

## [1.11.0] - 2026-07-19

### Changed

- Workflow coherence (the v1.11 milestone). The packaged workflows
  stop assuming the first book: authorities research derives its
  subject and preferred source kinds from the book's own metadata and
  manuscript, extraction is exhaustive by default with any sampling
  cap disclosed in the accounting (#76); editorial synthesizer
  rejections become durable reviewed findings in
  build/editorial-rejections.md, fed into later rounds so a refuted
  suggestion is not re-filed unchanged, with staleness resolved
  against the current text (#77); and the book-aesthetics schema
  documents the full page-look surface (web palettes, typography,
  book colors) with a selftest tying the documentation to the keys
  the aesthetic engine actually consumes (#59).
- The complexity inventory is empty: the route-table refactor of the
  CLI dispatch and decompositions of the remaining oversized
  functions bring every function under the C901 ceiling and remove
  every noqa; the docs drift checker now derives routed targets from
  the route table itself instead of regexing source (#66).
- Contributor contracts are single-source: CLAUDE.md is canonical
  (release procedure now states scripts/release.sh; the authorities
  ledger renders a standalone companion, not an appendix) with
  AGENTS.md as a checked mirror, and the roadmap is
  registry-authoritative with generated milestone projections (#75).

### Added

- Public reference documents for #33: an invariant matrix and
  provenance-versus-verification and design-versioning sections in
  docs/ARCHITECTURE.md, a complete configuration reference in
  docs/CONFIGURATION.md, and builder/verifier/destination columns in
  the generated docs/REFERENCE.md, all carried on the documentation
  site.
- Package metadata is publishable: README as long description,
  authors and maintainers stated, and a build-plus-twine-check
  --strict gate in CI; pip-from-git at a tag remains the one
  supported channel and the docs say so (#74).

## [1.10.0] - 2026-07-19

### Changed

- Boundary integrity, first half (the v1.10 milestone's verifier and
  CI groups). Public artifacts: source publication is now an
  allowlist (git's tracked files, inside a repo) stated once in
  `publication_members()` and consumed by both the packager and the
  archive verifier, so an appended member, an untracked private
  file, or a flipped byte each fail digest-exact verification
  (#12, #23); the pages crawler follows stylesheet `url()` assets
  and fragment anchors (#10); the reader site proves per-chapter
  identity witnesses (a duplicated or missing chapter page fails by
  name) and an underivable manuscript witness is a refusal, not a
  free pass (#20). CI: pull-request toolchain smokes run with read
  permissions and no registry credentials, and main publishes the
  exact smoked image object with docker push, never a second build
  (#67, #27); the composite action passes its command input as an
  environment value matched against a target grammar, so shell
  metacharacters are data (#68); the release script validates strict
  SemVer, preflights remote state, resumes idempotently after any
  failed step, and does not float the major until the immutable
  tag's contract is green (#69, #70). Every audit-3 damage exploit
  is now a selftest fixture.
- Retail artifacts tell the truth (the milestone's second half):
  `press publish` builds and verifies the interior, wrap, and EPUB
  through the registry before checking anything off, exits non-zero
  when a required artifact fails, and separates interior and wrap
  failures under their own labels; `--report-only` says "NOT
  verified" on every line instead of pretending (#71). The cover
  wrap gains its own verifier: one page at the exact
  trim-plus-bleed-plus-spine size recomputed from the generator's
  own functions, embedded fonts, rendered ink, cover art on the
  front panel, surviving title text, and a barcode on a white card
  whose quiet zones are judged against the expected EAN symbol span,
  never against observed ink (#72). `press verify-print` verifies
  the interior first and degrades gracefully for coverless books.
  The agent workflows harden too: whole-book editorial suggestions
  normalize file paths against the scout list so a basename or
  absolute path reaches the right synthesizer and unresolvable paths
  are set aside loudly (#57), and research or audit agents that fail
  route their claims to an explicit unresolved list with reconciled
  counts, never silently out of the ledger (#58).
- Contact and imprint identity: the security contact is
  clint@lgtm.systems, the license holder is LGTM Systems, LLC, and
  books appear under the LGTM Publishing imprint.

### Added

- Every checked-in format has a linter, locally and in CI:
  shellcheck, yamllint, pymarkdown (frontmatter-aware; known-bad
  fixtures excluded on purpose), TOML/JSON validity, and
  merge-conflict/large-file guards join ruff, mypy, and the selftest
  in pre-commit; the CI quality job runs the identical battery via
  `pre-commit run --all-files`.
- docs/TUI-PLAN.md records the press desk design (Textual, screens,
  integration laws, first milestone) from the three research passes.

- Full CSS freedom for a book's web surfaces: `assets/web/reader.css`
  replaces the house reader stylesheet outright and
  `assets/web/extra.css` appends cascade-winning declarations to both
  the reader and the pages landing page. The aesthetic palette applies
  to either; a book supplying neither renders byte-identically.
- The press publishes its own documentation site
  (https://clintecker.github.io/press/): `scripts/build_site.py`
  renders every repo document through pandoc with the site's own
  design (self-hosted Source Serif, Space Grotesk, and Plex Mono;
  a two-ink letterpress palette), and the docs-site workflow deploys
  it on every push to main. Three phase guards keep site and repo in
  step: no page is hand-written; every repo Markdown file must be
  published or consciously excluded with a reason (the check caught
  SUPPORT, SECURITY, ROADMAP, and AGENTS on its first two runs);
  and every page footer stamps the commit it was built from, while
  CI builds the site pre-merge so a breakage goes red before deploy.
  The link check covers stylesheet url() references as well as page
  hrefs.

### Changed

- The press repository is public (2026-07-19), and the repository
  boundary matrix is proven with real repositories (#37):
  `press-smoke` is the standing boundary fixture, exercised as a
  private consumer (minimum permissions plus the toolchain grant),
  as a public consumer (anonymous action fetch, zero owner-specific
  setup), through a cross-boundary Pages deployment, and through a
  witness-gate refusal on a vacuous release tag. Fork-PR posture is
  proven mechanically (no pull_request_target, default read token,
  per-job least privilege); the live second-party proofs are #87.

### Fixed

- Bad input now gets a named refusal, never a traceback or an
  injection, closing the audit's failure-honesty tail: a malformed or
  empty `config/metadata.yaml` is refused with the file and line
  instead of a parser traceback (#53); the installed `press` command
  passes a failing tool's exit code through cleanly instead of
  leaking a CalledProcessError traceback (#54); a malformed
  banned-patterns regex names `config/house-rules.yaml` and the
  offending pattern (#55); a metadata title with quotes or angle
  brackets is escaped into the single-file HTML edition's cover
  fragment (#43); and index terms pass through the shared print-safe
  sanitizer so a backslash in `config/index-terms.yaml` can never
  reach the TeX engine (#44). The selftest proves every refusal.
- The release script's version bump is anchored to the `[project]`
  version line; v1.9.0's cut rewrote `[tool.mypy]`'s `python_version`
  to the release number, and mypy silently fell back to checking
  against the running interpreter instead of 3.10.

## [1.9.0] - 2026-07-19

### Added

- An engineering-quality layer with teeth: ruff lints with a
  cyclomatic-complexity ceiling of 15 (six pre-existing functions
  carry `# noqa: C901` as tracked inventory, #66), mypy runs clean
  over the whole package, and a `quality` CI job plus a
  `.pre-commit-config.yaml` run the same gates locally and on every
  PR. `pip install -e '.[dev]'` brings the tools.
- Build timing metrics: every pipeline command that takes a second or
  more prints its elapsed time, and dependency-graph builds
  (`press pages`, `press print`) print a per-stage summary, so a
  regression in the slow stages is a number, not a feeling.

### Fixed

- The doc-drift selftest now sees tuple routes
  (`target in ("pages", "verify-pages")`) as well as equality routes,
  so a routed target can no longer hide from the usage/README check
  (#41, #49).
- `gen_authorities.generate` (cyclomatic 35, the worst in the
  package) decomposed into `_structural_problems`, `_locate`, and
  `_render_companion` with behavior unchanged; PDF verification and
  art intake carry precise types where Pillow and pypdf return
  unions, and an unresolvable plate-link destination is now a named
  refusal instead of a TypeError.

## [1.8.2] - 2026-07-19

### Fixed

- The release contract's gate check requests checks:read, the scope
  the check-runs API actually demands; v1.8.1's run had pins proven
  and manifest resolving but 403'd on its final question.

## [1.8.1] - 2026-07-19

### Fixed

- The release contract awaits the tagged commit's own integration
  verdict instead of demanding prescience; v1.8.0's maiden contract
  run refused itself by racing its own gate.

## [1.8.0] - 2026-07-19

### Fixed

- The second audit's first two waves: smart-quote-proof sentinels,
  model-driven builders and bylines, headless research granted the
  web, counsel mode proving the manuscript untouched, the integration
  gate running on the pinned toolchain image, least-privilege jobs,
  sha-pinned actions, serialized toolchain publishes, tag-gating as
  machinery, and the release script the docs had only promised.

## [1.7.0] - 2026-07-19

### Added

- press doctor, the dependency examiner.
- The documentation suite: INSTALL, ARCHITECTURE, CONTRIBUTING,
  SECURITY, SUPPORT, and this changelog.

### Changed

- The 190-word paragraph rule is enforced law in book prose.
