# Migrating between press majors

A book pins the press to a major — `@v1`, `@v2`, and now `@v3` — and that pin is a
contract: it resolves the same pipeline, action, and toolchain bytes for as
long as you leave it. Moving to a new major is opting into a new contract,
and this page is how you do it safely, prove what changed, and reverse it if
you change your mind.

The whole operation is one command, `press migrate`, and its first promise
is that it touches **only the pin**. Your manuscript, your config, and your
accepted art — the three things a book owns — are never rewritten by a
migration. A migration changes which pipeline builds your book, never what
your book says.

## What v1 → v2 actually changes

Almost nothing, unless you ask for more. v2 makes trim, binding, cover
material, and print vendor configurable, but a book that repins from `@v1`
to `@v2` and keeps the **house design profile** renders byte-for-byte as it
did under v1: the house 6×9 profile reproduces the sealed v1 geometry
exactly. The design changes only when you *select* a non-house
`print.profile` — a separate, explicit choice you make after migrating, not
a side effect of the pin.

So the migration itself is small: it rewrites the press major in the two
places a book pins it, and leaves everything else alone.

| Site | Before | After |
| --- | --- | --- |
| `requirements.txt` | `clintecker/press@v1` | `clintecker/press@v2` |
| `.github/workflows/<ci>.yml` | `…/build.yml@v1` | `…/build.yml@v2` |

An immutable pin (`@v1.20.0`) is floated to the new major (`@v2`); pin a
three-part v2 tag afterward if you want to freeze the exact release.

## What v2 → v3 actually changes

More than v2 did, and in every book. v3 is a design major: it moves the
typography of the house interior, so a book that repins from `@v2` to `@v3`
does **not** render byte-for-byte as before. Two things change on every
page, and two more appear only when a manuscript asks for them.

- **A fine-press craft pass on the house typography.** Optical margins and
  even colour through microtype protrusion and expansion; oldstyle text
  figures for the aesthetic's PDF font; ligatures suppressed across a
  morpheme seam; and a widow, orphan, runt, and hyphenation discipline that
  no longer lets a paragraph end on a hyphen, stack two hyphenated lines,
  carry a hyphen across a page turn, or leave a lone word on a paragraph's
  last line. A curated set of abbreviations (`Mr. Smith`, `p. 42`,
  `C. L. Dodgson`) binds to what follows with a non-breaking space in every
  edition. Glyph positions and line breaks move; page counts may move with
  them.
- **Figures earn numbers, a list, and cross-references.** A figure that
  declares an informative kind (`.figure`, `.chart`, `.map`, `.photo`,
  `.diagram`) is numbered by chapter, listed in a List of Figures kept apart
  from the List of Plates, and reachable with `@id`. A plate stays
  unnumbered. A book that declares no numbered figure sees no change here.
- **A placement vocabulary for images** (`width`, `place`, `outset`,
  `fig-alt`, `decorative`), laid in the PDF as real wraps, cleared leaves,
  and frontispieces, and refused by `press check` when malformed. A book
  that uses none of it is unchanged by this item.
- **Set-piece constructs** (`::: cascade`, `::: verse`, `::: tail`), an
  `ornate` chapter opening, and aesthetic-driven scene breaks. All opt-in.

So a v3 migration is a re-proof of your PDF, not a quiet repin: after
`press migrate apply`, build the book and look at it, because the pages
have been reset. The migration itself is still only the pin, and
`press migrate rollback` still restores the exact v2 pin if you want the old
pages back.

| Site | Before | After |
| --- | --- | --- |
| `requirements.txt` | `clintecker/press@v2` | `clintecker/press@v3` |
| `.github/workflows/<ci>.yml` | `…/build.yml@v2` | `…/build.yml@v3` |

