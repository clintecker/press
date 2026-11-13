# Table rendering today: research note (2026-11-12)

Facts gathered for the shape-aware table spec (reference lists vs grids).
Every claim cites a file and line; quotes are verbatim. The pinned toolchain
image (`build.yml:28`, `press-toolchain@sha256:0d784ac0…`) carries
**pandoc 3.1.3** (Ubuntu 24.04 apt, `Dockerfile:25-38`); the local dev box has
pandoc 3.9.0.2. The CI quality job also apt-installs pandoc on ubuntu-24.04
(`.github/workflows/selftest.yml:30-32`). Sample renders below were run in the
pinned image.

## 1. How a pandoc table reaches each edition

### Defaults files (`src/press/data/defaults/`)

| Edition | Defaults | Filters, in order | Writer notes |
|---|---|---|---|
| PDF | `pdf.yaml` | typographic-spacing, set-pieces, chapter-dropcap, scene-break, figure-numbering (`:11-16`) | `include-in-header` book-header.tex + profile/aesthetic/front-matter (`:17-23`); `lot: false` (`:36`) |
| Print interior | `print.yaml` | same plus `print-safe-images.lua` after set-pieces (`:17-23`) | adds `print-header.tex` (`:32-40`); `lot: false` (`:53`) |
| EPUB | `epub.yaml` | same five as PDF (`:8-13`) | `css: @press/tex/epub.css` (`:14-15`) |
| Single-leaf HTML | `html.yaml` | same five (`:8-13`) | `self-contained: true`; `css: @press/tex/book.css` (`:16-17`) |
| Reader site | `chunked.yaml` | same five (`:8-13`) | `--to=chunkedhtml` (`build.py:326`); `css: reader.css` (`:15-16`), written by `site_stylesheet()` (`build.py:287-316`) |
| DOCX | `portable.yaml` | typographic-spacing, set-pieces, figure-numbering only (`:7-10`) | `build.py:654`: `pandoc_build("portable", f"dist/{slug}.docx", extra=["--to=docx"])`; no `reference-doc` |
| Plain text | `portable.yaml` | same three | `build.py:651-653`: `--to=plain`, `--columns=80` |
| Markdown | none | no pandoc at all | `markdown_build` (`build.py:256-274`) stitches the source chapters through `strip_heading_attrs` |

### No filter touches a Table today

`grep -n "Table\|SimpleTable" src/press/data/lua/*.lua` finds one hit:
`chapter-dropcap.lua:119` (`Table = true,`), inside the `SKIP` set
(`:113-122`) of blocks that are "not the opening prose paragraph". No filter
defines a `Table` function; no file references `SimpleTable`.

### How filters pick the writer

- `set-pieces.lua:30-32`:
  `local function is_web() return FORMAT:match("html") ~= nil or FORMAT:match("epub") ~= nil end`
  with comment (`:27-29`) "every other writer (markdown, plain text, docx) gets
  a clean native line block".
- `figure-numbering.lua:192`: `local latex = FORMAT == "latex" or FORMAT == "beamer"`.
- `chapter-dropcap.lua:159`, `:265` and `scene-break.lua:23,26,38,41` use
  `FORMAT:match("latex")` / `FORMAT:match("html") or FORMAT:match("epub")`.
- `strip_house_keys` (`figure-numbering.lua:63-68`) nils `place`, `outset`,
  `decorative`, `fig-alt` on an image: "The house-only attributes that must
  never leak into the output (pandoc would otherwise pass them through as
  data-* on the HTML <img>)."

### Lua conventions

- `press-util.lua` (113 lines) holds pure helpers with "No pandoc-AST
  dependency, so they are unit-tested under plain Lua
  (tests/lua/test_press_util.lua via `pandoc lua`)" (`:1-6`). Exports:
  `MEASURE_WIDTH`, `MEASURE_PERCENT`, `MEASURE_GUARD`, `is_true` (`:37`),
  `width_opt` (`:43`), `cascade_indent` (`:63`), `tail_ramp` (`:97`),
  `tail_web_size` (`:105`).
