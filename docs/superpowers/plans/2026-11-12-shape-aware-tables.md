# Shape-aware tables (Round 1C, v4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render every Markdown table by its shape in every edition: a key-plus-prose table becomes a ledger (a styled definition list), a grid stays a table that wraps, never splits an identifier, and scrolls or stacks on the Web, with verifiers that reject the broken forms.

**Architecture:** One new Lua filter, `table-shapes.lua`, classifies each `Table` with a pure helper in `press-util.lua` and rewrites it to a native `DefinitionList` inside a `Div.ledger` (so every pandoc writer renders it) or wraps it in a `Div.grid` with explicit column widths. Styling is per edition: a `PressLedger` environment and grid macros in the TeX header, `.ledger`/`.grid` rules in the three stylesheets. Two verifiers prove the output: `verify_formats.verify_tables` on the HTML surfaces and `verify_pdf.verify_text_block` on rendered pages.

**Tech Stack:** pandoc 3.1.3 Lua filters (pandoc Lua 5.4), LuaLaTeX with enumitem, longtable, booktabs and needspace (already loaded), CSS, Python 3.12 (pypdf, Pillow via the existing verify_pdf imports), pytest with the repo's `lua_coverage` harness.

**Spec:** `docs/superpowers/specs/2026-11-12-shape-aware-tables-design.md`

## Global Constraints

- Branch: `v4/round-1c-shape-aware-tables` off `main`. This is v4 design work and changes the PDF; it amends Round 1B's "PDF untouched" constraint (spec 2, 6).
- Classification (spec 3): explicit `::: {.ledger}` / `::: {.grid}` wrapper wins; otherwise a table with two or three columns, exactly one column with mean body-cell word count >= 8, that column last, is a ledger; everything else is a grid. A code span counts as one word.
- A document with no tables renders byte-identically filtered and unfiltered, in every writer (spec 5.1, 7).
- Ledger output is a native `DefinitionList` in a `Div` with class `ledger`; caption `Para.ledger-caption`; legend `Para.ledger-legend` (header cells joined with " · "); three-column middle cell as `Para.ledger-sub` first in the definition (spec 4.1).
- PDF ledger: hanging indent 1.6 em, `\needspace{3\baselineskip}` before each term, 0.45 baseline between entries, no rules, legend in `\textsc` small (spec 4.1).
- PDF grid: relative `p{}` widths from mean cell length, `\small`, `\tabcolsep` 0.5 em, `\needspace{4\baselineskip}` before the head, `\texttt` unhyphenated inside the grid, never wider than `\columnwidth` (spec 4.2).
- Web grid: `.grid { overflow-x: auto }`, `td code { white-space: nowrap }`, table face `.9em`, `th` small caps; the phone card rules unchanged (spec 4.2).
- DOCX in this round: the native definition list with pandoc's `DefinitionTerm`/`Definition` styles; the house `LedgerTerm`/`LedgerSub`/`LedgerDesc` styles land with Round 1B Task 5's reference document (spec 4.1, amended).
- Table numbering, `@tbl:`, List of Tables: out of scope (spec 4.3).
- House law: every `*.lua` compiles, passes `scripts/lua-lint.sh`, has a floor in `.celebrimbor/baselines/lua-coverage.yaml` set with `update --from-report` from a CI report, never from macOS; its test file is in the `scripts/verify.sh` list. Docs change in the same commit as the surface. Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. A table whose header row is empty or absent (`|---|---|` only, or a pandoc simple table) must still classify and render; the legend is omitted, nothing crashes. Test in Task 2.
2. A ledger whose key cell is empty (a continuation row an author used for a second description paragraph) must not emit an empty `dt`; the definition joins the previous entry. Test in Task 2.
3. A grid cell holding a 60-character identifier must wrap the column wider rather than overrun the measure in the PDF, and must scroll rather than overflow the paper on the Web. Tests in Tasks 3 and 6.
4. A table inside a sidebar, tip, or warning div (the house admonitions) must keep working: the filter walks nested blocks, and the ledger inherits the admonition's frame. Test in Task 2.
5. The reader site's phone cards must fire in a CI-built book, which needs `label_table_cells` to match `<tr class="odd">` (issue #283, fixed in the v3 wave). Task 4 asserts it on the branch and carries the fix if the merge base lacks it.

