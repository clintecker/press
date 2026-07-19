# Changelog

The press records its own releases here from v1.7.0 onward; earlier
history lives in the tags and their messages (v1.0.0 through v1.6.0,
2026-07-18: the packaged instruments, the art department, generated
front matter, the print pack, registrations, the operator, the
aesthetic system, and the public-readiness hardening of the P0/P1
audit).

## [Unreleased]

### Fixed

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
