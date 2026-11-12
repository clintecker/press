# Shape-aware tables (Round 1C, v4): design

Date: 2026-11-12. Status: draft for the author's review. Research:
`docs/superpowers/research/2026-11-12-table-rendering-today.md` (cited below
as "research, section N").

## 1. The problem, measured

Every table in a press book is rendered the same way in every edition: a
pandoc table, with no house rule for it anywhere (research 2, 3). Measured on
the published reader site of *Publishing with Press* (116 tables, 1,598 body
cells) with headless Chrome:

| Symptom | 1280 px | 820 px | 390 px |
|---|---|---|---|
| Code identifier split inside the token (`--foil-` / `bright`) | 51 cells, 31 tables | 34, 26 | 135, 51 |
| Multi-word command wrapped across lines | 51 cells, 27 tables | 33, 21 | 110, 37 |
| Prose at one or two words per line for three lines or more | 51 cells, 28 tables | 31, 15 | 163, 66 |
| Cells of five lines or more | 37 cells, 26 tables | 18, 14 | 310, 98 |
| Pages that scroll sideways | 0 | 0 | 13 |

The PDF shares the fault in a different form: a short-source pipe table gets
`ll` columns that never wrap and can run past the text block, and a
three-column table with a prose column (Table 16.1) crushes it into a third
of the measure (research 2).

The shape count decides the design. Of the 116 tables, 106 are a key column
plus exactly one prose column (77 two-column, 29 three-column) and 10 are
grids with no prose column. The median table has five rows and the longest
has sixteen.

## 2. The principle

Render a table by what it is, not by how it was typed. A key-plus-prose
table is a reference list, and a reference list reads best as a ledger
entry, the manpage form: the key on its own line, the description at full
measure beneath it. That form has no column to squish, so it reads the same
at 390 px, in a 6 by 9 print measure, in Word, and in an EPUB reader, and it
is the native idiom of the late-1990s manual the house imitates. A grid
stays a grid, because its point is scanning across rows, and gets the fixes
that make a grid honest.

This is a design change to valid books in every edition, so it is v4 work,
a sibling of Round 1B (edition parity). It amends Round 1B's constraint that
the PDF is untouched by v4 (research 6).

## 3. Classification

A new Lua filter, `table-shapes.lua`, runs after `typographic-spacing` and
before `figure-numbering` in every defaults file that renders tables (pdf,
print, epub, html, chunked, portable; research 1). For each `Table`:

1. **Explicit class wins.** A table inside a fenced div with class `ledger`
   or `grid` takes that form. (Pipe tables carry no attributes of their own
   in pandoc 3.1.3, and the house already uses fenced divs for `tip`,
   `warning`, `sidebar`.)
2. **Otherwise, by shape.** Count columns and, for each column, the mean
   word count of its body cells (a code span counts as one word). The table
   is a **reference list** when it has two or three columns and exactly one
   column has a mean of eight words or more, and that column is the last
   one. Everything else is a **grid**: one column, four or more columns, no
   prose column, two prose columns, or the prose column not last.
3. **Header rows** are required for the legend (section 4.1) but not for
   classification. A table with no header row is classified the same way.

The classifier is a pure function in `press-util.lua` (`table_shape(cols,
mean_words) -> "ledger" | "grid"`), unit-tested under plain Lua like the
other helpers (research 1, Lua conventions), so the threshold has one home.

## 4. Rendering

### 4.1 Reference lists become ledgers

The filter rewrites the `Table` to a `Div` with class `ledger` that holds:

- the caption, if any, as a `Para` with class `ledger-caption` (the house
  prints table captions above the table, small italic, no label; the ledger
  keeps that);
- a **legend** line when the header row is non-empty: the header cells
  joined with a middle dot, as a `Para` with class `ledger-legend`, small
  caps in the PDF and reader, so "Skill · Meaning" names the columns once;
- a native `DefinitionList`: for each body row, the term is the first
  cell's inlines; the definition is one or two blocks: for a three-column
  table, the middle cell as a `Para` with class `ledger-sub` (constant width
  if it was, since inline formatting is kept), then the last cell's blocks.

Because the output is a native `DefinitionList`, every pandoc writer renders
it without a per-writer branch: `description` in LaTeX, `<dl>` in HTML and
EPUB, `DefinitionTerm`/`Definition` paragraphs in DOCX, an indented list in
plain text. Only the styling is per edition:

