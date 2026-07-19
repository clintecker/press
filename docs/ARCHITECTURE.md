# The press, explained to someone who will change it

## The four laws

Everything here follows four laws, and a change that violates one is
wrong even when it works:

1. **Facts are stated once.** A book's identity lives in its config;
   the house design lives in press data; the artifact graph lives in
   the registry. If you find the same fact in two places, one of them
   is a bug already filed or a bug you should file.
2. **Generators over checkers over conventions.** Prefer machinery
   that produces the right thing to machinery that detects the wrong
   thing, and either to a sentence in a document asking people to
   behave.
3. **Artifacts are verified as objects.** A green build means the
   actual PDF was rendered and inspected, the actual EPUB was
   validated by the tool retail channels run, the actual site was
   crawled. Verifying without rebuilding is forbidden by construction.
4. **Scars become law.** Every production failure earns a mechanical
   guard and an entry in CLAUDE.md's scars list. Do not relearn them.

## The shape of the machine

- `booklib` / `bookmodel` — the one typed, normalized reading of a
  book's config, with locatable refusals. Nothing else parses
  metadata.
- `registry` — every artifact's outputs, prerequisites, and
  publication role, stated once; build order, download lists, and the
  CLI's format list derive from it.
- `build` — pandoc/LuaLaTeX orchestration through defaults templates
  (`@press/` and `@book/` path prefixes, `?optional` degradation).
- `gen_*` — the generators: front matter from config, the subject
  index, the authorities companion, the cover wrap with computed
  spine and EAN-13.
- `check_*`, `style_audit`, `jargon_lint` — the editorial law, which
  proves its own checkers against known-bad fixtures that each
  declare the rule they exist to trip.
- `verify_*` — the artifact inspectors: rendered-page PDF checks
  (with print-profile margin and ink laws), format witnesses, archive
  contracts, and the public-site crawl.
- `aesthetic` — the book's visual identity, merged over the house
  default; consumed by builders (palette, type, inks) and by the art
  workflows (prompt material).
- `instruments`, `operator`, `art`, `art_commission` — the packaged
  skills and agent workflows, their headless drivers, and the art
  department's commission/accept cycle.
- `selftest`, `doctor` — the press checking itself and the machine
  it runs on.

## The artifact contract

`registry.ARTIFACTS` is the authoritative table. Every published
artifact is built by `press all`, named in the Pages downloads,
attached to releases by the reusable workflow, and covered by a
verifier; `press pages` builds its full prerequisite graph from a
clean repository. Adding an artifact obliges you to: declare it in
the registry (outputs, prerequisites, role), give it a verifier or
state why none applies, and let `press selftest` prove the graph
still holds and the docs still name every target. The selftest fails
otherwise; that failure is the extension checklist.

## The invariant matrix

Every invariant the press enforces, where it is enforced, the
negative proof that the enforcement can actually fail (a selftest
check or a known-bad fixture), and what the enforcement does not
cover. An honest limitation column is the point: a guarantee whose
edges are unstated is a guarantee waiting to be overtrusted.
Universal fixtures live in `src/press/data/known-bad/`; a book adds
its own under `tests/known-bad/`.

