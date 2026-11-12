# Round 1B: edition parity M1–M3 as v4.0.0 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship v4.0.0, the design major in which a figure's declared placement, the illustration lists, the cross-references, and the three set-piece constructs are re-performed in HTML, EPUB, and DOCX with medium-appropriate fidelity, and the verifier proves each one rendered.

**Architecture:** One filter change per concern, projected into every non-PDF writer at once (`figure-numbering.lua` translates `place`/measure/`outset` into classes and custom properties for the web, and into a marker for Word; `set-pieces.lua` grows a `docx` arm). Three stylesheets carry the web geometry. DOCX gets its own defaults file, a reference document generated from pandoc's default plus the house styles, and one small post-processor that applies the two things pandoc's writer cannot express from the AST: a text-wrapping frame around a placed figure, and per-paragraph indent and size directives for cascades and tails. The reader site gains a Python pass that resolves anchors across chapter pages, which the chunked writer does not do. Every addition is gated on a declared construct, and `verify_formats.py` gains presence checks that fire only when the source declares the construct.

**Tech Stack:** pandoc Lua filters (pandoc 3.1.3 in CI and the toolchain image, 3.9 locally), CSS, Python 3.10+ (`zipfile`, `xml.etree`, `re`), pytest, celebrimbor gate, the Lua coverage ratchet.

**Spec:** `docs/EDITION-PARITY-PLAN.md` (capability matrix, per-edition items, "New cross-edition verification", M1–M3 of "Recommended sequencing", and the non-goals). `CLAUDE.md` § The contract. Memory `press-design-contract-scope`.

## Findings this plan rests on (verified 2026-11-11 with pandoc 3.9.0.2)

- `figure-numbering.lua` strips `place`/`outset` on every non-latex writer (`strip_house_keys`), so HTML, EPUB, and DOCX render every placed figure as a centred in-flow figure. `set-pieces.lua` emits styled geometry only for `html`/`epub` (`is_web`) and a bare `LineBlock` for docx. `scene-break.lua` has no docx arm. DOCX builds through `portable.yaml` (`build.py` handler `"docx"`) with no reference document.
- The chunked writer does **not** rewrite a link to an id in another chunk: `href="#f1"` stays `#f1` on a page that does not contain `f1`. It names a chunk `%s-%i.html` (section number, identifier), so an unnumbered front section becomes `-illustrations.html`. Blocks before the first H1 go to a chunk of their own (`0--1.html`), not to `index.html`.
- The docx writer passes a `RawInline("openxml", …)` into the paragraph verbatim (a `w:fldSimple` survives), emits a `w:bookmarkStart` named after a `Span` identifier and after a `Figure` identifier, maps `custom-style="Verse"` to `w:pStyle w:val="Verse"`, and writes an image's `title` attribute to `wp:docPr/@title`. It adds an undefined custom style to `styles.xml` as a bare Normal-based style.
- `verify_docx` checks sentinels, witnesses, and media count but **not** `require_figure_labels`; HTML and EPUB do.
- `tests/structure_harness.py` compares the DOCX's declared styles in the regression direction only (removed = drift, added = fine), the EPUB document count exactly, and the site's pages in the regression direction; its baseline book declares none of these constructs.
- `examples/signal-and-noise-manual` declares every placement (`04-plates-and-placement.md`); `examples/alice-in-wonderland` declares all three set-pieces (chapters 02 and 03). No example uses `@fig:`.

## Rulings made at planning time (deviations from the spec, each with its reason)

1. **No `SEQ`/`STYLEREF` fields in DOCX.** Pandoc writes section numbers as literal text, so `STYLEREF 1 \s` cannot resolve a chapter number and a field update would replace `2.1` with a flat count. The spec's own law is that the number stays baked text. The Table of Figures is built from the `Figure Caption` paragraph style (`TOC \h \z \t "Figure Caption,1"`), cross-references are `REF` fields to a bookmark around the caption prefix, and both carry correct cached text. No post-processing is needed for any of it.
2. **Wrapped figures in DOCX use a paragraph frame (`w:framePr`), not `wp:anchor`.** A frame keeps the image paragraph and its caption together, needs no run relocation into the following paragraph, and survives revision panes. The image extent is scaled to the frame width.
3. **The DOCX edition always builds through `docx.yaml` with the generated reference document.** A plain book's text and structure are unchanged (the reference document is pandoc's own default plus six added styles that nothing in a plain book uses); one build path beats a bimodal one. `chapter-dropcap.lua` is **not** added to the docx chain: the spec keeps the Word opening word plain.
4. **The web and EPUB illustration lists are one construct**, a front section "Illustrations" with a List of Figures and, when captioned plates exist, a List of Plates, in both editions. The PDF lists plates; the reader should too. In the chunked reader the section is its own page named `-illustrations.html` by pandoc's convention for an unnumbered section; chapter URLs do not change.
5. **Full-bleed in the reader escapes the body's inline padding, not the paper.** The reader frames the book as a sheet at wide viewports; an image across the viewport would leave the sheet. Below the sheet breakpoint the body is the viewport and the bleed is true.
6. **Tail offsets become positive padding.** A line's `padding-left` is `2·(TAIL_AMP + offset)` em and the container carries `padding-right: 2·TAIL_AMP` em, which centres the serpentine exactly with no negative margin anywhere. Word gets the same geometry as `w:ind`.

## Global Constraints