- **PDF.** `book-header.tex` gains `\setlist[description]` through
  `enumitem` and a `PressLedger` environment the filter wraps around the
  list as `RawBlock` for the latex writer: hanging indent of 1.6 em, the
  term set on its own line with `\needspace{3\baselineskip}` before it so a
  term never strands at a page foot (this also discharges the description
  half of issue #286), 0.45 baseline between entries, no rules. The legend
  is `\textsc` small. The caption keeps the house caption setup.
- **Reader site and single-leaf HTML.** `reader.css` and `book.css` gain a
  `.ledger` block: `dt` in the body face at full weight, `dd` indented 1.6
  rem with `margin-bottom: .55em`, `.ledger-sub` in constant width, a
  hairline above each `dt` after the first. The existing phone card rules
  are untouched (they apply only to tables).
- **EPUB.** `epub.css` gains the same `.ledger` block; it has no table or
  list styling today (research 3).
- **DOCX.** In this round Word gets the native definition list in
  pandoc's `DefinitionTerm` and `Definition` paragraph styles, which are
  already hanging entries. The house styles (`LedgerTerm`, `LedgerSub`,
  `LedgerDesc`) land with Round 1B Task 5's generated reference document,
  where they join `HOUSE_STYLES` and the filter adds `custom-style` Divs
  for the docx writer (research 4).
- **Plain text and Markdown.** Unchanged pandoc output for a definition
  list; the Markdown edition is the stitched source and keeps the pipe
  table.

### 4.2 Grids stay grids, honestly

For a grid the filter keeps the `Table` and:

- **PDF.** Sets explicit relative column widths from the measured mean
  cell length (so pandoc emits `p{}` columns and every cell wraps; research
  2 shows `ll` columns never wrap), and wraps the table in a `RawBlock`
  pair that sets `\small`, `\tabcolsep` of 0.5 em, and
  `\needspace{4\baselineskip}` before the head (the table half of #286).
  Inside a grid, `\texttt` text is set with `\nohyphens` so an identifier is
  never split; a column too narrow for its longest token widens, the prose
  column gives way, and the table never exceeds `\columnwidth`.
- **HTML, reader, EPUB.** Wraps the table in a `Div` with class `grid`.
  CSS: `.grid { overflow-x: auto }` so a grid wider than the measure scrolls
  inside its own box like a code block, `td code { white-space: nowrap }`,
  table face at `.9em`, `th` in small caps. The phone card layout stays for
  grids with a header row, and `webmeta.label_table_cells` is fixed to
  match `<tr class="odd">` rows (issue #283), with a fixture row in its
  tests, so the cards fire in a CI-built book.
- **DOCX.** Unchanged pandoc table (the `Table` style), with the same
  explicit column widths, which Word honours.

### 4.3 What does not change

Table numbering stays authored text ("Table 9.1." typed into the caption),
there is still no List of Tables, and `@tbl:` references are not resolved.
Those are a separate feature. Captions keep their place above.

## 5. Verification

A producer is only proven by a verifier that rejects a broken artifact
(CONTRIBUTING). Three checks, each with a negative fixture:

1. **Filter contract** (`tests/test_table_shapes_filter.py`, pandoc
   through `_render`): a key-plus-prose fixture renders as a definition
   list in latex, html, and docx output, with legend and caption; a grid
   fixture stays a table with `p{}` columns in latex and a `grid` wrapper
   in html; a `::: {.grid}` wrapper forces a table; a `::: {.ledger}`
   wrapper forces a list; a document with no tables is byte-identical
   filtered and unfiltered (the house idiom). The filter gets a coverage
   floor in `.celebrimbor/baselines/lua-coverage.yaml` and its test file
   joins the list in `scripts/verify.sh`.
2. **Rendered editions** (`verify_formats.verify_tables`, run inside
   `verify_html`, `verify_epub`, and `verify_site`): every `<table>` in the
   output sits inside a `.grid` wrapper and, when it has a header row, every
   body cell carries `data-label`; every `<dl class="ledger">` has at least
   one `dt`; no `<table>` appears outside a wrapper. Registered in
   `.celebrimbor/invariants.yaml` as `INV-table-shape` with the negative
   proof a test that feeds an unwrapped table and a labelless row.
3. **PDF text block** (`verify_pdf.verify_text_block`): render each page
   and fail when ink lies more than 2 pt outside the text block that the
   profile geometry declares, excluding the running head and folio bands.
   This catches a table, or anything else, that overruns the measure, which
   the current 2 px paper-edge sample cannot (research 2). Negative proof: a
   fixture book with a `::: {.grid}` table whose one cell is a 60-character
   identifier.

A fourth check is a maintainer's script, not a target:
`scripts/measure_tables.py` runs the headless-Chrome measurement from this
research (clipped cells, in-token code breaks, pages scrolling sideways)
over a built reader site at 1280, 820, and 390 px, the way
`scripts/check_layout.py` serves the docs site. A `press verify-layout`
target can follow once the measurement has proved stable.

## 6. Documentation and contract

- New `docs/TABLES.md`: pipe tables, the two shapes and how press decides,
  the `ledger` and `grid` overrides, what each edition renders, the
  verifiers. `docs/BOOK-PARTS.md` points to it from the glossary advice.
- `docs/MIGRATION.md` "What v3 → v4 actually changes" and
  `migrate.py` `DESIGN_NOTES[4]` gain the tables paragraph and drop the
  claim that the PDF is unchanged. Round 1B's plan gets a note that Round
  1C amends its PDF constraint.
- `CHANGELOG.md` Unreleased: the feature, #283, the description and
  longtable halves of #286.
- The spec and plan live under `docs/superpowers/`, which the docs-site
  glob does not publish (research 6).

## 7. Acceptance

Measured on *Publishing with Press* rebuilt under the branch:

- Reader site at 1280, 820, and 390 px: zero in-token code splits, zero
  clipped cells, zero pages scrolling sideways; the 106 reference lists
  render as ledgers, the 10 grids as wrapped tables.
- PDF: `verify_text_block` passes; Table 16.1 reads as a ledger; the page
  count change is recorded in the book's ledger.
- EPUB passes epubcheck with the new stylesheet.
- A book with no tables renders byte-identically in every edition apart
  from the stylesheet bytes the editions carry.

## 8. Not in this round

Table numbering and `@tbl:` references; a List of Tables; the `[H]` figure
placement defect (#290) and the Contents strand (#291), which are their own
issues; any change to the Markdown edition.
