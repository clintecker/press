# CLAUDE.md

This repository is a small press: the build, check, and verify pipeline for
books, extracted from the production of one so the next starts with the
scars already paid for. There is no book in here. Every book-specific fact
(title, slug, sentinels, banned vocabulary, front matter, art) lives in the
book repository that consumes this package.

## Layout

- `src/press/` is the pip-installable pipeline. `python -m press <target>`
  (or `press <target>`) runs from inside a book repository.
- `src/press/data/` carries the house design (TeX header, CSS, reader
  templates), pandoc defaults templates, the jargon watchlist, universal
  known-bad fixtures, and the new-book template.
- `action.yml` is a composite action: a book's CI does
  `uses: clintecker/press@v1` and the press installs itself from the
  action's own checkout. That is what lets a private book use the private
  press with no cross-repo token; do not replace it with pip-from-git.
- `.github/workflows/build.yml` is the reusable workflow books call. It
  hardcodes the press action ref and the toolchain image tag; they are part
  of the pinned contract.
- The toolchain image `ghcr.io/clintecker/press-toolchain` is private by
  Clint's decision. Every new book repo must be granted read access once,
  by hand, under the package's Manage Actions access settings
  (https://github.com/users/clintecker/packages/container/press-toolchain/settings);
  until then its builds die at "Initialize containers" with a pull denial.
  The workflow already authenticates with the calling repo's token, so the
  grant is the only step.
- `src/press/data/workflows/editorial-passes.js` is the editorial machine:
  an agent workflow (per-chapter skill passes plus whole-book cadence,
  repetition, and arc passes producing suggestions; per-chapter
  synthesizers applying them; `press check` closing each round, iterating
  until suggestions dry up). The scaffold lays it into every book's
  `.claude/workflows/`; run it with the Workflow tool by name
  (`editorial-passes`) from inside a book. It hard-codes the named diseases
  of agent prose (epigram compulsion with a two-maxim quota, uniform
  rhetorical rhythm, self-annotation) because "apply the skills" alone
  produces locally-obedient, globally-patterned prose.
- `skills/` holds the authoring guides (four prose skills, jargon watchlist
  documentation, design skills for covers, plates, and logomarks). Read the
  relevant ones before composing prose or art direction for any book.

## The contract

Books pin a tag (`@v1`). Tags follow the GitHub Actions convention: `vN` is
a floating major that moves to the latest compatible `vN.x.y`; the
three-part tags are immutable. Design is part of the contract: within a
major, fixes may correct broken output but must not change typography or
layout of a valid book; design and template changes require a new major.
To release a fix: commit, tag `vN.x.y`, force-move `vN` to it, push both.
To release a new major: update the action ref in build.yml and the
requirements pin in the template to the new major, commit, tag, push.

## Config a book supplies

- `config/metadata.yaml`: identity plus press facts (`slug`, `repository`,
  `site-url`) and verification knobs (`verify-sentinels`,
  `verify-min-pages`, optional `trim`).
- `config/house-rules.yaml` (optional): `banned-patterns` (regex -> label),
  `jargon-allow`, `audit-dirs`.
- `config/index-terms.yaml` (optional): curated subject-index terms; the
  index appendix generates on every build and zero-hit terms fail it.
- `config/authorities.yaml` (optional): the table of authorities, a ledger
  mapping exact text fragments (claims of fact) to the sources that
  warrant them. The "Sources and authorities" appendix generates on every
  build; a claim whose sentence has left the text fails the run. Populate
  it with the `authorities-research` workflow (extract, research with web
  sources, adversarial audit, ledger write).
- `tex/title-page.tex` (optional): cover plate, title page, colophon.
- `assets/cover.jpg`, `assets/press-logo.png`, `assets/woodcuts/*.jpg`
  (all optional; every consumer degrades gracefully when absent).
- `tests/known-bad/` (optional): fixtures for the book's own house rules;
  every fixture must be rejected by a checker on every build.

## Scars (carried from the first book; do not relearn them)

- A figure taller than the text block makes LuaLaTeX ship empty pages
  forever, silently, at 100% CPU. The TeX header now caps every included
  image at 6.3in tall (caption room included) so markdown figures cannot
  trigger it; the cap in tex/title-page.tex covers the cover plate; never
  stack a third `titlepage`. Do not raise either cap near \textheight.
- Ubuntu has no `fonts-libertinus` package, and `--no-install-recommends`
  drops the Libertine keyboard face; the Dockerfile states
  `fonts-linuxlibertine` explicitly.
- The PDF builds through latexmk so multi-pass lists converge; plain
  lualatex under pandoc does not run enough passes. `toc-depth: 1` sets
  tocdepth 0, which silently empties the List of Plates; the TeX header
  raises the depth inside the lof file itself.
- hyperref anchors floats at the caption, not the image; list-of-plates
  links overshoot without `hypcap` (loaded in the hyperref after-hook).
  When touching PDF links, verify destinations with pypdf.
- pandoc's chunked writer copies referenced media itself; site assembly
  must tolerate existing directories.
- PNG barely compresses engraving grain; woodcut plates are JPEG q88 on
  purpose.
- Verifying `dist/` without rebuilding blesses stale artifacts; the CLI's
  dependency edges exist so that cannot happen. Keep them.
- The verify scripts render with `pdftoppm` when the authoring sandbox's
  renderer is absent. Keep that fallback working.
- First LuaLaTeX run on a fresh machine triggers a several-minute font scan
  that looks like a hang. It is not a hang.
- Never pipe a check command into grep before `&&` in a commit chain; the
  pipeline exit code is grep's, and a red check once shipped as green.

## Verifying changes here

The press has no book of its own, so prove changes against a real one:
clone a consuming book, `pip install -e` this checkout into it, run
`press all`, and confirm every verifier passes before tagging. A green
`pip install` is not a working pipeline.
