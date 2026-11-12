# Tables

::: {.lede}
A Markdown table is two different things wearing one syntax. Most tables in
a manual are reference lists: a short key, then a sentence or two about it.
A few are true grids, read across and down. Press reads the shape from your
cells and sets each table by what it is, in every edition.
:::

## Write a pipe table

Write tables the ordinary way, as pandoc pipe tables. A caption goes on a
line of its own after the table, starting with `:`.

```markdown
| Command        | What it does                                              |
| -------------- | --------------------------------------------------------- |
| `press all`    | Builds every edition, then runs every verifier against it. |
| `press check`  | Lints the manuscript without building anything.            |
| `press doctor` | Reports which tools the build can find on this machine.    |

: The three commands you run most
```

You do not choose a layout, set column widths, or mark the table up. The
press reads the cells and decides. If it decides wrong, one fenced div
overrides it (see "Force a shape" below).

## Two shapes

The reason for the rule is a count. The first manual built with press,
*Publishing with Press*, has 116 tables; 106 of them are a key column plus
exactly one column of prose. Set as a grid, that prose column is squeezed
into a third or half of the measure and wraps a word or two to a line, and
on a phone it is worse. So press renders the two shapes differently.

**A reference list becomes a ledger.** A table is a reference list when it
has two or three columns, exactly one of them is prose (its cells average
eight words or more), and that prose column is the last one. A code span
counts as one word however long it is, so a key like `press all` is as
short as `pandoc`. A ledger is the manpage form:

- each row's first cell is the entry's key, on a line of its own;
- the prose is set beneath it at the full measure, hanging a little in;
- in a three-column table, the middle cell sits between them as a short
  line of its own (in constant width on the Web and in the EPUB);
- the header row survives as one small-capitals legend above the entries,
  its cells joined by a middle dot, and the caption is kept;
- a row whose key cell is empty continues the entry above it, as a further
  paragraph.

A ledger has no column to squeeze, so it reads the same in a 6 by 9 print
measure, at 390 pixels on a phone, in an EPUB reader, and in Word.

**Everything else is a grid.** One column, four or more columns, no prose
column, two prose columns, or a prose column that is not last: those are
grids, read across rows, and they stay tables. A grid gets fixes that make
it honest:

- every column gets a relative width, taken from its cells' mean length or
  its longest code token, whichever is larger, so a column too narrow for an
  identifier widens and the prose gives way;
- no column falls below 12 percent of the measure; a table of nine or more
  columns, where those floors alone would fill the line, shares it equally;
- in the PDF the grid is set a size smaller, with half-em cell padding,
  and it asks for room for its head and a few rows before it starts, so a
  head is never stranded at a page foot;
- code in a grid cell is never hyphenated, so `--foil-bright` is never
  split as `--foil-` / `bright`. A hyphen the identifier already has is a
  break of last resort, taken only when the token is wider than its whole
  column, because ink past the text block is a fault in print and a split
  identifier is only ugly.

## Force a shape

The rule reads cells, not intent. When it guesses wrong, wrap the table in a
fenced div with the class you want:

```markdown
::: {.grid}
| Flag      | Meaning                                                        |
| --------- | -------------------------------------------------------------- |
| `--watch` | Rebuilds the edition whenever a manuscript file changes on disk. |
:::
```

`::: {.ledger}` forces a ledger the same way. Every table inside the div
takes the forced shape. When the div holds just the one table, it becomes
the table's wrapper itself: the rendered page carries one `div.grid` or
`div.ledger`, not one nested in another, and the div's id and any other
classes and attributes you gave it are kept, so `{#flags .grid .wide}`
still has its anchor and its extra class.

A one-column table is always a grid: a ledger needs a key and something to
say about it, so `::: {.ledger}` around a one-column table still renders a
grid.

## What each edition renders

| Edition | Ledger | Grid |
| --- | --- | --- |
| PDF and print | A hanging description list: the key on its own line, the entry indented 1.6 em, a check before each key so it never strands at a page foot; the caption and the small-capitals legend above. | A smaller table with relative column widths that wrap, 0.5 em cell padding, room asked for before the head, and code that never hyphenates. |
| Reader site and HTML | A definition list in `.ledger`: the key in semibold, a hairline between entries, the middle column (`.ledger-sub`) in constant width. | The table in `.grid` at reading width, scrolling inside its own box if it is wider than the page. On a phone each row stacks into a card, each cell labelled with its column's header, and code wraps inside the card. |
| EPUB | The same `.ledger` list, plain: no colour and no web fonts, because the reader's device owns the theme. | The table in `.grid`, with the same widths. |
| DOCX | A native Word definition list, in pandoc's `DefinitionTerm` and `Definition` paragraph styles. House ledger styles arrive with the generated reference document. | The table, with the same relative column widths, which Word honours. |
| Markdown and plain text | The Markdown edition is your stitched source and keeps the pipe table; plain text prints an indented list. | The Markdown edition keeps the pipe table. Plain text prints the grid as a full-width table with ruled top and bottom, its columns in the same proportions as the other editions. |

A book with no tables renders as it did before, apart from the new rules in
the stylesheets the editions carry: the shapes are added only where a table
is.

## What the verifiers refuse

A producer is only proven by a check that rejects a broken result, so two
verifiers run on every `press all`. Both are listed in the
[invariants](invariants.html).

- **Every table is in a shape** (`INV-table-shape`, enforced by
  `verify_table_shape.verify_tables`). In the single-leaf HTML and every
  chapter of the reader site, a table must sit directly inside a `.grid`
  wrapper, every body row of a headed grid must carry the column labels its
  phone cards wear, and every `.ledger` must hold at least one entry. The
  EPUB is checked for wrappers and entries only, because it stacks no phone
  cards. A raw HTML `<table>` typed into the manuscript is refused too: the
  filter cannot see inside raw HTML, so it reaches the page bare (unless it
  sits inside your own `::: {.grid}`, whose div keeps its class and so
  passes). Write it as a pipe table.
- **No page inks past its text block** (`INV-pdf-text-block`, enforced by
  `verify_pdf.verify_text_block`). Each body page of the PDF is rendered and
  refused when its ink runs more than 6 pixels (0.05 inch) past the right
  edge of the text block the trim profile declares. This catches a table
  cell, a code line, or anything else that will not break and runs into the
  margin. Front matter and the running-head and folio bands are not judged.
  The raster cannot tell a deliberately outset figure from overflowing text,
  so such a figure is refused as well.