- New major: a book that declares none of these constructs renders the same **pandoc output** in HTML, EPUB, and DOCX as under v3 (byte-identical `document.xml`, byte-identical HTML body apart from the stylesheet). Every task that touches a filter ends with a test that proves it on a plain document.
- Design is now v4; within it, the existing v3 PDF/print output is **not** touched by this round. Any LaTeX branch change is out of scope. Round 1C (shape-aware tables, `docs/TABLES.md`) amends this for v4 as a whole: tables change in the PDF too, so v4 does not leave the PDF untouched; this round still makes no LaTeX change of its own.
- Docs law: a surface change and its documentation land in the same commit. The authoring docs for these constructs are `docs/ILLUSTRATIONS.md` (placements, lists, cross-references) and `docs/CONFIGURATION.md` (set-pieces).
- Pre-commit passes (ruff, mypy, PyMarkdown, yamllint, stylua, selene, Lua syntax gate); no `--no-verify`. New Python modules get `press.*` tests at ≥ the coverage ratchet's floor.
- The Lua coverage floors in `.celebrimbor/baselines/lua-coverage.yaml` hold throughout: new filter lines come with tests; floors are never lowered and are only raised from a CI report.
- A pytest skip must name a declared capability (`pandoc`), via `tests.lua_coverage.needs_pandoc`.
- Every new producer (`press.docx_ooxml`, `press.reader_links`) is registered in `.celebrimbor/producers.yaml` `producers:` with its verifier and negative fixture before the gate runs; surfaces are ratified with `celebrimbor ratify <module>`, never hand-edited.
- Release law: the major is cut with `scripts/release.sh v4.0.0` after a green main and the local gates; template and doc pins move to `@v4` in the release commit's branch; the CHANGELOG carries `## [4.0.0]`.
- Commit trailer: `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Exact numbers used throughout: `CASCADE_STEP` 2.4em; `TAIL_AMP` 3.0em; Word text width 9360 twips (Letter, 1in margins, pandoc's default reference); 1em = 240 twips at the 12pt body; measures `full-measure` 100% / `half-measure` 50% / `third-measure` 33%.

## Review Focus

1. **A placed figure inside a `Div` or `BlockQuote`** (walk_blocks recurses): the class translation must happen there too. Pinned in Task 2's test of a wrap inside a fenced div.
2. **An `@fig:` reference to a figure in another chapter on the reader site** used to dangle silently. Pinned in Task 8: the site verifier refuses a dangling anchor and the resolver rewrites it to `page.html#id`.
3. **A caption with emphasis or a footnote inside the DOCX bookmark span** must keep its inlines. Pinned in Task 9's test that the caption's `Emph` survives inside `FigureCaption`.
4. **An EPUB reader that ignores `page-break-*`** still gets a full-width centred image with no float; the own-screen is progressive. Pinned in Task 4: the bleed figure's `img` has `width:100%` with no float rule in `epub.css`.
5. **The post-processor meeting a DOCX whose `document.xml` has no marker** must return the bytes unchanged and leave the zip valid. Pinned in Task 6's identity test.

---

### Task 1: Register the plan

**Files:**
- Create: `docs/ROUND-1B-EDITION-PARITY-V4-PLAN.md` (this file)
- Modify: `scripts/build_site.py` (`NOT_PUBLISHED`)

- [ ] **Step 1:** add `"docs/ROUND-1B-EDITION-PARITY-V4-PLAN.md": "internal round plan for v4.0.0 edition parity; lives in the repo and issues, not the docs site"` to `NOT_PUBLISHED`.
- [ ] **Step 2:** `pre-commit run --files docs/ROUND-1B-EDITION-PARITY-V4-PLAN.md scripts/build_site.py` passes.
- [ ] **Step 3:** commit: `Record the round-1B plan: edition parity M1–M3 as v4.0.0`.

---

### Task 2: Placement reaches the web and Word (figure-numbering.lua, non-latex branch)

**Files:**
- Modify: `src/press/data/lua/figure-numbering.lua` (`finalize_image`, `numbered_block`, `plate_block`)
- Modify: `src/press/data/lua/press-util.lua` (new pure helpers)
- Modify: `tests/test_figure_placement.py`, `tests/test_press_util_lua.py`

