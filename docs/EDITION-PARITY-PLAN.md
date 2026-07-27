# Edition parity: matching the PDF across HTML, EPUB, and DOCX

## Philosophy and scope

The reading PDF is the layout authority. Every other edition re-performs its *intentions* in its own medium; it does not photograph its fixed pages. The bar is medium-appropriate fidelity, not pixel-matching: a wrap figure that actually runs prose around it in a reflowable column, a plate that owns its space, a stanza that keeps its inset and its exact line breaks — never a promise that a Kindle page equals a LaTeX page.

Two things are already guaranteed and are explicitly out of scope to "fix": **content and meaning** (sentinels, per-chapter witnesses, and `verify_editions_agree` already prove every chapter and every distinctive fragment survives into every edition, `verify_formats.py:129-163`), and **the figure number and `@fig` cross-reference target** (computed once in `figure-numbering.lua` and baked into caption *text* so every edition agrees to the digit — this must not be replaced by CSS counters or writer-native counters, which diverge on Kindle/Word). What is missing everywhere is **layout fidelity for declared constructs** and **any pipeline gate that proves it rendered**.

The contract governs what ships when. A book that declares none of a feature must stay **byte-identical**, so every addition below is feature-gated (appears only when the source uses `place=`, a numbered figure, a set-piece div, or an opted-in ornament). Under the strict reading of the design contract (and the design-contract-scope memory), any change that alters the rendered output of a book that *builds validly today* — giving a `place=wrap` figure a real float, changing a verse inset, widening the tail taper, restyling captions — is a **design change requiring a new major**, even when feature-gated. Within a major we may ship only genuine corrections to broken output: overflow, overlap, non-centering, and dead code. This document marks every item `[within-major]` or `[new-major]` on that line. Because feature-gating bounds the blast radius, all the new-major work can be batched into one major bump.

## Capability matrix

Each cell reads **current → target**. PDF is the authority; its "target" is its present behaviour, kept.

