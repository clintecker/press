# Changelog

The press records its own releases here from v1.7.0 onward; earlier
history lives in the tags and their messages (v1.0.0 through v1.6.0,
2026-07-18: the packaged instruments, the art department, generated
front matter, the print pack, registrations, the operator, the
aesthetic system, and the public-readiness hardening of the P0/P1
audit).

## [Unreleased]

Nothing yet.

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