---

### Task 1: The pure classifier in press-util.lua

**Files:**
- Modify: `src/press/data/lua/press-util.lua` (append after `tail_web_size`)
- Test: `tests/lua/test_press_util.lua` (append)

**Interfaces:**
- Produces: `util.word_count(text) -> integer` (whitespace-separated tokens); `util.table_shape(ncols, means) -> "ledger" | "grid"` where `means` is a list of per-column mean word counts in column order; `util.LEDGER_PROSE_WORDS = 8`.

- [ ] **Step 1: Write the failing tests** (append to `tests/lua/test_press_util.lua`, using its `eq`)

```lua
eq(util.word_count("press all"), 2, "word_count two")
eq(util.word_count("  one   "), 1, "word_count trims")
eq(util.word_count(""), 0, "word_count empty")
eq(util.table_shape(2, {1.5, 12.0}), "ledger", "shape 2-col key+prose")
eq(util.table_shape(3, {1.0, 2.5, 9.0}), "ledger", "shape 3-col key+sub+prose")
eq(util.table_shape(3, {1.0, 9.0, 2.0}), "grid", "shape prose not last")
eq(util.table_shape(2, {1.0, 7.9}), "grid", "shape below threshold")
eq(util.table_shape(4, {1.0, 1.0, 1.0, 20.0}), "grid", "shape four columns")
eq(util.table_shape(3, {9.0, 1.0, 9.0}), "grid", "shape two prose columns")
eq(util.table_shape(1, {30.0}), "grid", "shape one column")
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_press_util_lua.py -q`
Expected: FAIL, "attempt to call a nil value (field 'word_count')".

- [ ] **Step 3: Implement** `word_count`, `LEDGER_PROSE_WORDS`, and `table_shape` in `press-util.lua`, exported on the module table like the existing helpers. `table_shape` returns `"ledger"` only when `ncols` is 2 or 3, exactly one entry of `means` is `>= LEDGER_PROSE_WORDS`, and that entry is the last.

- [ ] **Step 4: Run to verify they pass**

Run: `python3 -m pytest tests/test_press_util_lua.py -q && scripts/lua-lint.sh`
Expected: PASS, lint clean.

- [ ] **Step 5: Commit**

```bash
git add src/press/data/lua/press-util.lua tests/lua/test_press_util.lua
git commit -m "press-util: table_shape and word_count, the shape classifier for tables"
```

### Task 2: The table-shapes.lua filter

**Files:**
- Create: `src/press/data/lua/table-shapes.lua`
- Modify: `src/press/data/defaults/{pdf,print,epub,html,chunked,portable}.yaml` (insert `"@press/lua/table-shapes.lua"` after `typographic-spacing.lua`)
- Modify: `scripts/verify.sh:48-50` (add `tests/test_table_shapes_filter.py`)
- Modify: `.celebrimbor/baselines/lua-coverage.yaml` (floor for `table-shapes.lua`, see Step 7)
- Test: `tests/test_table_shapes_filter.py`