| Concern | PDF (target/authority) | HTML (single + chunked reader) | EPUB | DOCX |
|---|---|---|---|---|
| **Figure placement** | Real `wrapfig` (i/o), full-page leaf, frontispiece via `\cleardoubleevenpage`; `margin`≡`wrap-outer` (no true margin). Keep. | All placements stripped → centered in-flow → floats (`float:inline-start/end`), `shape-outside` silhouette, full-bleed escape, true margin figures, frontispiece hero; feature-gated classes. | Stripped + `epub.css` has no `figure` rule → centered styled in-flow; full-bleed/frontispiece = own screen via `page-break`; **no float default**. | Stripped → inline centered → `wp:anchor`+`wrapSquare` float, own-page for bleed/frontispiece. |
| **Width measures** | Fraction of `\linewidth`; ignored for bleed. Keep. | Percent honored (reader), `book.css` unframed → keep percent + `max-inline-size` cap + center in `book.css`. | Percent honored but sits **flush-left** → add `figure{text-align:center}`+`img{max-width:100%}`, class fallback. | Percent scales `wp:extent` (fine) → keep; force 100% for bleed. |
| **Captions** | `\caption*`, small italic, bold `Figure C.N.` prefix. Keep. | Number baked in text; reader styles `figcaption`, `book.css` does not → add `figcaption` rule to `book.css`. | Number baked; `figcaption` unstyled → add size/italic rule (no hard color, night-safe). | Baked text in `Image Caption` style, no field → real `Caption` style + `SEQ`/`STYLEREF` fields with cached text. |
| **Figure numbering** | Computed in filter, bold in caption. Keep (filter numbers for all). | Baked in caption text — correct, keep; do **not** use CSS counters. | Baked in caption text — correct, keep. | Baked text → live `SEQ Figure`/`STYLEREF 1 \s` fields, cached "C.N". |
| **List of Figures / Plates** | Two lists: `\PressListOfFigures` (numbered) + KOMA `\listoffigures` relabelled "List of plates". Keep. | None → emit web LoF **and** LoP as `<nav>` link lists; host as a front chunk in the reader so cross-file anchors resolve. | None → generated in-body "List of Illustrations" from the `numbers` table (figures only; plates only if they carry ids). | None → `TOC \h \z \c "Figure"` field (figures only; **no** plates list — no editorial construct). |
| **Cross-references** | `\hyperref[id]{Figure~N}`, `hypcap` anchor. Keep. | `pandoc.Link → #id`, live anchor — excellent, keep. | `pandoc.Link → #id`, live anchor — excellent, keep. | Static-text `w:hyperlink` → `REF fig_<id> \h` field, cached text. |
| **Alignment** | Justified + microtype + hyphenation. Keep. | Ragged right → justify + `hyphens:auto` (rivers-safe), narrow→ragged. | Ragged / reader-controlled → leave to reader, optional justify. | Pandoc default (left) → optional justified `Normal` via reference doc. |
| **Cascade** | `\hspace*` staircase, 2.4em step. Keep. | Faithful `.cascade-line` padding → logical `padding-inline-start`. | Faithful `padding-left` (safe, no clip) → keep. | `LineBlock`, indent lost → per-para `Cascade` style + `w:ind` staircase. |
| **Verse** | `PressVerse`, `\leftskip=3em`, ragged-right tolerance. Keep. | One `Plain`+`<br>`, 2.4em inset, **dead `.verse-line` selector** → per-line divs, 3em inset, hanging-punctuation + runover indent. | Same + dead selector → **delete dead selector** (fix), 3em inset (design). | `LineBlock` → `Verse` style, `w:ind` 3em + `w:br` lines (near-lossless). |
| **Tail** | Sine offset + `\normalsize`→`\tiny` taper. Keep. | Sine exact but timid 1em→0.68em taper → widen ramp (~0.45em), `overflow-x:clip`. | Same + **negative-margin clip risk** → positive-offset centering, widen taper. | `LineBlock` → `Tail` style, per-line `w:ind` + point-scale `w:sz` (can match PDF drama best). |
| **Drop caps** | `\PressDropCap` lettrine; ornate=yinit. Off by default. Keep. | Float spans, works → add `@supports(initial-letter)` sink on Safari. | Float spans, **no clearfix in `epub.css`** → add clearfix (fix), no hard ink color. | Not in chain → plain opening word; keep plain (honest, do not fake). |
| **Scene breaks** | `\PressFairyDust` grid / centered asterism. Keep. | Faithful asterism/fairy-dust; reader ornaments `hr`, `book.css` plain `hr` → bring diamond `hr` to `book.css`. | Faithful → minor: `role="separator"` on asterism for parity. | Not in chain → ornament lost, plain rule → re-add via `docx.yaml`, `Scene Break` style. |
| **Microtypography** | Protrusion/expansion, hyphenation, widow/orphan penalties, `\parfillskip`, `selnolig`. Keep. | `book.css` bare, reader has `text-rendering` → `text-wrap:pretty/balance`, `hanging-punctuation`, `orphans/widows` in `@media print`, legibility catch-up. | Bare; reader owns type → minimal; `hanging-punctuation` (Safari) only. | Pandoc default → `Normal` widow/orphan + kerning via reference doc. |

## Per-edition implementation

PDF/print need no work; they are the target. Items are ordered most-author-visible first.

### HTML (standalone `book.css` + chunked reader `reader.css`)