**Interfaces:**
- Produces, in `press-util.lua`: `M.PLACE_CLASS = { ["wrap-inner"]="place-wrap-inner", ["wrap-outer"]="place-wrap-outer", margin="place-margin", ["full-bleed"]="place-full-bleed", frontispiece="place-frontispiece" }` (`inline`, `plate`, and no place map to nil); `M.is_full_page(place) -> boolean` (true for `full-bleed`/`frontispiece`); `M.measure_percent(width) -> string|nil` (a measure's percent, a `NN%` passed through, else nil); `M.docx_place_title(place, width, outset) -> string` returning `"press:place=<place>;width=<percent or ''>;outset=<outset or 1em>"`.
- Produces, on the web (`html*`/`epub*`): the `Figure` carries class `PLACE_CLASS[place]` and a `style` attribute `--fig-measure:<percent>;--fig-outset:<outset>;--fig-shape:url("<src>")` (each term only when its source value exists; the shape only for wraps and margin). For a full page the image `width` is forced to `100%`.
- Produces, in docx: no class; the first image's `title` is `docx_place_title(...)` **only when `place` is one of PLACE_CLASS's keys**; a full page's image width is forced to `100%` and the figure is returned as `{ RawBlock("openxml", PAGE_BREAK), fig, RawBlock("openxml", PAGE_BREAK) }` where `PAGE_BREAK = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'`.
- Every other writer (plain, markdown): unchanged from today (keys stripped, width to percent).
- Consumes: `FORMAT`; the existing `placed()`/`fig_inner()` latex path is untouched. `walk_blocks` must splice a returned **list** of blocks (the docx full page) into `out` rather than appending it as one element; today it only sees a block or `{wrap=…}`.

- [ ] **Step 1: Write the failing tests** (all `@_needs_pandoc`, `layer("integration")`):

```python
def test_wrap_carries_its_class_and_measure_into_html():
    out = _render(_WRAP, to="html")
    assert 'class="place-wrap-inner"' in out and "--fig-measure:50%" in out and "--fig-outset:1em" in out
    assert "place=" not in out and "data-place" not in out

def test_full_page_is_its_own_screen_in_epub_and_forces_full_width():
    out = _render('# C\n\n![Cap.](x.png){.figure place=full-bleed fig-alt="a"}\n', to="epub3")  # read EPUB/text/ch001.xhtml from the archive
    assert "place-full-bleed" in out and "width:100%" in out

def test_wrap_inside_a_fenced_div_is_translated_too():
    out = _render("# C\n\n::: aside\n" + _WRAP.split("\n\n", 2)[2] + ":::\n", to="html")
    assert "place-wrap-inner" in out

def test_inline_and_plate_and_bare_figures_get_no_class(): ...  # three renders, no "place-" in any

def test_docx_wrap_carries_a_title_marker_and_bleed_gets_page_breaks():
    xml = _render_docx(_WRAP)          # new helper: pandoc -o tmp.docx, return word/document.xml text
    assert 'title="press:place=wrap-inner;width=50%;outset=1em"' in xml
    bleed = _render_docx('# C\n\n![Cap.](x.png){.figure place=full-bleed fig-alt="a"}\n')
    assert bleed.count('<w:br w:type="page"/>') == 2

def test_a_plain_document_is_byte_identical_with_the_filter_in_html_epub_and_docx(): ...  # render with and without the filter; compare html body, epub ch001.xhtml, document.xml

# tests/test_press_util_lua.py: PLACE_CLASS maps the five, nil for inline/plate/nil; measure_percent("half-measure") == "50%", ("40%") == "40%", ("3in") == nil; docx_place_title("wrap-outer","third-measure",nil) == "press:place=wrap-outer;width=33%;outset=1em"
```

- [ ] **Step 2:** run `python3 -m pytest tests/test_figure_placement.py tests/test_press_util_lua.py -p no:cacheprovider`; expected: the new tests FAIL (no class, no title, no page break).
- [ ] **Step 3:** implement the helpers and the non-latex branch. `finalize_image` keeps stripping the raw keys; the class, `style`, and docx title are applied in `numbered_block`/`plate_block` from the values read **before** `finalize_image` runs. Plain/markdown writers must see no title and no class.
- [ ] **Step 4:** the full suite for the filter is green; `stylua --check` and `selene` pass on both Lua files.
- [ ] **Step 5:** commit: `Placement reaches the web and Word: figure-numbering translates place/measure/outset instead of stripping them`.

---

### Task 3: The web geometry (reader.css, book.css) and figure quality in the standalone HTML

**Files:**
- Modify: `src/press/data/web/reader.css`, `src/press/data/tex/book.css`
- Modify: `tests/test_web_css.py` (create if absent: pure-text assertions over the sheets)

**Interfaces:**
- Consumes: the classes and custom properties from Task 2.
- Produces, in **both** sheets (identical rule text; `book.css` also gains the `figure`/`figure img`/`figcaption` block it lacks, matching reader.css's values: `figure{margin:2.4rem auto;text-align:center}`, `figure img{max-width:100%;height:auto}`, `figcaption{margin:.85rem auto 0;font-size:.88rem;line-height:1.5;max-width:26rem}` with `book.css` colouring the caption `var(--muted)`):
  - `figure.place-wrap-inner{float:inline-start;inline-size:var(--fig-measure,40%);margin:.35em var(--fig-outset,1em) .6em 0;shape-outside:var(--fig-shape);shape-image-threshold:.5;shape-margin:var(--fig-outset,1em)}`; `.place-wrap-outer` and `.place-margin` mirrored to `float:inline-end` with the margin on the inline-start side.
  - `figure.place-full-bleed, figure.place-frontispiece { margin-inline: calc(-1 * var(--page-pad)); inline-size: auto; max-inline-size: none }` with `--page-pad` defined on `body` as the body's own horizontal padding at each breakpoint (`3rem` sheet / `1.25rem` narrow in the reader; `1.4rem` in book.css) and `figure.place-full-bleed img, figure.place-frontispiece img { width: 100% }`.
  - `figure.place-frontispiece { min-block-size: 100svh; display: grid; place-content: center }`.
  - reader only, at `(min-width: 56rem)`: `figure.place-margin { margin-inline-end: -2.5rem }` (hangs into the sheet's own margin, never off the paper).
  - `@media (max-width: 34rem) { figure[class*="place-wrap"], figure.place-margin { float: none; inline-size: auto; margin: 2.4rem auto; shape-outside: none } }`.

- [ ] **Step 1: Write the failing tests:** `test_both_sheets_define_every_placement_class()` (each of the five classes appears in both sheets), `test_book_css_now_styles_figures()` (`figcaption` rule present), `test_wraps_revert_below_34rem()` (the media block names `place-wrap` and `float: none`), `test_full_bleed_never_uses_viewport_units()` (no `vw` in any `place-full-bleed` rule).
- [ ] **Step 2:** run; FAIL.
- [ ] **Step 3:** write the CSS.
- [ ] **Step 4:** tests pass; `scripts/dev-render.sh html site --book examples/signal-and-noise-manual` builds; open `dist/site/4-plates-and-placement.html` and `dist/signal-and-noise-manual.html` at 1280px and 360px and confirm by eye: wraps run text around, the bleed reaches the sheet edge, nothing overflows horizontally (no horizontal scrollbar at 360px).
- [ ] **Step 5:** commit: `Web placements: floats, silhouettes, sheet-edge bleeds, and figure quality in the standalone HTML`.

---

### Task 4: EPUB own-screen plates, and the placement-presence verifier for HTML, EPUB, and the site

**Files:**
- Modify: `src/press/data/tex/epub.css`
- Modify: `src/press/verify_formats.py` (`verify_html`, `verify_epub`, `verify_site`; new helpers)
- Modify: `.celebrimbor/invariants.yaml` (new `INV-format-construct-parity`), `src/press/quality_checks.py` if it indexes proofs
- Test: `tests/test_verify_constructs.py` (new)

**Interfaces:**
- Produces, `epub.css`: `figure.place-full-bleed, figure.place-frontispiece { page-break-before: always; page-break-after: always; text-align: center }` and `figure.place-full-bleed img, figure.place-frontispiece img { width: 100%; max-width: 100% }`. **No float rule for any placement** (wraps stay centred in-flow at their declared width).
- Produces, `verify_formats.py`: `declared_places(root: Path) -> set[str]` (every `place` the build's chapter files declare, via `figures.parse` over `booklib.chapter_files()`, intersected with `("wrap-inner","wrap-outer","margin","full-bleed","frontispiece")`); `require_placement_classes(markup: str, places: set[str], label: str) -> None` (for each place, `f'place-{place}'` must occur in `markup`, else `SystemExit(f"{label} dropped the declared placement {place}: no figure carries place-{place}")`). Called from `verify_html` (raw HTML), `verify_epub` (the concatenated xhtml), `verify_site` (all chapter pages' raw text).

- [ ] **Step 1: Write the failing tests:**

```python
def test_declared_places_reads_the_build_file_set(tmp_path, monkeypatch): ...  # two chapters, one draft; {"wrap-inner","full-bleed"}; inline and plate excluded
def test_placement_class_present_passes(): vf.require_placement_classes('<figure class="place-wrap-inner">', {"wrap-inner"}, "HTML")
def test_missing_placement_class_is_named():  # SystemExit mentions "wrap-outer" and "EPUB"
def test_no_declared_places_is_a_no_op(): vf.require_placement_classes("<p>plain</p>", set(), "HTML")
```

- [ ] **Step 2:** run; FAIL (`AttributeError`).
- [ ] **Step 3:** implement; wire into the three verifiers after their `require_figure_labels`/witness calls.
- [ ] **Step 4:** add the invariant entry (statement: "When the source declares a figure placement or a set-piece, every edition's markup carries the construct; the verifier refuses an edition that re-strips it." enforced_by `verify_formats:require_placement_classes`, negative_proof `tests/test_verify_constructs.py::test_missing_placement_class_is_named`). Task 11 extends this same entry with the set-piece proofs.
- [ ] **Step 5:** `python3 -m pytest tests/test_verify_constructs.py tests/test_verify_epub_figures.py -p no:cacheprovider` green; `scripts/dev-render.sh all --book examples/signal-and-noise-manual` passes its verify stage.
- [ ] **Step 6:** commit: `EPUB full pages take their own screen; the verifier refuses an edition that drops a declared placement`.

---

### Task 5: The DOCX chain: docx.yaml, the generated reference document, the build dispatch, scene breaks

**Files:**
- Create: `src/press/data/defaults/docx.yaml` (from `portable.yaml`: `from`, `standalone`, `toc`, `toc-depth`, `number-sections`, `metadata-file` unchanged; filters `typographic-spacing`, `set-pieces`, `scene-break`, `figure-numbering`; `reference-doc: "@book/build/reference.docx"`)
- Create: `src/press/docx_ooxml.py`
- Modify: `src/press/build.py` (`render_defaults` writes the reference document for `name == "docx"`; new `_build_docx(slug)`; handler `"docx"` → `_build_docx`)
- Modify: `src/press/data/lua/scene-break.lua` (docx arm)
- Modify: `src/press/verify_formats.py` (`verify_docx` gains `require_figure_labels`)
- Modify: `.celebrimbor/producers.yaml` (`press.docx_ooxml` under `producers:` with `verifier: press.verify_formats:verify_docx`, negative fixture from Task 6), `docs/REFERENCE.md` (the docx row: "builds through docx.yaml with a generated reference document")
- Test: `tests/test_docx_ooxml.py` (new), `tests/test_scene_break.py`, `tests/test_build_docx.py` (new)

**Interfaces:**
- Produces: `docx_ooxml.HOUSE_STYLES: dict[str, str]` mapping styleId → the `<w:style …>` XML, for exactly: `FigureCaption` ("Figure Caption": italic, `w:sz 20`, centred, `w:spacing w:after="240"`), `Verse` (`w:ind w:left="720"`, spacing before/after 240), `Cascade` (spacing 0), `Tail` (centred, `w:ind w:right="1440"`, spacing 0), `SceneBreak` ("Scene Break": centred, spacing before/after 360), `FrontispieceImage` ("Frontispiece Image": centred). Each `w:basedOn w:val="Normal"`, `w:qFormat`.
- Produces: `docx_ooxml.reference_doc(out: Path) -> Path`: runs `pandoc --print-default-data-file reference.docx`, appends every HOUSE_STYLES entry absent from `word/styles.xml` before `</w:styles>`, writes the zip to `out` (all other members copied byte-for-byte, in order). Deterministic for a given pandoc.
- Produces: `build._build_docx(slug: str) -> None`: `pandoc_build("docx", f"dist/{slug}.docx", extra=["--to=docx"])` then `docx_ooxml.postprocess(path)` (Task 6 defines it; here it is the identity).
- Produces: `scene-break.lua` docx arm: when `FORMAT == "docx"`, the asterism becomes `Div(Plain(Str "* * *"), Attr("", {}, {{"custom-style","Scene Break"}}))` and fairy dust the same Div with the three rows as a `LineBlock`; the `rule` ornament stays a `HorizontalRule`.

- [ ] **Step 1: Write the failing tests:**

```python
# tests/test_docx_ooxml.py
def test_reference_doc_carries_every_house_style(tmp_path): ...  # unzip; styles.xml has each styleId once
def test_reference_doc_keeps_pandocs_own_styles(tmp_path): ...  # "BodyText", "Heading1", "ImageCaption" still present
# tests/test_build_docx.py (needs_pandoc, layer integration): a scaffolded book builds dist/<slug>.docx through docx.yaml; word/settings.xml or styles.xml shows "FigureCaption"; verify_docx passes
# tests/test_scene_break.py: test_asterism_is_a_scene_break_paragraph_in_docx (pStyle SceneBreak in document.xml); test_rule_ornament_stays_a_rule_in_docx
```

- [ ] **Step 2:** run; FAIL.
- [ ] **Step 3:** implement. `render_defaults("docx")` calls `docx_ooxml.reference_doc(root / "build" / "reference.docx")` before resolving paths.
- [ ] **Step 4:** `verify_docx` adds `require_figure_labels(flattened, numbered_figure_count(booklib.root()), "docx")`.
- [ ] **Step 5:** register the producer; `celebrimbor ratify press.docx_ooxml`; `celebrimbor gate --diff-base origin/main` green locally.
- [ ] **Step 6:** `python3 -m pytest tests/test_structural_baseline.py tests/test_sabotage.py -p no:cacheprovider` still green (added styles are growth, not drift).
- [ ] **Step 7:** commit: `DOCX builds through its own defaults with a generated house reference document; scene breaks reach Word`.

---

### Task 6: DOCX placed figures: frames for wraps, own pages for bleeds

**Files:**
- Modify: `src/press/docx_ooxml.py`
- Modify: `src/press/verify_formats.py` (`verify_docx`)
- Test: `tests/test_docx_ooxml.py`, `tests/test_verify_constructs.py`

**Interfaces:**
- Consumes: the `press:place=…` title marker from Task 2 (in `wp:docPr/@title`), the page-break paragraphs (already final).
- Produces: `docx_ooxml.parse_marker(title: str) -> dict[str, str] | None` (`{"place","width","outset"}` or None when the title does not start with `press:place=`).
- Produces: `docx_ooxml.frame_xml(place: str, width_pct: int, outset_em: float) -> str` returning `<w:framePr w:w="{w}" w:hSpace="{gap}" w:vSpace="{gap}" w:wrap="around" w:vAnchor="text" w:hAnchor="margin" w:xAlign="{align}" w:y="1"/>` with `w = round(9360 * width_pct / 100)` (default 40% when width is empty), `gap = round(outset_em * 240)`, `align = "left"` for `wrap-inner`, `"right"` for `wrap-outer` and `margin`.
- Produces: `docx_ooxml.apply_frames(document_xml: str) -> str`: for each `w:drawing` whose docPr title parses, (a) scale `wp:extent`/`a:ext` so `cx == w * 635` with `cy` in proportion, (b) insert the frame into the containing paragraph's `w:pPr` (creating one) after the last of `w:pStyle`, `w:keepNext`, `w:keepLines`, `w:pageBreakBefore` present, and (c) insert the identical frame into the **next** paragraph when its `w:pStyle` is `ImageCaption` or `FigureCaption`, so image and caption share one frame; (d) blank the `title` attribute. A document with no marker is returned **unchanged**.
- Produces: `docx_ooxml.postprocess(path: Path) -> None`: rewrites `word/document.xml` through `apply_frames` and `apply_paragraph_directives` (Task 11; identity until then), copying every other zip member in order; no-op when nothing changed.
- Produces, verifier: `require_docx_constructs(document_xml: str, places: set[str], label: str)`: a wrap/margin place requires `w:framePr` with `w:wrap="around"`; a full-page place requires `<w:br w:type="page"/>`. Wired into `verify_docx` with `declared_places(booklib.root())`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_parse_marker(): assert docx_ooxml.parse_marker("press:place=wrap-outer;width=33%;outset=1.5em") == {"place":"wrap-outer","width":"33%","outset":"1.5em"}; assert docx_ooxml.parse_marker("A title") is None
def test_frame_xml_values(): # wrap-inner, 50, 1.0 -> w:w="4680" w:hSpace="240" w:xAlign="left"; margin -> right
def test_apply_frames_frames_image_and_caption_and_scales_extent(): ...  # a hand-written two-paragraph fragment; both paragraphs gain framePr; cx == 4680*635; title blanked
def test_apply_frames_is_identity_without_a_marker(): assert docx_ooxml.apply_frames(xml) == xml
def test_postprocess_keeps_the_zip_valid_and_other_members_intact(tmp_path): ...  # build a docx via pandoc (needs_pandoc); postprocess; zipfile.testzip() is None; [Content_Types].xml unchanged
def test_verify_docx_refuses_a_docx_without_the_declared_frame(): ...  # the producer's negative fixture: SystemExit names "wrap-inner"
```

- [ ] **Step 2:** run; FAIL.
- [ ] **Step 3:** implement with `xml.etree.ElementTree` registering the `w`, `wp`, `a`, `pic`, `r`, `mc`, `w14` namespaces so the serialisation keeps pandoc's prefixes; or with anchored regexes if namespace round-tripping proves lossy (state which in the report).
- [ ] **Step 4:** tests green; `scripts/dev-render.sh docx --book examples/signal-and-noise-manual`, open the DOCX in Word or LibreOffice and confirm text wraps around the half-measure figures and the bleed sits alone on its page.
- [ ] **Step 5:** commit: `Word wraps text around a placed figure through a paragraph frame; bleeds take their own page`.

---

### Task 7: The Illustrations section for the web and EPUB (List of Figures, List of Plates)

**Files:**
- Modify: `src/press/data/lua/figure-numbering.lua` (`Pandoc`, after `walk_blocks`), `src/press/data/lua/press-util.lua`
- Modify: `src/press/data/web/reader.css`, `src/press/data/tex/book.css`, `src/press/data/tex/epub.css`
- Modify: `src/press/verify_formats.py` (`require_illustration_list`)
- Test: `tests/test_figure_numbering_filter.py`, `tests/test_verify_constructs.py`

**Interfaces:**
- Produces, filter (only when `FORMAT` matches `html` or `epub`): while walking, every plate whose caption is non-empty is recorded as `{id, caption_inlines}`; a plate with an empty identifier is minted `plate-<k>` (k counting captioned plates from 1) and the `Figure` gets that identifier. After the walk, when `has_numbered or #plates > 0`, insert at `doc.blocks` position 1: `Header(1, "Illustrations", Attr("illustrations", {"unnumbered"}))`, then when numbered figures exist `Div({ Header(2, "Figures", Attr("list-of-figures-title", {"unnumbered","unlisted"})), BulletList(items) }, Attr("", {"list-of-figures"}))` where an item is `Plain({ Link({Str "Figure", Space, Str numstr}, "#"..id), Str ".", Space } .. caption_inlines)`, and likewise `Div(..., {"list-of-plates"})` with items `Plain({ Link(caption_inlines, "#"..id) })`. Figures recorded in document order; `numbers` already maps id → numstr. A numbered figure with no identifier is listed without a link (`Str` instead of `Link`).
- Produces, CSS (all three sheets, theme-safe in epub.css): `.list-of-figures ul, .list-of-plates ul { list-style: none; padding-left: 0 }` and `.list-of-figures li, .list-of-plates li { border-bottom: 1px dotted currentColor; padding: .45em .2em; }` (reader.css uses `var(--foil)` for the rule, matching `#TOC`).
- Produces, verifier: `require_illustration_list(markup: str, expected_figures: int, label: str)`: when `expected_figures > 0`, `class="list-of-figures"` must appear in `markup`. Wired into `verify_html`, `verify_epub`, `verify_site` (any page).

- [ ] **Step 1: Write the failing tests:** `test_html_gets_an_illustrations_section_with_linked_figures()` (`id="illustrations"`, `list-of-figures`, `href="#f1">Figure 1.1`); `test_captioned_plates_are_listed_with_minted_ids()` (`id="plate-1"`, `list-of-plates`); `test_uncaptioned_plates_and_plain_books_get_no_section()`; `test_plain_text_and_docx_get_no_illustrations_section()`; `test_the_section_is_its_own_chunk_in_the_reader()` (`-t chunkedhtml` into tmp: `-illustrations.html` exists and holds the list); verifier tests: present passes, missing named, zero figures no-op.
- [ ] **Step 2:** run; FAIL.
- [ ] **Step 3:** implement.
- [ ] **Step 4:** green; render signal-and-noise `html epub site` and look at the section in each.
- [ ] **Step 5:** commit: `Web and EPUB editions open with an Illustrations section: a List of Figures and a List of Plates`.

---

### Task 8: Anchors resolve across reader pages, and every edition's anchors are verified

**Files:**
- Create: `src/press/reader_links.py`
- Modify: `src/press/build.py` (`site_build`: call the resolver after pandoc, before the zip)
- Modify: `src/press/verify_formats.py` (`require_anchors_resolve`; wired into `verify_html`, `verify_epub`, `verify_site`)
- Modify: `.celebrimbor/producers.yaml` (`press.reader_links` → verifier `press.verify_formats:verify_site`, negative fixture below), `.celebrimbor/invariants.yaml` (new `INV-format-anchors-resolve`)
- Test: `tests/test_reader_links.py` (new), `tests/test_verify_constructs.py`

**Interfaces:**
- Produces: `reader_links.page_ids(html: str) -> set[str]` (every `id="…"` value); `reader_links.local_anchors(html: str) -> list[str]` (every `href` of the form `#x` or `name.html#x`, in order).
- Produces: `reader_links.resolve_anchors(site: Path) -> int`: builds `id → page` over `site/*.html`; for each page rewrites `href="#x"` where `x` is not on that page but is on exactly one other page to `href="other.html#x"`; returns the count rewritten; raises `SystemExit("reader site: N anchors resolve nowhere: page.html -> #x, …")` when any `#x` is on no page. `href="#"` and `href="#top"`-style anchors that pandoc's own template emits are ignored only if not present as ids on no page (do not special-case; the template's anchors all resolve).
- Produces: `verify_formats.require_anchors_resolve(pages: dict[str, str], label: str)`: `pages` maps a name to its markup; for each page, each `#x` must be an id on that page and each `name.html#x` an id on `name`; EPUB passes `{member name: xhtml}` and tolerates `name.xhtml#x`; the standalone HTML passes one page.