The full list of what shipped in 3.0.0, with the within-major fixes that
rode along, is in the
[changelog](https://github.com/clintecker/press/blob/main/CHANGELOG.md).

## What v3 -> v4 actually changes

v4 is a design major, and it reaches the PDF as well as the web editions,
so a book with tables or code does not render byte-for-byte as it did under
v3.

- **Tables are set by shape** ([tables](tables.html)). A reference list (two
  or three columns whose last column, and only that one, is prose) becomes a
  ledger: each key on a line of its own, its description beneath it at the
  full measure, the header row kept as a one-line legend and the caption
  kept. Every other table becomes a grid: in the PDF it is set a size
  smaller, its columns get widths that wrap instead of running past the text
  block, and code in its cells never hyphenates; on the Web it scrolls in its
  own box and stacks into labelled cards on a phone. In the PDF, ledgers
  replace key-plus-prose tables outright, and grids are smaller and wrap, so
  page breaks and the page count move a little. A book that wants a table
  kept as a table wraps it in `::: {.grid}`; `::: {.ledger}` forces the other
  way.
- **Two new verifiers.** Every table on an HTML surface must be a wrapped
  grid or a ledger, so a raw HTML `<table>` in the manuscript is now refused,
  and so is a table nested inside a grid-table cell (the press shapes the
  outer table and leaves the inner one bare; lift it out of the cell);
  and no PDF page may ink past its text block. A v3 book that built green can
  turn red on either, and each failure names the PDF page, or the edition
  and page file that holds the table.
- **Line breaking changes in every book, with or without tables.**
  `\emergencystretch` is 10em (pandoc's 3em under v3), and a code span may
  break as a last resort after an existing hyphen or after `/ _ . , ( ) ; = :`
  with no glyph added. Paragraphs that held unbreakable code re-break, so page
  breaks move (55 of 387 pages on *Publishing with Press*), and a code line
  that overran the margin under v3 now either breaks or fails the text-block
  verifier.

- **Every code block is a listing** ([the parts of a book](book-parts.html)).
  In the PDF every fence, tagged or not, is set a size smaller (`\small`)
  between two hairline rules the full width of the measure, with 9pt (plus
  2pt of stretch) above and below and 4pt between each rule and the code;
  the air from the prose to the top rule and from the bottom rule to the
  prose is the same (about 13pt, ink to rule). The code inside sets as
  before at the new size: the same face, the same wrapping. A one-line
  lead-in ("Press prints:") is kept with its listing. Page breaks move in
  any book with code: on *Publishing with Press* 387 to 405 pages (+18,
  about 5 percent). A listing longer than a page breaks as before; its rules
  mark only its true top and bottom.
- **An example caption is attached to its listing.** A paragraph that is
  nothing but `**Example C.N. Title**` (or `Example N.`, or `Example A.N.`
  in an appendix) directly before a fence becomes the listing's caption:
  bold number, italic title, set just above the top rule, and kept with the
  rule and two lines of code, so it never strands at a page foot. The
  explicit spelling is a fence attribute,
  `{.text caption="Example 2.4. Title"}`. The web, HTML, and EPUB editions
  set it as `.example-caption` above the code; DOCX in the `Caption` style;
  plain text keeps the paragraph. A bold paragraph before anything else, or
  with a number in another form (`Example 6-1.`), is untouched; a bold
  caption above a fence that also has `caption=` is dropped.

Beyond that line breaking and the listings, a book with no tables and no
code differs from v3 only by new stylesheet rules, and the text-block
verifier judges every book.
After `press migrate apply`, rebuild and look at every page that carries a
table, a listing, or inline code; `press migrate rollback` restores the exact v3 pin.

| Site | Before | After |
| --- | --- | --- |
| `requirements.txt` | `clintecker/press@v3` | `clintecker/press@v4` |
| `.github/workflows/<ci>.yml` | `.../build.yml@v3` | `.../build.yml@v4` |

## The four moves

```bash
press migrate            # or: press migrate plan — dry run, writes nothing
press migrate apply      # repin, after writing an exact backup
press migrate status     # what you're pinned to, and any recorded migration
press migrate rollback   # restore the exact prior pin
```

The plan's first note is specific to the target major: it says whether the
design moves, so read it before you apply.

### `press migrate` (plan) — see everything first

The dry run reports every change it would make and every consequence to
weigh, and **writes nothing**. This is the `INV-migration-preview`
guarantee: you learn exactly what moving majors does before a byte changes.

```text
migrate v1 -> v2

changes:
  requirements.txt: clintecker/press@v1  ->  clintecker/press@v2
  .github/workflows/book.yml: …/build.yml@v1  ->  …/build.yml@v2

before you apply:
  - design is unchanged: with the house profile, v2 reproduces the v1
    geometry byte-for-byte. Selecting a non-house print.profile is a
    separate, explicit choice.
  - the manuscript, config, and accepted art are not touched.
  - custom override tex/title-page.tex is preserved as-is: overrides the
    generated front matter entirely; verify it against your trim before
    shipping.

nothing is written until you run `press migrate apply`.
```

If you supply files the design profile does not govern — a
`tex/title-page.tex`, a custom `assets/web/reader.css` or `extra.css`, a
`config/aesthetic.yaml` — the plan **names each one** so you re-check it
against the major you are moving to. They are preserved untouched, never
silently carried or overwritten.

### `press migrate apply` — repin, reversibly

Apply writes an exact backup of every file it will change *before* it
changes anything, then rewrites the pin. It records a receipt at
`.press/migration-receipt.json`. This is the `INV-migration-safe`
guarantee: only the pin moves, and there is always a way back.

Commit the repinned `requirements.txt` and workflow. On the next push, CI
resolves the new major's pipeline and toolchain.

### `press migrate rollback` — exact reversal

Rollback restores the exact pre-migration bytes of every file the last
migration touched, from the backup, and clears the migration state. It is a
byte-for-byte reversal, not a best-effort undo.

## What migration will not do

- It will not touch `book/`, `config/`, `tex/` (except a pin, which never
  lives there), or `assets/`. A press pin found *outside* `requirements.txt`
  or a CI workflow is refused, not rewritten — migration cannot edit prose.
- It will not migrate a book pinned to two different majors at once; it
  reports the split and asks you to reconcile it first.
- It will not change your design. Moving to a non-house profile is a
  deliberate act you take after migrating, under v2's
  [trim & binding](https://github.com/clintecker/press/blob/main/docs/PRINT-FORMATS.md)
  configuration.

## Old pins keep working

Migration is opt-in and per-book. A book that never repins stays on its
major forever: `@v1` keeps resolving the v1 pipeline, and every immutable
`v1.x.y` tag resolves its exact proven bytes. There is no forced upgrade and
no deadline. The v1 milestones continue to receive fixes within the v1
design contract; v2 is a door you walk through when you want what is behind
it.

## How the press proves this

The two guarantees are invariants, proven on every selftest by
`check_migration`, which scaffolds a real book, runs the full
`plan → apply → rollback` round-trip, and asserts that the plan changes
nothing on disk, that apply moves only the pin while the manuscript, config,
and art come out byte-for-byte identical, that a receipt is written, and
that rollback restores the exact prior pin. A v2 release consumes that proof
along with the consumer backtest — a real book built from the installed v2 —
so a major cannot ship claiming a migration path it has not demonstrated.

- `INV-migration-safe` — migration moves only the pin; rollback restores
  exact bytes.
- `INV-migration-preview` — a dry run reports every change before any
  mutation.