1. **Stop discarding placement on the non-latex branch.** In `figure-numbering.lua` (`strip_house_keys` `:75-80`, `finalize_image` `:89-99`, `numbered_block` `:224-242`, `plate_block` `:247-263`): *translate* `place`/`outset`/measure into a class (`place-wrap-inner|wrap-outer|margin|full-bleed|frontispiece`) + custom props (`--fig-measure`, `--fig-outset`) on the `Figure`, then delete the raw keys so nothing leaks as `data-*`. **[new-major] · effort M · risk M** (must not emit any class for figures that declared no `place`, or byte-identity breaks).
2. **Implement placements in `reader.css` and `book.css`.** Float wraps on logical sides (`inner→inline-start`, `outer→inline-end`), `shape-outside` from `src` for alpha-master silhouette runaround, full-bleed via `margin-inline:calc(50% - 50vw)`, frontispiece via `min-block-size:100svh` grid hero, true `place-margin` on wide desktop (negative outer margin). Below ~34rem every wrap reverts to in-flow. **[new-major] · effort L · risk M** (float+`shape-outside` edge cases; verify against `check_layout.py` so a bled figure never overlaps the reader body frame `reader.css:29-33`).
3. **Emit a web List of Figures and List of Plates** from the filter (mirror the `\PressListOfFigures` injection `:332-334`, gated `not latex`); host as a dedicated front chunk in `chunked-template.html` so cross-file `@fig` and list links resolve to `file.html#anchor`, not a dangling `#anchor`; mint a stable id for every listed plate. Style as leader-dotted lists echoing `#TOC` (`reader.css:219-225`). **[new-major] · effort M · risk M** (chunked cross-file link resolution is the real hazard; standalone HTML has no such wrinkle).
4. **Bring `book.css` up to figure quality.** Add `figure`/`figure img`/`figcaption` rules (frame, `max-inline-size` cap, tight caption measure) matching `reader.css:145-157`; standalone HTML has *no* figure rule today. **[new-major] · effort S · risk S.**
5. **Verse fidelity in `set-pieces.lua` + CSS.** Emit per-line `.verse-line` divs (revive the dead selector), `margin-inline-start:3em`, `hanging-punctuation:first`, runover indent. **[new-major] · effort M · risk S.**
6. **Tail taper.** Widen the web ramp toward the PDF's `\tiny` end (`set-pieces.lua:131`) and add `overflow-x:clip` on `.tail`. **[new-major] · effort S · risk S.**
7. **Logical cascade indent** (`padding-left`→`padding-inline-start`, `set-pieces.lua:66-72`). **[new-major] · effort S · risk S.**
8. **Drop-cap progressive enhancement.** `@supports(initial-letter:2){.drop-cap{initial-letter:3;float:none}}` in all three sheets; keep the float span as the base. **[new-major] · effort S · risk S.**
9. **Ornamental `hr` in `book.css`** (diamond) to match the reader; aesthetic-gated. **[new-major] · effort S · risk S.**
10. **Alignment + microtypography.** `text-align:justify`+`hyphens:auto`+`hyphenate-limit-chars:6 3 3` (narrow→ragged), `text-wrap:pretty` on `p`, `text-wrap:balance` on headings, `orphans/widows` in `@media print`, `text-rendering`/`font-kerning` catch-up in `book.css`. **[new-major] · effort M · risk M** (global restyle; ship defaulted-on with a `reader.css`/`extra.css` escape; `orphans/widows` are no-ops in scrolling HTML — state that honestly).

Files: `src/press/data/lua/figure-numbering.lua`, `src/press/data/lua/set-pieces.lua`, `src/press/data/web/reader.css`, `src/press/data/tex/book.css`, `src/press/data/web/chunked-template.html`.

### EPUB (`epub.css`, epub3 writer)

Governing constraint: the reader owns the type and theme — port *structure* from `reader.css` but **drop its color fills, borders, and shadows** so night/sepia wins. No fixed-layout EPUB.