- Filters load it relative to themselves (`set-pieces.lua:20-22`):
  `local here = (PANDOC_SCRIPT_FILE or ""):match("^(.*[/\\])") or "./"`,
  `package.path = here .. "?.lua;" .. package.path`, `require("press-util")`.
- Filter tests run pandoc directly through a `_render` helper, e.g.
  `tests/test_figure_numbering_filter.py:30-44` (`pandoc -f markdown+smart -t
  <to> --top-level-division=chapter --number-sections` plus
  `lua_coverage.filter_arg(FILTER)`), marked `pytestmark =
  lua_coverage.needs_pandoc` (`:27`) and per-test
  `@pytest.mark.layer("integration")` / `@pytest.mark.proof("positive"|"negative")`.
  The byte-identity idiom: `test_a_book_with_no_numbered_figures_is_byte_identical`
  (`:121-131`) asserts `_render(doc, to=fmt, filtered=False) == _render(doc, to=fmt)`.
- Pure-helper tests: `tests/lua/test_press_util.lua` (an `eq()` harness,
  `:9-16`) driven by `tests/test_press_util_lua.py` with `PRESS_LUA_DIR`.
- Every `*.lua` must compile: `tests/test_lua_compiles.py:25`
  (`FILTERS = sorted(LUA_DIR.glob("*.lua"))`). Lint: `scripts/lua-lint.sh:16`
  (`selene src/press/data/lua/`), stylua, `scripts/lua-syntax-gate.sh`.

### The Lua coverage ratchet

- Harness: `tests/lua_coverage.py` (`filter_arg`, env `PRESS_LUA_COV_DIR`)
  inlines `tests/lua/coverage-hook.lua` (a `debug.sethook` line tracer) into a
  per-filter shim.
- Floors: `.celebrimbor/baselines/lua-coverage.yaml:9-16` (per filter, e.g.
  `figure-numbering.lua: 87.8`, `press-util.lua: 96.7`). Enforced by
  `scripts/lua_coverage_ratchet.py`; its docstring (`:17-18`): "``check`` also
  fails for any ``*.lua`` filter that has no floor in the baseline: a new
  filter must be given one with ``update``."
- `scripts/verify.sh:40-56` runs the ratchet over a **hard-coded list** of
  test files (`:48-50`: figure_numbering_filter, figure_placement, set_pieces,
  scene_break, dropcaps_filter, typographic_spacing, print_safe_images_filter);
  a new filter's test file must be added there. CI instead sets
  `PRESS_LUA_COV_DIR` across the whole pytest run (`selftest.yml:36-41`) then
  `report`/`check` (`:65-71`).
- CONTRIBUTING.md:52-58: never `update` from a macOS measurement; feed CI's
  report with `update --from-report`.

## 2. The PDF

### What pandoc 3.1.3 emits (rendered in the pinned image)

A short two-column pipe table with a caption:

```latex
\begin{longtable}[]{@{}ll@{}}
\caption{Commands.}\tabularnewline
\toprule\noalign{}
Command & What it does \\
\midrule\noalign{}
\endfirsthead
...
\texttt{press\ all} & Builds every edition and verifies them. \\
```

A pipe table with any source line wider than `--columns` (72 by default)
gets relative `p{}` columns and minipage headers instead:

```latex
\begin{longtable}[]{@{}
  >{\raggedright\arraybackslash}p{(\columnwidth - 2\tabcolsep) * \real{0.5000}}
  >{\raggedright\arraybackslash}p{(\columnwidth - 2\tabcolsep) * \real{0.5000}}@{}}
```

