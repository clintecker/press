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
  action's own checkout. The press repo is public
  (since 2026-07-19; proven by press-smoke, the standing boundary
  fixture), but self-checkout install is still the law: it keeps a
  private book working with no cross-repo token and pins the installed
  press to the exact action ref; do not replace it with pip-from-git.
- `scripts/build_site.py` + `site/press.css` build the press's own
  documentation site (its home is `site/landing.md`, written for a
  first-time author; then the `docs/` suite, CHANGELOG, ROADMAP, and
  CONTRIBUTING/SUPPORT/SECURITY through pandoc) with a grouped left-sidebar
  nav, theme-aware syntax highlighting, canonical/social metadata, and
  build-time link, on-site-link, and accessibility checks; `README.md` is
  the repository front page and stays off the site (NOT_PUBLISHED).
  `.github/workflows/docs-site.yml` deploys it to
  <https://clintecker.github.io/press/> on every push to main. The site's
  content is generated from the repo, so it cannot drift.
- `.github/workflows/build.yml` is the reusable workflow books call. It
  hardcodes the press action ref and the toolchain image tag; they are part
  of the pinned contract.
- The toolchain image `ghcr.io/clintecker/press-toolchain` is public
  (since 2026-07-20; #161): a book under any account pulls it with no
  package grant and no configured secret. In CI the pull is authenticated
  with the workflow's own `GITHUB_TOKEN` (which works for a public image,
  including on fork and Dependabot pull requests); locally it pulls
  anonymously. The image is still pinned in build.yml and the pin is part
  of the immutable release contract, so every build runs against the exact
  toolchain bytes the release was proven on. Making it public was a
  one-time visibility change; there is no per-repo step anymore.
- `src/press/data/workflows/editorial-passes.js` is the editorial machine:
  an agent workflow (per-chapter skill passes plus whole-book cadence,
  repetition, and arc passes producing suggestions; per-chapter
  synthesizers applying them; `press check` closing each round, iterating
  until suggestions dry up). The scaffold lays it into every book's
  `.claude/workflows/`, stamped with the press version so drift is
  visible; run it with the Workflow tool by name (`editorial-passes`)
  from inside a book. It hard-codes the named diseases
  of agent prose (epigram compulsion with a two-maxim quota, uniform
  rhetorical rhythm, self-annotation) because "apply the skills" alone
  produces locally-obedient, globally-patterned prose. Its siblings:
  `authorities-research` (the sources ledger), `aesthetic-brief` (drafts
  `config/aesthetic.yaml` from an author's one-line brief, behind
  `press aesthetic "<brief>"`), and `art-direction` (reads
  the manuscript, applies the design skills, writes `art/commissions.md`
  with paste-ready image-model prompts; results come back in through
  `press art accept <file> --as cover|plate:<name>|logomark|portrait`,
  which converts to house format (plates gray to single ink when the
  aesthetic states it; an opaque logomark gets its ink extracted onto
  transparency), enforces the geometry scars, and updates the
  commission record). An author photograph supplied at
  `art/author-photo.jpg` makes the portrait commission engrave the
  actual author.
- `src/press/data/skills/` holds the authoring guides (four prose skills,
  the overused-jargon skill whose `references/watchlist.csv` is the one
  watchlist the jargon lint reads, design skills for covers, plates, and
  logomarks, and the registrations skill: the ISBN/LCCN/ISSN paperwork
  end to end). They are package data: `press skills` lists them with
  installed paths, `press workflows` prints paste-ready workflow
  invocations, and workflows resolve skills through `press skills` before
  falling back to a checkout. Read the relevant ones before composing
  prose or art direction for any book.

## Where this is going

ROADMAP.md is the plan for press as the whole publisher: self-contained
skills and workflows (M1), the art department (M2), front matter from
metadata (M3), the print pack for KDP/IngramSpark (M4), registrations
(M5). Read it before adding capability to a book repo; if a book needs
machinery, the machinery belongs here.

## The contract