1. **Port a theme-safe figure block into `epub.css`** (currently *no* `figure`/`img` rule): `figure{margin;text-align:center;break-inside:avoid}`, `figure img{max-width:100%;height:auto}` (no background/border), `figcaption{font-size:.9em;line-height:1.4;font-style:italic}`. `max-width:100%` (overflow guard) and centering a half-measure figure are **corrections**. **[within-major] · effort S · risk S.**
2. **Drop-cap clearfix.** Add `.chapter-opening::after{content:"";display:block;clear:both}` to `epub.css` (present in `reader.css:85`, absent here) so a short opener never overlaps the floated initial. Correction. **[within-major] · effort S · risk S.**
3. **Delete the dead `.verse .verse-line` rule** (`epub.css:36`, matches no emitted element). Cleanup. **[within-major] · effort S · risk S.**
4. **Full-bleed / frontispiece as own screen.** Same filter class-translation as HTML item 1; in `epub.css` `figure.plate-full{page-break-before:always;page-break-after:always;min-height:90vh;display:flex;justify-content:center}`; force width 100%. ADE ignores flex → still full-width on its own page. **[new-major] · effort M · risk M.**
5. **Generated in-body List of Illustrations** from the `numbers` table (figures only; plates only if id'd), parallel to `:332-334`, gated `not latex`. Anchors double as navigation. **[new-major] · effort M · risk S.**
6. **Set-piece safety + inset.** Shift the tail from signed `margin-left` (clip risk on narrow columns, `set-pieces.lua:130-138`) to positive-offset centering; bring `.verse` inset to 3em; widen taper (point-scale reads well on e-readers). **[new-major] · effort M · risk M.**
7. **Do not** float wraps by default (fragile on KF8/ADE, produces the short-line rag `\Needspace` exists to avoid); render wraps as centered in-flow at declared width. Decline documented, not a task.

Files: `src/press/data/tex/epub.css`, `src/press/data/lua/figure-numbering.lua`, `src/press/data/lua/set-pieces.lua`. Ship-gate: open the built EPUB in Kindle Previewer 3, Apple Books, Thorium, Kobo, and ADE, each in night/sepia — epubcheck proves validity, not fidelity.

### DOCX (new `docx.yaml`, `reference.docx`, `docx_ooxml.py`)

DOCX shares `portable.yaml` with plain text today (3 filters, no `reference-doc`, `build.py:864`). Excellence = a manuscript built from Word's own parts for an editor with tracked changes. This whole edition upgrade is **[new-major]**; each item is gated on feature presence so a plain book still round-trips byte-for-byte through today's exact `portable`+`--to=docx` path.

1. **Fork `docx.yaml`** off `portable.yaml` (adds `reference-doc`, re-adds `chapter-dropcap` and `scene-break`); dispatch `docx` to it in `build.py` and feature-gate the reference-doc/post-process. **effort S · risk M** (all-or-nothing `--reference-doc` — must fall through to the current invocation when no feature is used).
2. **Ship `reference.docx`** (`src/press/data/docx/reference.docx`) defining `Caption`, `Verse`, `Cascade`, `Tail`, `Frontispiece Image`, `Scene Break` styles. **effort M · risk S.**
3. **Set-pieces `docx` arm in `set-pieces.lua`** (currently all three → bare `LineBlock`, the largest silent loss): verse → `custom-style="Verse"` Div (near-lossless), cascade → per-line `Cascade` + `press:step:n` marker, tail → per-line `Tail` + `press:tail:off:sz` marker; un-gate scene-break for docx → `Scene Break` centered paragraph. **effort M · risk M.**
4. **Numbered captions via fields.** In `figure-numbering.lua` docx arm stop baking `Strong`; emit `Caption`-styled para with a `press:seq` marker and cached "C.N"; `docx_ooxml.py` replaces it with `STYLEREF 1 \s`+`.`+`SEQ Figure \* ARABIC \s 1`, wrapped in a `fig_<id>` bookmark. **effort L · risk M** (STYLEREF needs Heading 1 numbering; fall back to bare `SEQ` for the pre-chapter case, `figure-numbering.lua:274`).
5. **Table of Figures + REF cross-refs.** ToF as a raw-openxml `TOC \c "Figure"` block gated on `has_numbered` (`:332`), title matching the PDF chapter; change the `Cite` walk (`:337-349`) to emit `REF fig_<id> \h` with cached text. No plates list (no editorial construct — matches PDF suppressing an empty list, `build.py:180-183`). **effort M · risk M** (fields show cached text until F9; cache correct values).
6. **Floating figures.** Filter carries `place` in `wp:docPr/@title` as `press:wrap-…`; `docx_ooxml.py` rewrites the `wp:inline` to a `wp:anchor` with `wrapSquare`, column-relative `align`, extent from measure×column-EMU, `distL/R` from outset; anchor into the following paragraph (mirror `walk_blocks`/`pending` `:286-313`). Bleed/frontispiece → `w:br type="page"` around a centered full-column `Frontispiece Image` para (pure raw-openxml, no post-process). Default `wrapSquare` not `wrapTight` (track-changes safety). **effort L · risk L** (floats reflow-fragile under revision panes; no recto/verso; degrades to centered inline if post-process skipped).
7. **Drop cap: keep plain opening word** — Word has no clean construct; do not fake a frame. Documented, not a task.

Files: new `src/press/data/defaults/docx.yaml`, new `src/press/data/docx/reference.docx`, new `src/press/docx_ooxml.py`; `src/press/build.py` (dispatch + gate + post-process call, beside the HTML `webmeta.label_table_cells` post-pass `:849-854`); `src/press/data/lua/figure-numbering.lua`; `src/press/data/lua/set-pieces.lua`. No CSS.

## New cross-edition verification

All checks go in `verify_formats.py`, in the existing witness idiom (content/structure scans over extracted text or unzipped parts — no rendering engine, that stays with `check_layout.py`). Each fires **only when the source declares the feature**, so byte-identity for non-users is preserved. This closes the map's "no fidelity gate" defect.

1. **Caption presence per edition.** When the book has numbered figures, assert every edition's extracted text contains the literal label `Figure` and a space followed by a computed number — the number is text in HTML/EPUB/DOCX (`figure-numbering.lua:230`). Add to `verify_html` (`:296-305`), `verify_epub` (`:308-342`), `verify_docx` (`:417-434`).
2. **Figure-count parity.** Count declared numbered figures in source; assert each edition witnesses at least that many `Figure C.N` labels — the cross-edition analogue of `verify_editions_agree`'s per-chapter fragment sweep, run over figure labels instead of chapter witnesses.
3. **Cross-reference resolution.**
   - HTML/site: parse built HTML, collect all `id`s, assert every `href="#…"` and every cross-chunk `file.html#…` resolves (guards `@fig` and the new LoF/LoP links). Add to `verify_html`/`verify_site` (`:437-481`).
   - EPUB: assert each `@fig` link target `id` exists in the concatenated xhtml.
   - DOCX: assert one `REF fig_` field instr per `@fig` use.
4. **Structural / order parity (per-edition construct presence).**
   - HTML/EPUB: when source declares `place=`, assert the `figure.place-*` class appears (catches a regression re-stripping placement); when the book has numbered figures/plates, assert a `.list-of-figures`/`.list-of-plates` (HTML) or "List of Illustrations" block (EPUB) exists.
   - EPUB: when a set-piece div is in source, assert `class="cascade|verse|tail|asterism|fairy-dust|chapter-opening"` appears in the xhtml.
   - DOCX: assert `w:pStyle w:val="Verse|Cascade|Tail"` when the matching fenced div is in source; `SEQ Figure` and the `Caption` style in `word/styles.xml` when numbered; `TOC \c "Figure"` when `has_numbered`; a `wp:anchor`+`wrapSquare` when a wrap/margin placement is declared.

These reuse the source-scan already implied by `plate_count()` and follow how `require_witnesses` (`:270-289`) and `verify_editions_agree` gate on presence rather than exact match.

## Recommended sequencing

Ordered so the most author-visible excellence lands first. Verification for each capability ships **with** that capability (never after), the way rendered-PDF gating is inseparable from the PDF build.

**M0 — Corrections (within-major, ship now, no version bump).** EPUB figure block + `max-width` + centering; EPUB drop-cap clearfix; delete the dead `.verse-line` selector in all three sheets. Small, purely-fixing, high-value for the weakest reader. Add EPUB caption-presence and figure-count checks alongside.

*The remaining milestones are the design major; cut the new major when M1 lands and batch M1-M5 into it. Feature-gating keeps every plain book byte-identical throughout.*

**M1 — Figures everywhere (the biggest visible gap).** Filter class/prop translation of `place`/`outset`/measure on the non-latex branch (serves HTML, EPUB, DOCX at once); HTML floats + full-bleed + frontispiece + true margin figures; EPUB full-bleed/frontispiece own screen; DOCX `wp:anchor` floats + own-page bleed; `book.css` figure quality catch-up. Ship placement-class and figure-parity verification with it.

**M2 — Illustration navigation.** Web List of Figures + List of Plates (with the chunked front-chunk host), EPUB in-body List of Illustrations, DOCX `TOC`/`REF`/`SEQ` field machinery. Ship anchor-resolution and REF/SEQ verification with it.

**M3 — Set-pieces to full fidelity.** DOCX `set-pieces.lua` arm + `reference.docx` styles (largest DOCX loss); HTML verse per-line divs + hanging punctuation + tail taper + logical cascade; EPUB tail-clip fix + verse inset. Ship set-piece construct-presence verification with it.

**M4 — Ornament and drop caps.** HTML `@supports(initial-letter)` + `book.css` diamond `hr`; DOCX scene-break style; EPUB asterism `role`. Cosmetic, low risk.

**M5 — Global microtypography (highest blast radius, last).** HTML justification + hyphenation + `text-wrap` + widow/orphan + legibility catch-up; DOCX `Normal` widow/orphan. Defaulted-on with a per-book CSS escape; ship after the feature-gated work has proven the pipeline.

## Non-goals

- **Pixel- or page-matching any edition to the PDF.** The target is medium-appropriate re-performance of intent.
- **Fixed-layout (pre-paginated) EPUB.** It disables reflow, reader font choice, scaling, and accessibility to buy a pixel-match the house rejects. No FXL.
- **CSS counters / writer-native figure counters** for numbering. The number stays baked as text so every edition agrees to the digit; counters diverge on Kindle and older Word/ADE.
- **A true calligram** (glyphs on a curved path) for the tail. That needs SVG `<textPath>` and sacrifices selectable, reflowable text. Offset + a strong taper is the medium's ceiling.
- **A faked Word drop cap.** Word's drop-cap frame fights the editor; the DOCX opening word stays plain text (honest, not silently degraded).
- **A List of Plates in EPUB or DOCX.** Plates carry no caption/SEQ and (usually) no id; there is no editorial construct, so none is synthesised — matching the PDF, which suppresses an empty list.
- **`shape-outside` / silhouette runaround in EPUB, and `float` wraps as a DOCX or EPUB default.** Unsupported or fragile on the weak-floor readers; declined deliberately.
- **Recto/verso page parity in any reflowable edition.** Inner/outer collapse to a stable logical left/right; there is no running page in reflow.
- **Any layout for the plain-text and Markdown editions.** `.txt` keeps content only; `.md` is a raw source stitch that runs no pandoc filters — both remain exactly as they are.
- **Restyling a book that declared nothing, within a major.** Every design change is gated on a declared construct and lands in the new major; a book using none of it stays byte-for-byte unchanged.
- **Rendered visual verification in `verify_formats.py`.** It asserts structure and content presence only; headless-browser layout checking stays with `check_layout.py`.