This section is the narrative form. The same invariants live in
machine-checkable form in `quality/invariants.yaml`, whose validator
proves that every enforcer and proof it names still resolves to a
real function or fixture, and which generates
[docs/INVARIANTS.md](https://github.com/clintecker/press/blob/main/docs/INVARIANTS.md)
as the traceable table.

### Config law

| invariant | enforced at | negative proof | limitation |
|---|---|---|---|
| Slug is strict lowercase kebab (`[a-z0-9][a-z0-9-]*`), safe as an artifact basename | `booklib.validate_slug` | selftest `check_slug_invariant` (13 bad slugs refused) | none material; fullmatch |
| Trim is exactly 6 x 9 in v1; anything else is refused | `bookmodel._trim` | selftest `check_book_model` (5 x 8 refused) | hard-coded to the v1 design; v2 geometry is unsupported by design |
| Config defects are collected and reported together with file and key; YAML errors are located; non-mapping files refused | `bookmodel.load`, `booklib.load_config_mapping` | selftest `check_book_model`, `check_honest_refusals` | some YAML errors carry no line mark |
| Release builds refuse vacuous witnesses (fewer than 2 sentinels, page floor under 24) when `PRESS_RELEASE=1` | `booklib.require_release_witnesses`, set by build.yml on tag refs | none direct; wired by build.yml and exercised by the integration gate | counts only; two trivial sentinels satisfy it; drafts skip it entirely |
| Registrations arithmetic: ISBN and ISSN check digits computed, never trusted; `retail: true` fails on pending numbers | `registrations`, `barcode.validate` | selftest `check_arithmetic` | LCCN is shape-checked only; ISBN is not matched to the barcode edition |

### Editorial law

| invariant | enforced at | negative proof | limitation |
|---|---|---|---|
| Every chapter has an H1, real length, no TODO/TBD/lorem; metadata names title, author, description, slug; sentinels appear in source; no orphaned plates | `check_source` | none in selftest; the integration gate runs `press check` on a real book | forbidden list is three fixed phrases; plate check is a path-anchored substring |
| Universal prose battery: dashes, curly quotes, out-of-font glyphs, throat-clearing, title-case and numbered headings, paragraph length, book banned patterns | `style_audit` | fixtures `em-dash.md`, `curly-quotes.md`, `emoji.md`, `title-case.md`, `numbered-heading.md`, `long-paragraph.md` | glyph law flags legitimate Greek or math; short title-case headings slip |
| Jargon watchlist terms at rewrite severity fail the run | `jargon_lint` via the check target | fixture `jargon.md` | exact matches only; per-book allow list can silence any term |
| Every known-bad fixture must trip its declared rule; known-good must pass clean | `check_the_checkers` | the fixtures are the proof; a fixture nothing rejects fails the build | a book fixture without an `expect:` comment falls back to any-rejection |
| A malformed book-supplied banned regex is refused by name | `style_audit.banned_book_patterns` | selftest `check_honest_refusals` | only regex-compile errors are caught |

### Generated appendices

| invariant | enforced at | negative proof | limitation |
|---|---|---|---|
| Every authorities claim exists in the manuscript exactly once, in its declared file; malformed, duplicate, missing, moved, and ambiguous entries are each named | `gen_authorities` | selftest `check_authorities_ledger` (all five diagnostics driven) | whitespace-normalized substring match; a coincidental duplicate of the fragment counts as a hit |
| Researched source text is print-safe and TeX-safe | `gen_authorities.print_safe` | selftest `check_honest_refusals` (backslash stripped) | fixed replacement table |
| Every curated index term matches the text; zero hits fail by name | `gen_index` | none | an over-broad match alternative matches spuriously |

### The PDF object

| invariant | enforced at | negative proof | limitation |
|---|---|---|---|
| The blank-page detector is proven before it judges | `verify_pdf.self_test_detector` | self-contained: it fails on a detector that misjudges its fixtures | two synthetic extremes; a page bearing only a faint hairline can still read as blank |
| Trim matches metadata within 1pt; page count meets the floor | `verify_pdf.verify_info` | none; runs only against a real rendered PDF | a floor, not a shape: padded pages pass |
| Sentinels and title survive into extracted text | `verify_pdf.verify_sentinel_text` | sentinel machinery proven by selftest `check_format_witnesses` | vacuous with no sentinels declared (release gate closes this) |
| All fonts embedded | `verify_pdf.verify_fonts` | none | parses `pdffonts` columns; a Poppler format change could slip through |
| Every List of Plates link lands on a page bearing an image | `verify_pdf.verify_plate_links` | none | checks for an image, not the correct image; degrades to a notice without pypdf |
| Every rendered page carries ink and keeps it off the edge | `verify_pdf.verify_page_ink` | detector proven by `self_test_detector` | tolerates one structural blank verso in print profile |
| Print profile: mirrored margins, gutter on the binding side | `verify_pdf.verify_mirrored_margins` | none | a median over body pages; erratic indentation can confuse it |
| Print profile: no colored ink in the interior | `verify_pdf.verify_black_ink` | none | a 200-pixel chroma budget for JPEG noise; a tiny colored mark slips under it |

### The other formats

| invariant | enforced at | negative proof | limitation |
|---|---|---|---|
| Title and a derived manuscript witness appear in every format; a book yielding no witness is refused, not passed | `verify_formats.require_witnesses` | selftest `check_format_witnesses` | one longest line per document; a format dropping every other line still passes |
| Each chapter's witness appears exactly once across the reader site | `verify_formats.verify_site` | selftest `check_format_witnesses` (forced duplicate and forced missing) | a chapter with no qualifying line contributes no witness |
| EPUB: valid mimetype and container, non-empty date, registered ISBN in the OPF, sentinels in text | `verify_formats.verify_epub` | none for the EPUB-specific checks | ISBN is a substring test in OPF text, not schema-located |
| EPUB passes epubcheck; a present-but-unrunnable tool is a toolchain fault, not an EPUB fault | `verify_formats.epubcheck` | none in selftest (needs the real jar) | strictness keys on `PRESS_TOOLCHAIN`; an image setting neither would warn and pass |
| DOCX text is read across split runs; embedded images at least match the plate count | `verify_formats.verify_docx` | selftest `check_format_witnesses` | image count is a floor; images are not matched to the woodcuts |

### The public site

| invariant | enforced at | negative proof | limitation |
|---|---|---|---|
| Every local reference and stylesheet url resolves; fragments resolve to real anchors | `verify_pages.check_refs` | selftest `check_pages_verifier` (five distinct breakages driven) | external links are skipped; a dead external URL is never caught |
| Every declared download exists and is linked from the landing page exactly once | `verify_pages.check_downloads` | the integration gate deletes a download and asserts refusal | the download list comes from the registry; an unregistered file is invisible |
| Sentinels appear on the public reading surface; the landing page names the book | `verify_pages.check_reading_surface` | exercised inside `check_pages_verifier` fixtures | reading text is aggregated; a sentinel on the wrong chapter passes |

### Archives and source policy

| invariant | enforced at | negative proof | limitation |
|---|---|---|---|
| The reader zip is byte-for-byte the verified site directory | `verify_archives.verify_site_zip` | selftest `check_source_policy` (one flipped byte refused) | compares to the on-disk site, which must itself have been verified first |
| The source zip holds exactly what `publication_members` admits: tracked files only, symlinks never dereferenced, secret-pattern files abort, no member escapes its prefix | `package_source.publication_members`, `verify_archives.verify_source_zip` | selftest `check_source_policy` (`.env` aborts, symlink skipped, extra member refused) | secret and junk patterns are fixed lists; a novel secret filename is not caught; expectation is recomputed at verify time |
| The sources companion names the book and holds real entries | `verify_archives.verify_sources_companion` | none for the emptiness path | a length-and-marker heuristic |

### The cover wrap

| invariant | enforced at | negative proof | limitation |
|---|---|---|---|
| One page at exactly trim plus bleed plus spine, spine recomputed from the built interior, never restated | `gen_coverwrap` and `verify_coverwrap`, sharing one geometry | none for the geometry; generator and verifier cannot disagree because the math is shared | spine trusts the declared paper stock; a wrong stock yields a wrong but self-consistent spine |
| The front panel is not blank or flat | `verify_coverwrap.check_front_panel` | selftest `check_coverwrap_detectors` (flat panel refused) | a stddev threshold; a very low-contrast cover could read as flat |
| The barcode panel has its white card, enough bar transitions, and clean quiet zones | `verify_coverwrap.scanline` | selftest `check_coverwrap_detectors` (all three refusals driven) | 25 transitions against EAN-13's real 59; it proves a symbol, not the right symbol |

### The build graph

| invariant | enforced at | negative proof | limitation |
|---|---|---|---|
| The artifact graph is acyclic, outputs unique, every published artifact a concrete filename | `registry.build_order` | selftest `check_registry` | proves graph shape, not that each builder produces its declared output |
| Verify targets rebuild before verifying; a stale artifact cannot be blessed | the CLI's dependency edges in `__main__` | the integration gate tampers and calls the verifier directly to prove it sees the damage | CLI-path only; importing a verifier module directly skips the rebuild |
| Pages assembly refuses a missing declared download | `build.pages_build` | none | existence, not freshness (freshness is the rebuild edge's job) |
| Metadata interpolated into HTML and TeX is escaped | `build.cover_fragment_html`, `gen_front_matter.escape`, `gen_coverwrap` | selftest `check_honest_refusals` (cover fragment) | the proof covers the cover fragment; sibling sites share the pattern unproven |
| A failing tool's exit code passes through the console, never a traceback | `__main__.console` | selftest `check_honest_refusals` (exit 43 passes through) | only `CalledProcessError` is unwrapped |
| Interior figures are capped below the text block height so LuaLaTeX cannot ship empty pages forever | `data/tex/book-header.tex` (6.3in cap), `front-matter.tex` (cover cap) | none automated; the blank-page checks would catch the symptom | a TeX constant guarded by comment, not machine-enforced against edits |

### The CI boundary

| invariant | enforced at | negative proof | limitation |
|---|---|---|---|
| A three-part tag pins its own action ref and an existing immutable `sha-` toolchain image | `.github/workflows/release-contract.yml` | selftest `check_release_grammar` proves the tag grammar and injection refusals | the pin grep is an exact string; it does not prove the tag's tree |
| Releases cut only from a default-branch commit with a green integration gate | build.yml ancestry check, release-contract gate poll | none automated beyond the workflows themselves | relies on the check run's exact name |
| The integration gate builds the wheel, raises a stranger's book in the real container, runs the gauntlet, then tampers to prove refusal | `.github/workflows/integration.yml` | the tamper step is the proof | the CI neutrality grep is two literal strings; the thorough check is the selftest |
| No original-book identity leaks into a clean scaffold | integration gate grep, selftest `check_scaffold_neutrality` | `check_scaffold_neutrality` | pattern-based; a novel identifying string is not caught |
| Docs cannot drift: usage and README name every target, REFERENCE.md equals the generated text, the aesthetics skill documents every consumed key | selftest `check_docs`, `check_aesthetic_schema` | these checks are the negative proof; they fail on drift | presence tests, not semantic ones |

## Provenance and verification

Two different kinds of trust operate in a build, and it pays to keep
them distinct.

Generated-from-config facts are provenance: the press produced them
from declared inputs, so they are right by construction as long as
the generator is right. The front matter pages come from
`config/front-matter.yaml` and `config/metadata.yaml`; the cover
wrap's spine width, trim geometry, and EAN-13 come from the rendered
interior's page count and the declared paper stock; the subject index
comes from `config/index-terms.yaml` against the manuscript; the
authorities companion comes from `config/authorities.yaml`. None of
these can drift from their inputs, because they are regenerated on
every build (the generated appendices are cleaned first so stale
copies cannot survive).

Verified-now facts are the other kind: claims about the artifact
object itself, proven against the bytes this build produced. Every
verifier runs against the artifact it names, in the same run that
built it: the PDF's pages are rendered and inspected, the EPUB goes
through epubcheck, the archives are opened and their members
compared to policy, the public site is crawled. Nothing is trusted
from a previous run; the CLI's dependency edges force a rebuild
before any verification, so a stale artifact cannot be blessed.

The rule of thumb: generation makes a fact true, verification proves
it stayed true all the way into the object a reader receives. A fact
that is only generated is trusted exactly as far as its generator;
a fact that is verified is trusted as far as this build's evidence.

## The release contract

Books pin `@v1` (floating) or a three-part tag (immutable, enforced:
the release-contract workflow proves each tag pins its own action ref
and an existing immutable toolchain sha). Design is part of the
contract: within a major, fixes may correct broken output but must
not change a valid book's typography; design changes wait for a new
major. Releases are gated on the integration workflow, which builds
the wheel, raises a stranger's book inside the real container, runs
the whole gauntlet, and tampers with an artifact to prove the
verifiers still refuse. Tag builds run with `PRESS_RELEASE=1`, which
refuses vacuous witnesses.

## Design versioning

Typography and layout are part of the pinned contract, not an
implementation detail behind it. The policy, restated plainly:

- Within a major version, a fix may correct broken output (a page
  that failed to render, a link that pointed nowhere, an artifact a
  verifier refused) but must not change the typography or layout of
  a book that was already valid. A book that rebuilt cleanly
  yesterday must produce the same design today.
- Design and template changes, however small they look, require a
  new major version. A different margin, face, or front-matter
  arrangement is a new contract, and books opt into it by moving
  their pin.
- Three-part tags (`vN.x.y`) are immutable, and the immutability is
  enforced rather than promised: the release-contract workflow
  proves that each three-part tag's build.yml pins the press action
  to that exact tag and the toolchain image to an existing immutable
  `sha-` tag, so a pinned book resolves the same pipeline, action,
  and toolchain bytes forever.
- `vN` floats: it moves to the latest compatible `vN.x.y`, following
  the GitHub Actions convention. A book that pins `@v1` accepts
  fixes within the design contract; a book that pins `@v1.x.y`
  accepts nothing at all.

## Where a book ends and the press begins

A book holds its manuscript, config, and accepted art — nothing else.
If a book needs machinery, the machinery belongs here. If the press
needs a book-specific fact, it must arrive through config. The
integration gate enforces the second rule mechanically: no original-
book identity may appear in a clean scaffold's public artifacts.
