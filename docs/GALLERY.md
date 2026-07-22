# A gallery of very different books

The house Victorian idiom is the press's default, not its cage. Nothing about
a book's subject, shape, or look is hardcoded: the trim, the typography, the
palette, the cover grammar, the front matter, the reading measure, and the
structure are all configuration a book supplies. The strongest way to show
that is to show it, so this gallery is a set of complete example books that
each produce a visibly different object.

Every one of these is built by the **same pipeline**. The only thing that
differs between them is the config in their directory. They live under
[`examples/`](https://github.com/clintecker/press/tree/main/examples) in the
press repository, each buildable with `press all`, and each is proven a valid
press book on every test run: the config passes the same typed model a real
build demands, the design surfaces genuinely vary across the set, and every
one passes the editorial law (`press check`).

## The books

### Between the Tides — a naturalist's field guide

A crisp, cool-toned reference to the rocky intertidal, on the house 6×9 trim.
It shows the house pipeline making a modern, technical guide rather than a
period volume: a **sea-glass aesthetic** (cool palette, a clean humanist
face), **footnotes**, and an **epigraph**. Same machine, opposite mood.

*Exercises:* `config/aesthetic.yaml` (palette, `book-colors`, typography),
footnotes, front matter.

### Small Hours — a poetry chapbook

Twenty nocturnes on the **novella 5×8 trim**, a smaller page that suits verse
in the hand. Warm and lamplit, with a **dedication and epigraph**, a
**custom `extra.css`** that narrows the measure and opens the line spacing for
poetry, and a hushed palette. Proof the press sets verse, not only prose.

*Exercises:* a non-house **print profile** (`novella-5x8`),
`config/front-matter.yaml`, `assets/web/extra.css`, aesthetic.

### The Reasonable Commons — an academic monograph

A sober, argued monograph on the house trim, with **citations in footnotes**,
**acknowledgements**, and an **about-the-author** appendix. Its restrained
scholarly aesthetic and evidential register are a world away from the
chapbook, from the same tooling.

*Exercises:* footnotes, `config/front-matter.yaml` (acknowledgements),
appendices (about-the-author), aesthetic.

### The Tinsmith's Daughter — a literary novella

Spare contemporary fiction on the **novella 5×8 trim**, with a minimalist
cool-neutral aesthetic, a one-line **dedication**, and an **also-by**
appendix. Understated where the field guide is exact and the cookbook is warm.

*Exercises:* a non-house **print profile** (`novella-5x8`), front matter
(dedication), appendices (also-by), aesthetic.

### The Hearthstone Table — a seasonal cookbook

An unfussy winter cookbook on the house trim: warm palette, a kitchen
**dedication**, recipes as ingredient lists and method, and a **subject
index** built from `config/index-terms.yaml` (every listed term is verified
to appear in the text). Practical and generous, not literary or academic.

*Exercises:* `config/index-terms.yaml` (subject index),
`config/front-matter.yaml`, aesthetic.

## What this proves

Across the five: two different trims, five different aesthetics, footnotes,
an index, custom web styling, four kinds of front matter, and three kinds of
appended matter. No example edits the pipeline; each only edits its own
config and manuscript. If you can describe the book you want, you can
configure it. The surfaces each one uses are documented in
[parts of a book](https://github.com/clintecker/press/blob/main/docs/BOOK-PARTS.md)
and [configuration](https://github.com/clintecker/press/blob/main/docs/CONFIGURATION.md);
the trims come from versioned
[print profiles](https://github.com/clintecker/press/blob/main/docs/PRINT-FORMATS.md).

Art (covers, plates, an author portrait) is commissioned per book through the
art workflows and the aesthetic each example declares; the examples build and
validate without generated images, and degrade gracefully where art is
absent.