**Interfaces:**
- Consumes: `util.word_count`, `util.table_shape` from Task 1.
- Produces, for later tasks to style and verify: ledger markup `Div{class=ledger}[Para.ledger-caption?, Para.ledger-legend?, DefinitionList]`, with latex `RawBlock` `\begin{PressLedger}` / `\end{PressLedger}` around the list; grid markup `Div{class=grid}[Table]` with every `ColSpec` width set (relative widths summing to 1.0, each column's share = max(0.12, its mean cell character length share)), and for latex `RawBlock` `\PressGridBegin` before and `\PressGridEnd` after the table. In HTML the Div renders as `<div class="ledger">` / `<div class="grid">`.

- [ ] **Step 1: Write the failing tests** in `tests/test_table_shapes_filter.py`, copying the `_render` helper from `tests/test_figure_numbering_filter.py:30-44` with `FILTER` pointing at `table-shapes.lua`, `pytestmark = lua_coverage.needs_pandoc`, and the `layer("integration")` / `proof(...)` marks the sibling tests use. Fixtures:

```python
LEDGER = (
    "# Ch\n\n| Skill | Meaning |\n|---|---|\n"
    "| `hemingway` | It asks for concrete detail, compression, omission, and restraint without imitation. |\n"
    "| `humanizer` | It drafts, revises, and audits prose so that it reads as one writer's deliberate choices. |\n\n"
    "Table: Table 15.5. The skills that come with press\n"
)
LEDGER3 = LEDGER.replace("| Skill | Meaning |\n|---|---|", "| Area | Modules | Meaning |\n|---|---|---|").replace(
    "| `hemingway` |", "| Build | `build.py`, `figures.py` |").replace("| `humanizer` |", "| Verifiers | `verify_pdf.py` |")
GRID = "# Ch\n\n| Profile | Trim | Margin |\n|---|---|---|\n| house | 6 x 9 | 0.78in |\n| pocket | 5 x 8 | 0.6in |\n"
NO_HEAD = "# Ch\n\n|---|---|\n| `a` | one two three four five six seven eight nine ten |\n"
CONTINUATION = LEDGER.replace("| `humanizer` |", "| |")
NESTED = "# Ch\n\n::: {.tip}\n" + LEDGER.split("\n\n", 1)[1] + ":::\n"
```

Tests (names and the assertion each makes):

```python
def test_a_key_plus_prose_table_becomes_a_ledger_in_latex():
    out = _render(LEDGER)
    assert "\\begin{PressLedger}" in out and "\\begin{description}" in out
    assert "\\item[\\texttt{hemingway}]" in out and "longtable" not in out
def test_a_ledger_keeps_its_caption_and_legend():
    out = _render(LEDGER, to="html")
    assert '<div class="ledger">' in out and 'class="ledger-caption"' in out
    assert "Skill · Meaning" in out and "<dl>" in out and "<dt>" in out
def test_a_three_column_ledger_sets_the_middle_cell_as_sub():
    out = _render(LEDGER3, to="html")
    assert '<p class="ledger-sub"><code>build.py</code>, <code>figures.py</code></p>' in out
def test_a_grid_stays_a_table_with_relative_widths():
    out = _render(GRID)
    assert "\\PressGridBegin" in out and "longtable" in out and "\\real{" in out and "\\PressGridEnd" in out
def test_a_grid_is_wrapped_on_the_web():
    out = _render(GRID, to="html")
    assert '<div class="grid">' in out and "<table" in out
def test_a_grid_wrapper_forces_a_table():
    out = _render("# Ch\n\n::: {.grid}\n" + LEDGER.split("\n\n", 1)[1] + ":::\n", to="html")
    assert "<table" in out and 'class="ledger"' not in out
def test_a_ledger_wrapper_forces_a_list():
    out = _render("# Ch\n\n::: {.ledger}\n" + GRID.split("\n\n", 1)[1] + ":::\n", to="html")
    assert "<dl>" in out and "<table" not in out
def test_a_table_with_no_header_row_classifies_without_a_legend():
    out = _render(NO_HEAD, to="html")
    assert "<dl>" in out and "ledger-legend" not in out
def test_an_empty_key_cell_continues_the_previous_entry():
    out = _render(CONTINUATION, to="html")
    assert out.count("<dt>") == 1 and out.count("<dd>") == 1
def test_a_table_inside_an_admonition_is_still_rewritten():
    assert '<div class="ledger">' in _render(NESTED, to="html")
def test_a_document_with_no_tables_is_byte_identical():
    doc = "# Ch\n\nProse only.\n\n- a list\n"
    for fmt in ("latex", "html", "docx", "plain"):
        assert _render(doc, to=fmt, filtered=False) == _render(doc, to=fmt)
def test_docx_gets_a_definition_list():
    out = _render(LEDGER, to="native")
    assert "DefinitionList" in out
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_table_shapes_filter.py -q`
Expected: FAIL at the filter path (file missing).

- [ ] **Step 3: Implement `table-shapes.lua`.** Structure, matching the siblings: load `press-util` via the `PANDOC_SCRIPT_FILE` idiom; `local latex = FORMAT:match("latex") ~= nil`; a `Div` handler that records a forced shape from classes `ledger`/`grid` and walks its content; a `Table` handler that computes per-column means with `util.word_count(pandoc.utils.stringify(cell))` (a `Code` inline counts once because stringify yields its text as one token when it has no spaces; wrap `Code` text in a placeholder before counting so `press all` counts one), calls `util.table_shape`, and dispatches to `to_ledger(tbl, forced)` or `to_grid(tbl)`. `to_ledger` builds the `DefinitionList` items `{term_inlines, {blocks}}`, prepends `Para{Str..., attr=ledger-sub}` (as a `Div` with class `ledger-sub` around the Para, since `Para` carries no attributes) for the middle column, merges a row whose first cell stringifies to "" into the previous item, emits caption and legend Paras inside `Div`s of those classes, and wraps the list in latex RawBlocks. `to_grid` sets each `ColSpec` to `{align, share}` and wraps in `Div.grid` plus the latex RawBlocks. Return `{ {Div = ..., Table = ...} }` with `traverse = "topdown"` so a forcing Div sees its table.

- [ ] **Step 4: Register the filter** in the six defaults files after `typographic-spacing.lua`, and add the test file to the `scripts/verify.sh` pytest list.

- [ ] **Step 5: Run to verify they pass**

Run: `python3 -m pytest tests/test_table_shapes_filter.py tests/test_lua_compiles.py -q && scripts/lua-lint.sh`
Expected: PASS, lint clean.

- [ ] **Step 6: Run the sibling filter suites** to prove nothing else moved: `python3 -m pytest tests/test_figure_numbering_filter.py tests/test_set_pieces.py tests/test_dropcaps_filter.py -q`. Expected: PASS.

- [ ] **Step 7: Coverage floor.** Measure locally only to confirm the harness sees the filter: `PRESS_LUA_COV_DIR=$(mktemp -d) python3 -m pytest tests/test_table_shapes_filter.py -q && python3 scripts/lua_coverage_ratchet.py report --cov-dir <dir>`. Add `table-shapes.lua: 80.0` to the baseline as a provisional floor with a `reasons` line "provisional floor for the new filter; raise from the first CI report with update --from-report", so `check` does not fail on a missing floor. (The CI number replaces it before release.)

- [ ] **Step 8: Commit**

```bash
git add src/press/data/lua/table-shapes.lua src/press/data/defaults/*.yaml scripts/verify.sh .celebrimbor/baselines/lua-coverage.yaml tests/test_table_shapes_filter.py
git commit -m "table-shapes.lua: a key-plus-prose table becomes a ledger, a grid keeps its columns and wraps"
```

### Task 3: The PDF: PressLedger and grid macros in the TeX header

**Files:**
- Modify: `src/press/data/tex/book-header.tex` (after the `\setlist` lines at 72-73, and a grid block after the mdframed `quote` at 232)
- Test: `tests/integration/test_pdf_family.py` (append two tests behind `@requires_pdf_toolchain`)

**Interfaces:**
- Consumes: `\begin{PressLedger}`, `\PressGridBegin`, `\PressGridEnd` emitted by Task 2.
- Produces: the three macros. `PressLedger` is an environment that sets `\setlist[description]{style=nextline, leftmargin=1.6em, labelindent=0pt, itemsep=0.45\baselineskip, parsep=0pt, topsep=0.5\baselineskip, font=\normalfont, before=\PressLedgerNeedspace}` where `\PressLedgerNeedspace` makes every `\item` run `\Needspace{3\baselineskip}` first (use `\let\PressLedgerItem\item` and redefine `\item` inside the environment). `\PressGridBegin` is `\begingroup\small\setlength{\tabcolsep}{0.5em}\Needspace{4\baselineskip}\PressNoHyphenTT` and `\PressGridEnd` is `\endgroup`, where `\PressNoHyphenTT` redefines `\texttt` for the group to `\texttt{\nohyphens{#1}}` (the `hyphenat` package provides `\nohyphens`; add `\usepackage{hyphenat}` beside the existing packages if absent, otherwise use `\hyphenpenalty=10000\exhyphenpenalty=10000` inside the group).

- [ ] **Step 1: Write the failing tests** in `tests/integration/test_pdf_family.py`, using the family's book factory and the same decorators as `test_pdf_family.py:54-58`:

```python
def test_a_ledger_table_sets_in_the_pdf_without_a_longtable(tmp_path):
    # a minimal book with LEDGER (from tests/test_table_shapes_filter.py) in one chapter
    # build press pdf; read build/pdf tex or the .tex pandoc wrote; assert "PressLedger" in tex and "longtable" not in tex; the PDF text (pdftotext) contains "hemingway"
def test_a_grid_with_a_long_identifier_stays_inside_the_measure(tmp_path):
    # a grid whose one cell is "a-very-long-identifier-that-cannot-break-at-all-anywhere-in-sixty-chars"
    # build; render page; assert verify_pdf.ink_bbox(page) right edge <= text block right edge + 2 px (reuse Task 6's helper once it exists; until then compute from the page: ink right <= 0.90 * page width)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/integration/test_pdf_family.py -k "ledger or long_identifier" -q`
Expected: FAIL (undefined control sequence `PressLedger`).

- [ ] **Step 3: Implement the header block** as the Interfaces block states, with a comment in the house voice explaining why (the research note's finding that pandoc's `ll` columns never wrap, and the manpage form).

- [ ] **Step 4: Run to verify they pass**

Run: the same pytest command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/press/data/tex/book-header.tex tests/integration/test_pdf_family.py
git commit -m "TeX header: PressLedger hanging entries and honest grids (small, wrapped, unhyphenated code)"
```

### Task 4: The Web: ledger and grid styles, and the phone cards that fire

**Files:**
- Modify: `src/press/data/web/reader.css` (new section before "/* 12. Tables, on a narrow screen only" and renumber that comment to 13; fix the duplicate "12")
- Modify: `src/press/data/tex/book.css` (same rules, in its idiom, before its phone block at 71)
- Modify: `src/press/data/tex/epub.css` (append `.ledger` and `.grid` rules; no colour)
- Modify: `src/press/webmeta.py:251` (row regex `<tr\b[^>]*>.*?</tr>`) only if the branch's merge base still has the bare `<tr>` form
- Test: `tests/test_webmeta.py` (append), `tests/test_reader_css.py` or the nearest stylesheet test (grep for `reader.css` under tests/ and append there)

**Interfaces:**
- Consumes: `.ledger`, `.ledger-caption`, `.ledger-legend`, `.ledger-sub`, `.grid` from Task 2.
- Produces: CSS only.

- [ ] **Step 1: Write the failing tests**

```python
def test_rows_with_a_class_are_labelled_too():   # tests/test_webmeta.py
    out = webmeta.label_table_cells(_headed('<tr class="odd"><td>Detect</td><td>turns RF into audio</td></tr>'))
    assert '<td data-label="Stage">Detect</td>' in out
def test_the_reader_stylesheet_styles_ledgers_and_grids():  # stylesheet test
    css = (DATA / "web" / "reader.css").read_text()
    for rule in (".ledger dt", ".ledger dd", ".ledger-sub", ".grid { overflow-x: auto", "td code { white-space: nowrap"):
        assert rule in css
    assert css.count("/* 12.") == 1
def test_book_and_epub_stylesheets_carry_the_same_classes():
    for name in ("tex/book.css", "tex/epub.css"):
        css = (DATA / name).read_text(); assert ".ledger" in css and ".grid" in css
```

- [ ] **Step 2: Run to verify they fail.** `python3 -m pytest tests/test_webmeta.py <stylesheet test file> -q`. Expected: FAIL.

- [ ] **Step 3: Implement the CSS.** reader.css: `.ledger { margin: 1.4em 0; } .ledger-caption { font-style: italic; font-size: .9em; text-align: center; margin: 0 0 .6em; } .ledger-legend { font-variant: small-caps; letter-spacing: .04em; color: var(--ink-soft); font-size: .85em; margin: 0 0 .4em; } .ledger dt { font-weight: 600; margin-top: .55em; padding-top: .45em; border-top: 1px solid var(--hairline); } .ledger dt:first-of-type { border-top: 0; margin-top: 0; padding-top: 0; } .ledger dd { margin: .15em 0 0 1.6rem; } .ledger-sub { font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; font-size: .85em; margin: 0 0 .2em; } .grid { overflow-x: auto; margin: 1.4em 0; } .grid table { font-size: .9em; border-collapse: collapse; } .grid th { font-variant: small-caps; letter-spacing: .04em; text-align: left; } .grid td code, .grid th code { white-space: nowrap; }`. book.css the same with its own variables; epub.css the same without colour or font-family beyond `monospace`. Fix the `#283` regex if present.

- [ ] **Step 4: Run to verify they pass**, then the full web family: `python3 -m pytest tests/test_webmeta.py tests/integration/test_web_family.py -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/press/data/web/reader.css src/press/data/tex/book.css src/press/data/tex/epub.css src/press/webmeta.py tests/
git commit -m "Reader, HTML, EPUB: ledger entries and honest grids; phone cards fire on classed rows"
```

### Task 5: verify_formats.verify_tables and its invariant

**Files:**
- Modify: `src/press/verify_formats.py` (new `verify_tables(markup: str, label: str) -> None` beside `require_figure_labels`; call it from `verify_html`, inside `verify_epub` for each XHTML member, and in `verify_site` for each chapter page)
- Modify: `.celebrimbor/invariants.yaml` (new `INV-table-shape`), `.celebrimbor/producers.yaml` (producer `build` gains a second verifier line or a new producer `tables` mapping to `verify_formats:verify_tables` with the negative fixture below), `docs/INVARIANTS.md` via `press selftest --write-docs`
- Test: `tests/test_verify_formats.py` (append)

**Interfaces:**
- Consumes: the markup classes from Task 2 and `data-label` from Task 4.
- Produces: `verify_tables(markup, label)` raising `SystemExit(f"{label}: table outside a grid wrapper")`, `SystemExit(f"{label}: grid row without data-label")` (only for tables with a `<thead>`), `SystemExit(f"{label}: ledger without an entry")`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.proof("negative")
def test_an_unwrapped_table_is_refused():
    with pytest.raises(SystemExit, match="outside a grid wrapper"):
        verify_formats.verify_tables("<table><tbody><tr><td>x</td></tr></tbody></table>", "HTML")
@pytest.mark.proof("negative")
def test_a_headed_grid_row_without_labels_is_refused():
    html = '<div class="grid"><table><thead><tr><th>A</th></tr></thead><tbody><tr class="odd"><td>x</td></tr></tbody></table></div>'
    with pytest.raises(SystemExit, match="without data-label"):
        verify_formats.verify_tables(html, "HTML")
@pytest.mark.proof("negative")
def test_an_empty_ledger_is_refused():
    with pytest.raises(SystemExit, match="without an entry"):
        verify_formats.verify_tables('<div class="ledger"><dl></dl></div>', "HTML")
@pytest.mark.proof("positive")
def test_a_wrapped_labelled_grid_and_a_ledger_pass():
    html = ('<div class="grid"><table><thead><tr><th>A</th></tr></thead><tbody><tr class="odd"><td data-label="A">x</td></tr></tbody></table></div>'
            '<div class="ledger"><dl><dt>k</dt><dd>v</dd></dl></div>')
    verify_formats.verify_tables(html, "HTML")
```

- [ ] **Step 2: Run to verify they fail.** `python3 -m pytest tests/test_verify_formats.py -k table -q`. Expected: FAIL, no attribute `verify_tables`.

- [ ] **Step 3: Implement** with `re` in the module's existing style, wire the three call sites, add the ledger entries (statement: "Every table in an HTML surface is a wrapped grid with labelled cells or a ledger with entries; a bare table is refused"; `enforced_by: verify_formats:verify_tables`; `negative_proof: tests/test_verify_formats.py::test_an_unwrapped_table_is_refused`; `owner: verify_formats`; `risk: A table renders in the one form that crushes on a phone and nothing notices`), and regenerate `docs/INVARIANTS.md`.

- [ ] **Step 4: Run to verify they pass**, then `celebrimbor gate` (through `scripts/verify.sh` without `--full`). Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/press/verify_formats.py .celebrimbor/invariants.yaml .celebrimbor/producers.yaml docs/INVARIANTS.md tests/test_verify_formats.py
git commit -m "verify_formats: every HTML table is a labelled grid or a ledger (INV-table-shape)"
```

### Task 6: verify_pdf.verify_text_block

**Files:**
- Modify: `src/press/verify_pdf.py` (new `text_block_right(images) -> int` and `verify_text_block(images, profile) -> None` beside `verify_mirrored_margins`; call from `main` after `verify_page_ink`)
- Modify: `.celebrimbor/producers.yaml` (producer `build` gains `verify_pdf:verify_text_block` with the negative fixture), `docs/INVARIANTS.md` if an invariant is added (`INV-pdf-text-block`)
- Test: `tests/test_verify_pdf_print_profile.py` (append, same style as `test_a_missing_gutter_is_rejected`)

**Interfaces:**
- Produces: `text_block_right(images)`: for body pages (the same page set `verify_mirrored_margins` uses), take each page's `ink_bbox` right edge, per parity when the profile is print; return the median per parity. `verify_text_block(images, profile)`: a page whose ink right edge exceeds its parity's median by more than 6 px at the render resolution raises `SystemExit(f"{profile} profile: page {n} runs {d} px past the text block")`. The running-head and folio bands are excluded by cropping the top and bottom 8 percent before `ink_bbox`.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_page_overrunning_the_measure_is_rejected(tmp_path):
    # synthesise 12 page images: 11 with ink to x=380, one with ink to x=410 (PIL), same size as render_pages produces
    with pytest.raises(SystemExit, match="runs .* px past the text block"):
        verify_pdf.verify_text_block(images, "print")
def test_pages_within_the_measure_pass(tmp_path):
    verify_pdf.verify_text_block(images_all_380, "print")
```

- [ ] **Step 2: Run to verify they fail.** Expected: FAIL, no attribute.
- [ ] **Step 3: Implement** as the Interfaces block states; wire into `main`; add the producer line and, if the team's ledger convention wants it, `INV-pdf-text-block` mirroring Task 5's entry shape.
- [ ] **Step 4: Run** `python3 -m pytest tests/test_verify_pdf_print_profile.py -q` and then a real build of the Alice example (`scripts/dev-render.sh`) to confirm the check passes on a valid book. Expected: PASS both.
- [ ] **Step 5: Commit**

```bash
git add src/press/verify_pdf.py .celebrimbor/producers.yaml .celebrimbor/invariants.yaml docs/INVARIANTS.md tests/test_verify_pdf_print_profile.py
git commit -m "verify_pdf: a page whose ink runs past the text block is refused"
```

### Task 7: Documentation and the v4 contract

**Files:**
- Create: `docs/TABLES.md`
- Modify: `docs/BOOK-PARTS.md:247-262` (glossary advice points to TABLES.md), `docs/MIGRATION.md` (a "What v3 → v4 actually changes" section if absent, with a Tables paragraph; if Round 1B has written it, add the paragraph and remove "the PDF is unchanged"), `src/press/migrate.py:161-173` (`DESIGN_NOTES[4]` naming tables and the PDF), `CHANGELOG.md` [Unreleased], `docs/ROUND-1B-EDITION-PARITY-V4-PLAN.md:34` (a one-line note that Round 1C amends the PDF constraint), `scripts/build_site.py` (TABLES.md in the nav group that holds ILLUSTRATIONS.md)
- Test: `tests/test_migrate.py` (a v3 → v4 plan names `TABLES.md`), the docs-site build (`python3 scripts/build_site.py`) which checks every `docs/*.md` is published or listed

- [ ] **Step 1: Write the failing test**: `test_the_v4_design_note_names_tables()` asserting `"tables" in migrate.DESIGN_NOTES[4].lower()` and `"TABLES.md"` in the rendered plan for 3 → 4.
- [ ] **Step 2: Run to verify it fails.** Expected: KeyError 4 or assertion.
- [ ] **Step 3: Write the docs.** TABLES.md sections: "Write a pipe table", "Two shapes" (the rule, with the 106-of-116 count as the reason), "Force a shape" (`::: {.ledger}` / `::: {.grid}`), "What each edition renders" (a five-row table, itself a grid), "What the verifiers refuse". Keep the house voice.
- [ ] **Step 4: Run** `python3 -m pytest tests/test_migrate.py -q && python3 scripts/build_site.py`. Expected: PASS and a green site build (Chrome layout check may skip locally).
- [ ] **Step 5: Commit**

```bash
git add docs/TABLES.md docs/BOOK-PARTS.md docs/MIGRATION.md src/press/migrate.py CHANGELOG.md docs/ROUND-1B-EDITION-PARITY-V4-PLAN.md scripts/build_site.py tests/test_migrate.py
git commit -m "Docs: TABLES.md, the v4 migration note now includes the PDF"
```

### Task 8: Acceptance on Publishing with Press

**Files:**
- Create: `scripts/measure_tables.py` (the headless-Chrome table measurement, from the production session's scratch script: per cell line boxes, in-token code splits, clipped cells, pages scrolling sideways, at 1280/820/390; reuses `scripts/check_layout.Chrome`; prints a table and exits 0 unless `--fail-on-any` is given)
- No book files change in this task.

- [ ] **Step 1:** `scripts/dev-render.sh --book /Users/clint/code/publishing-with-press --out <book>/build/v4-tables web pdf` (read the script header for the exact flags).
- [ ] **Step 2:** `python3 scripts/measure_tables.py <book>/build/v4-tables/dist/site`. Expected: in-token splits 0, clipped cells 0, pages scrolling sideways 0 at all three widths; 106 `.ledger` and 10 `.grid` elements across the site.
- [ ] **Step 3:** Open the PDF at Table 16.1's page and at Table 15.5's; confirm the ledger form; note the page count in the task report.
- [ ] **Step 4:** Run `scripts/verify.sh --full`. Expected: green except the Lua floor, which waits for CI's report.
- [ ] **Step 5: Commit** `scripts/measure_tables.py` with a CHANGELOG line, push the branch, open the PR with the before/after table from Step 2 in its body.

---

## Self-review notes

Spec coverage: 3 → Tasks 1-2; 4.1 → 2, 3, 4; 4.2 → 2, 3, 4; 5.1 → 2; 5.2 → 5; 5.3 → 6; the optional browser check → Task 8 as a script, not a target (spec amended); 6 → 7; 7 → 8. Type names used across tasks: `util.word_count`, `util.table_shape`, `PressLedger`, `\PressGridBegin`, `\PressGridEnd`, classes `ledger`, `ledger-caption`, `ledger-legend`, `ledger-sub`, `grid`, `verify_tables(markup, label)`, `verify_text_block(images, profile)`, `text_block_right(images)`. Review Focus items 1, 2, 4 are tested in Task 2, item 3 in Tasks 3 and 6, item 5 in Task 4.