So a short-source table gets `ll`: **neither column wraps**, and a long cell
runs past the text block. Code spans are `\texttt{press\ all}` (the space is
a backslash-space, an interword space that can still break; issue #287 reports `\texttt`
hyphenating at line ends). The standalone preamble pandoc adds:
`\usepackage{longtable,booktabs,array}`, `\usepackage{calc}`, a
`\patchcmd\longtable` fix, and `\makesavenoteenv{longtable}`.

### What the house TeX header sets for tables

Nothing. `src/press/data/tex/book-header.tex` (260 lines) has no `longtable`,
`booktabs`, `\arraystretch`, `\tabcolsep`, `LTcapwidth`, or table font
setting. `print-header.tex` (10 lines) only re-sets geometry
(`:5`, `\geometry{inner=0.88in,outer=0.58in}`). Relevant settings that do
reach tables:

- Fonts: `\usepackage{libertinus}` (`:12`),
  `\usepackage[scaled=0.86]{sourcecodepro}` (`:13`); `fontsize: 10pt`
  (`pdf.yaml:30`).
- Captions: `\usepackage{caption}` with
  `\captionsetup{font={small,it},labelformat=empty,labelsep=none,justification=centering,singlelinecheck=true,hypcap=true}`
  (`book-header.tex:137-139`). This is global, so a longtable `\caption`
  prints with **no automatic "Table N" label**, small italic, centred.
- `\floatplacement{figure}{H}` (`:147`) applies to figures only.
- `\setlength{\parindent}{1.1em}` (`:69`), `\linespread{1.045}` (`:71`).

### Caption numbering and the List of Tables

- `lot: false` in both PDF defaults (`pdf.yaml:36`, `print.yaml:53`); no
  `\listoftables` anywhere in `src/press/data/tex/`.
- "Table 9.1" style numbers are authored text, not generated. Publishing with
  Press writes `Table: Table 9.1. The house 6 by 9 page`
  (`~/code/publishing-with-press/book/chapters/09-the-house-design.md:43`) and
  refers to it by hand ("Table 9.1 gives every measurement", `:29`). The
  longtable `\caption` still steps LaTeX's `table` counter invisibly.
- No Lua filter numbers tables or resolves `@tbl:` (grep for `tbl` in
  `src/press/data/lua/` is empty); figure numbering is the precedent
  (`figure-numbering.lua`, `\PressListOfFigures` at `book-header.tex:112-121`).

### Description lists and hanging indents already in the header

- `\usepackage{enumitem}` is loaded (`book-header.tex:16`), but only
  `\setlist[itemize]` and `\setlist[enumerate]` are configured (`:72-73`); no
  `\setlist[description]`, no hanging-indent environment.
- pandoc 3.1.3 renders a Markdown definition list as
  `\begin{description}\tightlist\item[\texttt{press\ all}] Builds every edition. ...\end{description}`,
  so it gets KOMA scrbook's default description styling.
- Nearest house precedent for a custom block environment: `PressVerse`
  (`:212-215`, `\leftskip=3em\rightskip=0pt plus 2em\parindent=0pt`); the
  mdframed `quote` (`:218-232`); `\pretocmd{\section}{\Needspace{5\baselineskip}}`
  (`:235-236`) for stranding.
- Open issue #286 asks for `\needspace` before longtables (head plus 2-3
  rows) and before each description `\item`, citing seven stranded table heads
  in one PWP build.

### Print pack and PDF verifiers

- `print-safe-images.lua` only rewrites `Image` (`:7`); `press.print_safe`
  handles image files. Neither touches tables.
- `verify-print` (`__main__.py:425-440`) runs `verify_pdf.main([...,
  "--profile", "print"])` then the coverwrap. `verify_pdf.verify_page_ink`
  (`verify_pdf.py:374-399`) fails on blank pages, "ink touches rendered page
  edge", and inconsistent dimensions. `edge_has_ink` (`:166-175`) samples a
  **2-pixel border of the paper**, so a table that overruns the text block into
  the 0.58-0.88in margins is not detected; nothing reads the LaTeX log for
  Overfull `\hbox`. `verify_mirrored_margins` (`:185-206`) compares ink bboxes
  of recto/verso; a table overrunning the outer margin could perturb it.