- [ ] **Step 1: Write the failing tests:**

```python
def test_resolve_rewrites_a_cross_page_anchor_and_leaves_same_page_ones(tmp_path): ...  # two pages; "#f1" on a.html -> "b.html#f1"; "#here" untouched; returns 1
def test_resolve_refuses_an_anchor_that_is_nowhere(tmp_path): ...  # SystemExit names the page and "#ghost"  (the producer's negative fixture)
def test_resolve_is_idempotent(tmp_path): ...
def test_require_anchors_resolve_passes_and_refuses(): ...
```

- [ ] **Step 2:** run; FAIL.
- [ ] **Step 3:** implement; `site_build` calls `reader_links.resolve_anchors(out)` and prints `+ resolved N cross-page anchors` when N > 0.
- [ ] **Step 4:** add a temporary `@fig:` reference across chapters to a scratch copy of signal-and-noise (not committed) and confirm the built site's link lands on the figure's page; the verifier passes before and refuses when the resolver call is commented out.
- [ ] **Step 5:** register producer and invariant; ratify; gate green.
- [ ] **Step 6:** commit: `Reader-site anchors resolve across chapter pages; every edition's anchors are verified to land`.

---

### Task 9: DOCX captions, cross-references, and the Table of Figures

**Files:**
- Modify: `src/press/data/lua/figure-numbering.lua` (docx arm of `numbered_block`; `Cite` walk; front-matter insertion), `src/press/data/lua/press-util.lua` (`M.docx_bookmark(id) -> string` = `"fig_" .. id:gsub("[^%w]", "_")`)
- Modify: `src/press/verify_formats.py` (`fig_reference_count(root) -> int`, counting `@fig:[%w_.:-]+` tokens in the build's chapter files; `require_docx_fields(document_xml, numbered, refs, label)`)
- Modify: `docs/ILLUSTRATIONS.md` ("What each placement produces" gains an HTML/EPUB/DOCX column; a paragraph on the Word Table of Figures and `REF` fields: they show correct cached text and update on F9)
- Test: `tests/test_figure_numbering_filter.py`, `tests/test_verify_constructs.py`

**Interfaces:**
- Produces, docx numbered figure: the `Figure` is replaced by `{ Para({image}), Div(Plain(prefix .. caption_inlines), Attr("", {}, {{"custom-style","Figure Caption"}})) }` where `prefix = { Span({ Strong({Str("Figure " .. numstr .. ".")}) }, Attr(bookmark)), Space }` and `bookmark = docx_bookmark(fig.identifier)` (a figure with no identifier gets no Span, just the Strong). The image keeps its width percent and alt.
- Produces, docx `Cite`: `RawInline("openxml", '<w:fldSimple w:instr="REF ' .. bookmark .. ' \\h"><w:r><w:t xml:space="preserve">Figure ' .. num .. '</w:t></w:r></w:fldSimple>')`.
- Produces, docx front matter when `has_numbered`: inserted at position 1: `Header(1, "Figures", Attr("list-of-figures", {"unnumbered"}))` then one `RawBlock("openxml", TOF)` where `TOF` is a complex field: first paragraph `<w:p><w:pPr><w:pStyle w:val="TOC1"/></w:pPr><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> TOC \h \z \t "Figure Caption,1" </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:hyperlink w:anchor="{bm}"><w:r><w:t xml:space="preserve">Figure {numstr}. {caption plain text}</w:t></w:r></w:hyperlink></w:p>`, one further `<w:p><w:pPr><w:pStyle w:val="TOC1"/></w:pPr><w:hyperlink …>…</w:hyperlink></w:p>` per remaining figure, and `<w:r><w:fldChar w:fldCharType="end"/></w:r>` appended inside the last paragraph. Caption plain text via `pandoc.utils.stringify`, XML-escaped (`&`, `<`, `>`, `"`).
- Produces, verifier: when `numbered > 0`: `document.xml` contains `instrText` with `TOC \h \z \t "Figure Caption,1"` and at least `numbered` occurrences of `w:pStyle w:val="FigureCaption"`; `fldSimple w:instr="REF fig_` occurrences ≥ `refs`.

- [ ] **Step 1: Write the failing tests:** `test_docx_numbered_caption_is_a_figure_caption_paragraph_with_a_bookmark()`; `test_docx_cross_reference_is_a_ref_field_with_cached_text()`; `test_docx_table_of_figures_lists_every_numbered_figure()` (count of `w:hyperlink w:anchor="fig_` equals figures); `test_docx_caption_keeps_its_emphasis_inside_the_bookmark()`; `test_a_figure_without_an_id_is_captioned_but_not_bookmarked()`; verifier tests for present/missing/no-op; `test_fig_reference_count_counts_tokens_in_build_files`.
- [ ] **Step 2:** run; FAIL.
- [ ] **Step 3:** implement. The Lua coverage floor for `figure-numbering.lua` must hold: run the filter tests with `PRESS_LUA_COV_DIR` set and `scripts/lua_coverage_ratchet.py check --cov-dir`; add tests until it passes.
- [ ] **Step 4:** green; open signal-and-noise's DOCX, press F9 on the Table of Figures, confirm the entries and page numbers fill and a REF still reads `Figure 4.2`.
- [ ] **Step 5:** docs paragraph; commit: `Word gets real caption paragraphs, REF cross-references, and a Table of Figures built from the Figure Caption style`.

---

### Task 10: Set-pieces at full web fidelity (verse lines, hanging punctuation, wider tail, logical cascade)

**Files:**
- Modify: `src/press/data/lua/press-util.lua` (`M.TAIL_WEB_FACTORS = {1, 1, 0.92, 0.84, 0.76, 0.68, 0.6, 0.52, 0.45}`, `M.tail_web_factor(i, n) -> number`, `M.tail_web_size(i, n)` now `string.format("%.2gem", factor)`-equivalent of the factor, `M.tail_web_pad(i, n) -> number` = `2 * (M.TAIL_AMP + offset)`, `M.TAIL_CONTAINER_PAD = 2 * M.TAIL_AMP`)
- Modify: `src/press/data/lua/set-pieces.lua` (web arms of `verse`, `tail`, `cascade`)
- Modify: the three sheets
- Modify: `docs/CONFIGURATION.md` (the set-pieces entry gains one sentence per edition on what each construct becomes)
- Test: `tests/test_press_util_lua.py`, `tests/test_set_pieces.py`, `tests/test_web_css.py`

**Interfaces:**
- Produces, web verse: `Div({ Div(Plain(line), Attr("", {"verse-line"} [+ "stanza-first" for the first line after a blank])) … }, Attr("", {"verse"}))`; the LaTeX arm is unchanged.
- Produces, web tail: per line `style = string.format("padding-left:%.2fem;font-size:%s", tail_web_pad(i, n), tail_web_size(i, n))`; no `margin-left` anywhere.
- Produces, web cascade: `padding-inline-start` in place of `padding-left`.
- Produces, CSS (all three): `.verse { margin: 1.5em 0 1.5em 3em }`, `.verse .verse-line { margin: 0; padding-left: 1.5em; text-indent: -1.5em; hanging-punctuation: first }`, `.verse .stanza-first { margin-top: .8em }`, `.tail { padding-right: 6em; overflow-x: clip }`, `.cascade .cascade-line { margin: 0 }`. The old `.verse { … 2.4em }` margin is replaced.

- [ ] **Step 1: Write the failing tests:** util: `tail_web_pad(1, 9) == 6.0`, `tail_web_pad` is never negative across `i = 1..n` for `n` in `{1, 2, 9, 30}`, `tail_web_factor(9, 9) == 0.45`; filter: `test_verse_is_per_line_divs_with_a_stanza_gap_class_in_html()`, `test_tail_lines_use_positive_padding_only()` (no `margin-left` in the html output; `padding-left:6.00em` on line 1), `test_cascade_uses_the_logical_property()`; CSS: all three sheets define `.verse-line`, `.stanza-first`, and `.tail { padding-right: 6em`; `test_constructs_degrade_to_a_clean_line_block_in_plaintext` still passes unchanged.
- [ ] **Step 2:** run; FAIL.
- [ ] **Step 3:** implement; `stylua`/`selene` clean; Lua floors hold (`set-pieces.lua` 93.0, `press-util.lua` 96.7).
- [ ] **Step 4:** render Alice `html epub site` and look at chapter 2's cascade and verse and chapter 3's tail at 1280px and 360px: the tail is centred, nothing clips at the left edge.
- [ ] **Step 5:** commit: `Set-pieces on the web: per-line verse with hanging punctuation, a wider tail taper on positive offsets, logical cascade indents`.

---

### Task 11: Set-pieces in Word, the paragraph-directive post-process, and the construct-presence verifier

**Files:**
- Modify: `src/press/data/lua/set-pieces.lua` (docx arms), `src/press/data/lua/press-util.lua` (`M.docx_directive(k, left_twips, right_twips, half_points) -> string` = `string.format("press_%d_L%d_R%d_S%d", …)`; `M.em_twips(em) -> integer` = `math.floor(em * 240 + 0.5)`; `M.tail_docx_size(i, n) -> integer` = `math.floor(tail_web_factor(i, n) * 24 + 0.5)`)
- Modify: `src/press/docx_ooxml.py` (`apply_paragraph_directives`)
- Modify: `src/press/verify_formats.py` (`set_piece_kinds(root) -> set[str]`, `require_set_piece_constructs(markup_or_xml, kinds, label, edition)`)
- Modify: `.celebrimbor/invariants.yaml` (extend `INV-format-construct-parity` proofs)
- Test: `tests/test_set_pieces.py`, `tests/test_docx_ooxml.py`, `tests/test_verify_constructs.py`

**Interfaces:**
- Produces, docx verse: `Div(Plain(inl), Attr("", {}, {{"custom-style","Verse"}}))` (the same joined-LineBreak inlines the web uses).
- Produces, docx cascade: one `Div(Plain({ Span({}, Attr(docx_directive(k, em_twips(cascade_indent(i)), 0, 0))) } .. line), Attr("", {}, {{"custom-style","Cascade"}}))` per line, `k` a filter-global counter (so every bookmark name is unique in the document).
- Produces, docx tail: per line the same shape with `custom-style "Tail"` and `docx_directive(k, em_twips(tail_web_pad(i, n)), em_twips(TAIL_CONTAINER_PAD), tail_docx_size(i, n))`.
- Produces: `docx_ooxml.apply_paragraph_directives(document_xml: str) -> str`: for every `w:bookmarkStart` whose `w:name` matches `^press_\d+_L(\d+)_R(\d+)_S(\d+)$`, in its enclosing `w:p`: set `w:ind w:left`/`w:right` (merging into an existing `w:ind`, placed in schema order after `w:pStyle`/frame/spacing and before `w:jc`) when either is non-zero; when S is non-zero set `w:sz`/`w:szCs` to S on every run's `w:rPr` (creating `w:rPr` as the first child of a run lacking one); remove the `bookmarkStart` and its matching `bookmarkEnd` (same `w:id`). No directive → unchanged string.
- Produces, verifier: `set_piece_kinds` scans the build's chapter files for fenced-div openers (`^:{3,}\s*\{?\.?(cascade|verse|tail)\b`, multiline); `require_set_piece_constructs` requires, per declared kind, `class="<kind>"` (the HTML/EPUB check, `edition="web"`) or `w:pStyle w:val="<Kind>"` (`edition="docx"`, capitalised), else `SystemExit(f"{label} lost the {kind} set-piece: no {construct} present")`. Wired into `verify_html`, `verify_epub`, `verify_site`, `verify_docx`.

- [ ] **Step 1: Write the failing tests:** filter (`_render_docx`): verse → `pStyle w:val="Verse"` with `w:br` line breaks; cascade → three `Cascade` paragraphs each with a `press_` bookmark whose L grows by 576 (2.4em × 240); tail → `Tail` paragraphs with `R1440` and an `S` that falls from 24 to 11; `test_docx_plain_document_is_byte_identical_with_set_pieces()`; post-process: a hand-written paragraph with `press_3_L576_R0_S0` gains `w:ind w:left="576"` and loses the bookmark pair; `press_4_L1440_R1440_S16` sets `w:sz w:val="16"` on two runs; identity without directives; `test_postprocess_runs_both_passes` (a document with a frame marker and a directive gets both); verifier tests: web present/missing, docx present/missing, `set_piece_kinds` reads `::: verse` and `::: {.tail}` and ignores a draft file.
- [ ] **Step 2:** run; FAIL.
- [ ] **Step 3:** implement; wire `apply_paragraph_directives` into `postprocess`.
- [ ] **Step 4:** render Alice's DOCX; open it: the cascade is a staircase, the tail tapers and snakes, the verse is inset; `verify_docx` passes.
- [ ] **Step 5:** extend the invariant's proofs; gate green; commit: `Set-pieces reach Word: Verse, Cascade, and Tail styles with per-line indent and size; the verifier refuses a lost construct in any edition`.

---

### Task 12: The major: docs, migration, pins, changelog, proofs

**Files:**
- Modify: `docs/MIGRATION.md` (new "What v3 → v4 actually changes" section after the v2 → v3 one, listing: placements now rendered in HTML/EPUB/DOCX; the Illustrations section in web and EPUB; Word's Table of Figures, REF fields, frames; the set-piece changes; that a book declaring none of these is unchanged apart from stylesheet bytes; and that the PDF is untouched), `src/press/migrate.py` (`DESIGN_NOTES[4]`: `"design changes: v4 is a design major for the non-PDF editions (declared figure placements, the illustration lists, cross-references, and set-pieces now render in HTML, EPUB, and DOCX); the PDF is unchanged; docs/MIGRATION.md 'What v3 → v4 actually changes' lists what moved."`), `tests/test_migrate.py` (a v3 → v4 plan names `MIGRATION.md` and `PDF is unchanged`)
- Modify: `src/press/data/template/requirements.txt`, `src/press/data/template/dot-github/workflows/book.yml`, `docs/INSTALL.md`, `docs/QUICKSTART.md`, `site/landing.md`, `docs/MIGRATION.md` examples → `@v4` (`tests/test_scaffold_pin.py::test_template_pins_the_current_major` drives this; it reads `pyproject.toml`'s major, which `release.sh` bumps, so run it against a locally bumped version to prove the edit, then restore)
- Modify: `CHANGELOG.md` (`## [4.0.0] - <release date>` above `[3.0.2]`, grouped Added / Changed / Verification, naming the six rulings' outcomes in user terms), `docs/COMPATIBILITY.md` if it lists majors, `ROADMAP.md` (mark edition parity M1–M3 shipped; M4–M5 remain)
- Modify: `docs/ILLUSTRATIONS.md` and `docs/CONFIGURATION.md` (final read-through; every claim matches what Tasks 2–11 built)

- [ ] **Step 1:** write the docs and the note; tests for the note pass.
- [ ] **Step 2:** rebuild the gallery locally: `python3 scripts/build_examples.py` (or `scripts/dev-render.sh all --book examples/<each>` for the two construct-bearing books and one plain book, `the-tinsmith-novella`); every `press all` verify stage passes; diff the plain book's `document.xml` and HTML body against a build from `main` to prove the no-construct identity.
- [ ] **Step 3:** `scripts/verify.sh --full` green (pytest with coverage, celebrimbor gate with `--diff-base origin/main`, the Lua ratchet, site build, gauntlet).
- [ ] **Step 4:** commit: `v4.0.0 documentation: migration notes, @v4 pins, changelog, authoring docs for placements and set-pieces in every edition`.

---

### Task 13: Land, release v4.0.0, repin the consuming book

- [ ] **Step 1:** push the branch; open the PR (`gh pr create`), wait for `Press selftest` (all matrix legs), `Press integration gate`, and the docs-site build green. If the Lua ratchet reports a floor it could raise, raise it with `scripts/lua_coverage_ratchet.py update --from-report <CI report> --reason "round 1B: <filter> tests"` in a follow-up commit; never lower one.
- [ ] **Step 2:** final whole-branch review (fable) per the SDD skill; one fix wave; merge to main.
- [ ] **Step 3:** on main: the four local gates (`scripts/verify.sh`, installed-wheel desk run with `pytest-xdist`, Lua ratchet check, clean tree with the user's untracked files parked), then `scripts/release.sh v4.0.0`; confirm `gh release view v4.0.0` and that `refs/tags/v4` exists and points at it.
- [ ] **Step 4:** in `~/code/make-ready`: `press migrate 4` (plan), `press migrate apply`, commit, push, wait for its `build.yml@v4` run green; look at its HTML, EPUB, and DOCX once (the human ship-gate the spec names for EPUB readers is Clint's: Apple Books and Kindle Previewer in night and sepia).
- [ ] **Step 5:** update memory `press-state-2026-11.md`; close this round in the ledger.

## Not in this round (carried, on the record)

- M4 (ornaments, `initial-letter`, diamond `hr` in book.css, DOCX scene-break styling beyond the paragraph) and M5 (global microtypography) of the spec; they follow in v4.x as design corrections only if they are gated, else in v5.
- `shape-outside` beyond the `url()` silhouette; true calligram tails; fixed-layout EPUB; CSS counters; a faked Word drop cap (spec non-goals).
- The reader's chapter-URL scheme (`%s-%i.html`) is unchanged; the unnumbered front page's leading-hyphen name is pandoc's convention and is accepted.