Books pin a tag (`@v1`). Tags follow the GitHub Actions convention: `vN` is
a floating major that moves to the latest compatible `vN.x.y`; the
three-part tags are immutable, and immutability is enforced, not
promised: a three-part tag's build.yml must pin the press action to
that exact tag and the toolchain image to an existing immutable
`sha-` tag (the release-contract workflow turns red otherwise), so a
pinned book resolves the same pipeline, action, and toolchain bytes
forever, while `vN` floats normally. Design is part of the contract:
within a major, fixes may correct broken output but must not change
typography or layout of a valid book; design and template changes
require a new major.
To release: roll the CHANGELOG's [Unreleased] section into a version
section, then run `scripts/release.sh vN.x.y`. The script is the one
release path and a resumable state machine: it validates strict
SemVer, preflights remote state, pins build.yml and pyproject,
commits, tags, waits for the tag's release contract to prove, floats
`vN` only then, and publishes the GitHub Release; rerunning after any
failure is the recovery procedure. For a new major, also move the
requirements pin in the template.

## Config a book supplies

Every field below can be read, written, and validated with
`press config get|set|unset|list|validate` (each write is checked by the
same typed model that validates a build, before a byte is touched), or from
the operator desk's setup wizard (`press desk`, then `w`); hand-editing the
YAML remains available for experts.

- `config/metadata.yaml`: identity plus press facts (`slug`, `repository`,
  `site-url`) and verification knobs (`verify-sentinels`,
  `verify-min-pages`, optional `trim`). The print pack reads optional
  `print:` (`paper: white|cream` or `page-thickness:`) for spine math
  and `registrations: {isbn: {print: ...}}` for the wrap barcode; a
  missing ISBN renders an honest placeholder.
- `config/house-rules.yaml` (optional): `banned-patterns` (regex -> label),
  `jargon-allow`, `audit-dirs`.
- `config/index-terms.yaml` (optional): curated subject-index terms; the
  index appendix generates on every build and zero-hit terms fail it.
- `config/authorities.yaml` (optional): the table of authorities, a ledger
  mapping exact text fragments (claims of fact) to the sources that
  warrant them. Every build verifies each claim still appears exactly
  once in its declared file (a claim whose sentence has left the text
  fails the run) and renders the ledger as a standalone
  sources-and-authorities companion document published beside the
  book, not as an appendix inside it. Populate it with the
  `authorities-research` workflow (extract, research with web
  sources, adversarial audit, ledger write).
- `config/aesthetic.yaml` (optional): the book's visual identity
  (cover grammar, plate medium, logomark tradition, portrait style,
  register), applied by every art commission; absent, the house
  Victorian idiom in `data/aesthetic-house.yaml` applies. Draft it by
  interview (book-aesthetics skill) or `press aesthetic "<brief>"`;
  `press aesthetic` shows the effective merge. Craft laws (verbatim
  text, flat plates, single-ink interiors) are not configurable.
- `config/front-matter.yaml` (optional): everything book-variable on
  the generated front matter: dedication, epigraph, acknowledgements,
  and the colophon knobs (edition-note, manufacture, colophon-note,
  rights-notice, contact, motto). Its presence asks the press to
  generate the PDF title page and surrounding pages from config; the
  title page stacks the subtitle's OR clauses; absent keys simply do
  not render.
- `tex/title-page.tex` (optional): cover plate, title page, colophon,
  overriding the generated front matter entirely.
- `assets/cover.jpg`, `assets/press-logo.png`, `assets/woodcuts/*.jpg`
  (all optional; every consumer degrades gracefully when absent).
- `assets/web/reader.css` (optional) replaces the house reader
  stylesheet outright; `assets/web/extra.css` (optional) appends after
  it, winning the cascade, and is also injected into the pages landing
  page. The aesthetic palette applies to either; a book supplying
  neither renders byte-identically to before.
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
- Ubuntu's `epubcheck` launcher runs the jar through binfmt_misc, which
  containers do not register: the command exists, `which` finds it, and
  it dies with "Exec format error" only at execution. The Dockerfile
  ships a plain `java -jar` wrapper, and the verifier reports a
  present-but-unrunnable tool as a toolchain fault, not an EPUB fault.
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