## 3. HTML, the reader site, and EPUB

### reader.css (the reader site; 298 lines)

- No table rule at reading width. Base frame: `body { margin: 2.5rem auto;
  max-width: 48rem; ... font-size: 1.25rem; line-height: 1.62; ... padding:
  3rem 3rem 3.5rem; }` (`:23-33`); below 56rem the body is full-bleed with
  `padding: 1.6rem 1.25rem 3rem` (`:34-37`).
- Code: `code { font-size: .85em; background: var(--paper-warm); padding:
  .08em .3em; }` (`:141`); `pre { ... overflow-x: auto; }` (`:138-140`). No
  `white-space`/`overflow-wrap` rule on inline `code`.
- Section numbering collides: `/* 12. Dark mode */` (`:227`) and
  `/* 12. Tables, on a narrow screen only` (`:251`).
- The tables section (`:251-289`) applies only `@media (max-width: 34rem)` and
  only to `table:has(td[data-label])`: thead visually hidden (`:267-270`),
  rows as cards on `--paper-warm` with a hairline border (`:274-277`), cells
  `overflow-wrap: anywhere` (`:278-281`), `td::before { content:
  attr(data-label); ... font-size: .7em; font-weight: 700; text-transform:
  uppercase; }` (`:283-287`). Its comment (`:258-264`): "Giving tables a house
  treatment at every width is a design change and belongs to the next major."

### book.css (single-leaf HTML; 115 lines) and epub.css (44 lines)

- book.css: body `font-size: 19px; line-height: 1.58; max-width: 42rem`
  (`:10-19`); `code, pre { font-family: ... }`, `pre { overflow-x: auto; }`
  (`:31-32`); the same phone-card block at `:71-105` under
  `@media (max-width: 34rem)`. No reading-width table rule.
- epub.css: no table rule of any kind; `code, pre { font-family: monospace; }`
  (`:4`); figure corrections at `:39-44`.

### webmeta.label_table_cells and #283

`src/press/webmeta.py:195-254`. The row match (`:251`):

```python
labelled = _re.sub(r"<tr>.*?</tr>", one_row, body.group(0), flags=_re.S)
```

pandoc 3.1.3 writes body rows as `<tr class="odd">` / `<tr class="even">`
(confirmed in the image), so no row matches and no cell gets `data-label`;
the phone CSS keys on `td[data-label]`, so it never fires in a CI-built book.
Issue #283 (open) reports 34 unlabelled rows in PWP Appendix A and proposes
`<tr\b[^>]*>.*?</tr>`. The unit tests build bare `<tr>` fixtures
(`tests/test_webmeta.py:109`, `:112-169`), which is why they pass. Tables with
no `<thead>` are deliberately skipped (`:228-230`; docstring `:221-224`).
webmeta is `role: pure` in `.celebrimbor/surfaces.yaml:597-600`, coverage
floor 95.0 (`baselines/coverage.yaml:89`).

### Where webmeta runs

| Surface | Call site | Stylesheet |
|---|---|---|
| Reader site pages | `reader_meta.inject_reader_metadata` (`reader_meta.py:151`), `text = webmeta.label_table_cells(text)` at `:196`, called from `site_build` (`build.py:337`) | reader.css |
| Single-leaf HTML | `_build_html` (`build.py:626-636`) post-pass at `:634-636` | book.css |
| Pages landing | `_landing_index_html` returns `webmeta.label_table_cells(page)` (`build.py:510`) | reader-derived |
| Press docs site | `scripts/build_site.py:1157` | site/press.css |
| EPUB | **not run**: `_build_epub` (`build.py:594-624`) is `pandoc_build("epub", ...)` only | epub.css |
| DOCX, txt, md | not applicable | none |

So both HTML editions run the labeller (both currently defeated by #283);
EPUB has neither labels nor any table CSS.

### Precedent: the docs site already has a ledger-like record treatment

`site/press.css:181-191` styles all docs tables (`display:block;
overflow-x:auto`, uppercase small `thead th`, hairline `tbody td`), and
`:193-224` defines `body.doc-entries` for reference records (`td:first-child`
bold muted, `width:28%; white-space:nowrap`), applied per page by
`scripts/build_site.py:258-259` (`"invariants.html": "doc-entries"`). Narrow
rules at `:390-400`. This is the docs site only, not a book surface.

## 4. DOCX

- Today: `portable.yaml` with three filters and no reference document
  (`build.py:654`). pandoc's default `reference.docx` (3.1.3) declares styles
  including `Table`, `TableCaption`, `Compact`, `DefinitionTerm`, `Definition`,
  `VerbatimChar`, `BodyText`, `FirstParagraph` (listed from
  `pandoc --print-default-data-file reference.docx`, `word/styles.xml`).
  pandoc writes a definition list as `DefinitionTerm` / `Definition`
  paragraphs, and a table with the `Table` table style.
- Round 1B plan (`docs/ROUND-1B-EDITION-PARITY-V4-PLAN.md`), Task 5
  (`:168-200`): create `src/press/data/defaults/docx.yaml` "from
  `portable.yaml` ... filters `typographic-spacing`, `set-pieces`,
  `scene-break`, `figure-numbering`; `reference-doc:
  "@book/build/reference.docx"`" (`:171`); new `src/press/docx_ooxml.py`
  (`:172`) with `HOUSE_STYLES` for exactly six styles (`FigureCaption`,
  `Verse`, `Cascade`, `Tail`, `SceneBreak`, `FrontispieceImage`; `:180`) and
  `reference_doc(out)` that "runs `pandoc --print-default-data-file
  reference.docx`, appends every HOUSE_STYLES entry absent from
  `word/styles.xml`" (`:181`); `build._build_docx` (`:182`). Ruling 3
  (`:26`): the DOCX "always builds through `docx.yaml` with the generated
  reference document". `postprocess(path)` (Task 6, `:216`) is the OOXML
  rewrite hook.
- Implication: a reference-list style for Word slots in as a seventh
  `HOUSE_STYLES` entry, or by restyling pandoc's existing `DefinitionTerm` /
  `Definition` (they are already present, so an "append absent styles"
  generator would skip them). `tests/structure_harness.py` compares DOCX
  styles "in the regression direction only (removed = drift, added = fine)"
  (plan `:19`).

## 5. Verification and layout checks

### scripts/check_layout.py (588 lines)

- Docstring (`:2`): "Browser layout regression for the documentation site."
  Run as `python3 scripts/check_layout.py build/site` (`:27`); called only by
  `scripts/build_site.py:38,1297` (`check_layout.run(OUT)`). It is **not** in
  `src/press` and never runs on a book's reader site, HTML, or EPUB.
- `VIEWPORTS` (`:49-54`): desktop 1440x900, short-desktop 1265x697, tablet
  820x1180, narrow-mobile 390x844. `ZOOMS = (1, 2)` (`:60`).
  `DEFAULT_PAGES = ("index.html", "reference.html", "gallery.html")` (`:66`).
- Table geometry JS (`:306-320`) over `.prose table` (a docs-site selector):
  `stacked` (first body row computes `display: block`), `labelled`,
  `scrollW`/`clientW`, and `clippedCells` = cells with `scrollWidth >
  clientWidth + 1`.
- `_stacked_table_problems` (`:455-476`) judges **only stacked tables**:
  "A desktop table that keeps its columns may still scroll inside its own box,
  by design, so only stacked tables are judged here." It reports "still
  scrolls sideways" and "clips N cell(s)". Chrome is optional locally, required
  under `PRESS_REQUIRE_BROWSER_CHECK=1` (`run`, `:558-575`).

### verify_formats.py (608 lines)

- `verify_html` (`:325-336`): sentinels, `<html`, `require_witnesses`,
  `require_figure_labels` (`:315-322`). `verify_epub` (`:385`), `verify_docx`
  (`:469`), `verify_site` (`:542`), `main` (`:551-604`).
- Witnesses never come from a table row. `_manuscript_witness` (`:56-70`) and
  `chapter_witnesses` (`:78-98`) skip any line containing a character in
  the set of markup characters (asterisk, underscore, backtick, brackets, parentheses, angle brackets, quotes, ampersand, hash, bang, pipe), so a pipe-table row (and any line with a code span) is
  excluded. `verify_editions_agree` (`:141-174`) therefore compares chapter
  prose only; **no check compares table text across editions**, and nothing in
  verify_formats or verify_pages mentions `table`/`<td`.
- `verify_pages.py` (572 lines) checks refs, downloads, reading surface,
  commerce, metadata, sitemap; no table logic.

### Registering a verifier

- `registry.py` is the artifact graph only (`ARTIFACTS`, `:28-72`); it holds
  no verifiers. Format verification is wired in `__main__.verify_formats_built`
  (`:78-98`) calling `verify_formats.main`; the PDF via `verify_built`
  (`:70-75`) and `verify-print` (`:425-440`).
- Invariant ledger: `.celebrimbor/invariants.yaml`, entries with
  `enforced_by`, `negative_proof`, `owner`, `risk`, `statement`,
  `limitations` (e.g. `INV-format-witness`, `:533-547`); rendered to
  `docs/INVARIANTS.md` by `press selftest --write-docs`
  (`selftest.py:569-572`) and drift-checked (`selftest_release.py:431-442`).
- Producers: `.celebrimbor/producers.yaml` `producers:` maps each producer to
  `verifier` + `negative_fixture` (e.g. `build: verifier:
  verify_pdf:verify_mirrored_margins`); `pending:` entries carry `review_by`.
  Surfaces: `.celebrimbor/surfaces.yaml`, ratified with `celebrimbor ratify`.
- CONTRIBUTING.md:95-109: "**A producer is only proven by a verifier that
  rejects a broken artifact.**" and "**A verifier with no known-bad fixture is
  an untested claim.**" (Its text still names `quality/surfaces.yaml` and
  `PRODUCER_REJECTION_PROOFS`; the live ledger is `.celebrimbor/`.)
- Known-bad: `src/press/data/known-bad/*.md` are prose-lint fixtures with
  `expected.yaml` (checker + diagnostic substring); mirrored in
  `.celebrimbor/known-bad.expected.yaml`. No rendered-artifact fixtures live
  there; artifact negatives are pytest tests (e.g.
  `tests/test_verify_pdf_print_profile.py::test_a_missing_gutter_is_rejected`).

## 6. Design contract and versioning

- CLAUDE.md "The contract": "within a major, fixes may correct broken output
  but must not change typography or layout of a valid book; design and
  template changes require a new major. ... For a new major, also move the
  requirements pin in the template."
- `migrate.py:161-173` `DESIGN_NOTES` has entries for 2 and 3 only; the
  fallback (`:180-184`) is "design: see docs/MIGRATION.md for what v{to}
  changes". Round 1B Task 12 (`plan:361`) writes `DESIGN_NOTES[4]` as a
  non-PDF-only major: "the PDF is unchanged".
- `docs/MIGRATION.md` has one section per major ("What v2 → v3 actually
  changes", `:36-78`, with a requirements/workflow pin table at `:71-74`).
  Template pin: `src/press/data/template/requirements.txt:4`
  (`press @ git+https://github.com/clintecker/press@v3`).
- Round 1B structure: header (`:1-11`), "Findings" (`:13-20`), "Rulings"
  (`:22-29`), "Global Constraints" (`:31-42`), "Review Focus" (`:44-50`),
  Tasks 1-13 each with **Files**, Produces/Consumes, checkbox Steps; "Not in
  this round" (`:381-385`). Task 1 adds the plan file to `NOT_PUBLISHED` in
  `scripts/build_site.py`. **Global Constraint that conflicts with this
  spec** (`:34`): "within it, the existing v3 PDF/print output is **not**
  touched by this round. Any LaTeX branch change is out of scope." A sibling
  round that changes the PDF must amend the v4 migration note and
  `DESIGN_NOTES[4]`.
- Docs law (enforced part): `selftest_release.check_docs` (`:409-449`) checks
  routed targets against USAGE and README, and that `docs/REFERENCE.md`,
  `docs/INVARIANTS.md`, `docs/PROVIDER-QUALIFICATION.md` equal their
  renderers. REFERENCE.md is generated from the registry and CLI
  (`selftest.render_reference`, `:408`); a table feature with no new target
  or artifact does not change it. Feature docs are same-commit discipline,
  not mechanically checked.
- Which authoring doc would carry tables: none documents tables today. The
  Round 1B plan names `docs/ILLUSTRATIONS.md` (figures) and
  `docs/CONFIGURATION.md` (set-pieces) as the construct docs (`plan:35`).
  `docs/BOOK-PARTS.md:247-262` tells authors to write a glossary as "a
  Markdown definition list". Every `docs/*.md` must be published or listed in
  `NOT_PUBLISHED` (`scripts/build_site.py:129`, check at `:181-188`, glob is
  `docs/*.md`, non-recursive).

## 7. Test conventions

- Book factory: `tests/factories.py` `BookFactory` (`:66`) with
  `with_chapter(name, body)` (`:94`), `with_appendix` (`:98`),
  `with_sentinels` (`:102`), `with_reader_css` (`:126`), `with_extra_css`
  (`:130`), `with_aesthetic` (`:118`), `build(root) -> BookHandle` (`:163`);
  presets `minimal()` (`:258`), `full()` (`:272`), and others (`:299-346`).
  `BookHandle.use()` (`:50`) isolates BOOK_ROOT and caches.
- Real-tool runners: `tests/integration/_harness.py` (capability skip,
  evidence JSON) and families `test_pdf_family.py`, `test_web_family.py`,
  `test_epub_family.py`, `test_markdown_family.py`; e.g.
  `test_pdf_family.py:54-58` stacks `@requires_pdf_toolchain`,
  `@pytest.mark.layer("integration")`, `@pytest.mark.invariant("INV-pdf-ink")`,
  `@pytest.mark.proof("positive")`.
- Output assertions on markup: `test_figure_numbering_filter.py` asserts
  LaTeX substrings (`"\\textbf{Figure~1.1.}" in out`, `:61-64`) and HTML via
  `to="html"` (`:88-101`); `test_figure_placement.py:33` has its own
  `_render`. DOCX assertions are planned (`plan:98-99`, `_render_docx` returning
  `word/document.xml`); none exist yet.
- Ratchets a new module must satisfy: `scripts/verify.sh` (`:23-60`):
  pre-commit, `pytest --cov=press`, `celebrimbor gate` (surface, invariants,
  producers, known-bad, imports, impact, coverage, mutation), the Lua ratchet,
  the docs site build; `--full` adds `scripts/gauntlet.sh` (`:61-66`).
  Coverage floors: `.celebrimbor/baselines/coverage.yaml` (min 50,
  `celebrimbor.toml:53`). Mutation: `celebrimbor.toml:39`
  `mutation_survivors = "press.mutation:survivors"`, targets
  `mutation.py:63-68` (barcode, artifact_status, dropcaps, figures) and
  identity baseline `.celebrimbor/baselines/mutation.yaml`; a pure
  classifier module would be a candidate target. verify_formats is
  deliberately excluded (`mutation.py:55-62`).
