# The parts of a book

A finished book is more than its chapters: a title page, a dedication, an
acknowledgements page, an index, a list of sources, a note about the author.
This page walks the common parts and shows how to add each one.

Press builds a book from two kinds of material:

- **Generated matter** — press assembles it for you from configuration: the
  title page, colophon, dedication, epigraph, acknowledgements, the index,
  the table of authorities. You set a value; press typesets the page.
- **Authored matter** — anything you write as Markdown in `book/`. Press
  stitches `book/chapters/*.md` and then `book/appendices/*.md` in filename
  order into the book. A preface, an "about the author" page, a glossary —
  you write the Markdown and name the file so it lands where you want it.

Knowing which kind a part is tells you where to put it. Most of the named
front-matter pages are generated; everything else is a Markdown file you
author.

## Two doors to configuration

Every configured value has an easy door and an expert door. Lead with the
easy one:

```sh
press config set <path> <value>     # the easy door — validated before it writes
press config list                   # every field, with its current value
press config validate               # check the whole configuration
```

`press config set` checks your edit against the same typed model that
validates a build, so a bad value is refused before a byte lands. The expert
door is editing the YAML under `config/` by hand — identical result, no
guard rails. List and mapping values must arrive as JSON with `--json`;
plain text needs no flag. Every field is catalogued in the
[configuration reference](https://github.com/clintecker/press/blob/main/docs/CONFIGURATION.md).

## The byline

Who wrote the book. It feeds the title page, the EPUB metadata, and the
landing page. `author` is a list, so it takes JSON:

```sh
press config set author '["Jane Roe"]' --json
```

Two authors, in the order they should print:

```sh
press config set author '["Jane Roe", "Sam Okafor"]' --json
```

## The generated front matter

Setting any front-matter field creates `config/front-matter.yaml`, and its
presence asks press to generate the PDF title page, colophon, and the pages
below. When you turn it on, three identity facts become required alongside
the title and author — set them in the same breath:

```sh
press config set copyright "© 2026 Jane Roe" && \
press config set publisher "Old Street Press" && \
press config set publisher-place "London"
```

Then add the pages you want. Each is optional; a field you never set simply
does not render:

```sh
press config set dedication "For my mother, who kept every letter." && \
press config set acknowledgements "Thanks to the librarians of the Bodleian, and to R., who read every draft."
```

An epigraph is a quote plus its attribution; the quote gates the page:

```sh
press config set epigraph.quote "We are what we pretend to be." && \
press config set epigraph.attribution "Kurt Vonnegut"
```

The colophon — the note at the back on how the book was made — has its own
knobs, all optional:

```sh
press config set edition-note "First edition" && \
press config set manufacture "Printed on acid-free paper." && \
press config set colophon-note "Set in Libertinus." && \
press config set rights-notice "All rights reserved." && \
press config set contact "hello@example.test" && \
press config set motto "Made slowly."
```

The title page, half-title, copyright page, and table of contents are laid
out for you; you do not author them. If you need complete control, an
optional `tex/title-page.tex` overrides the generated front matter entirely
— that is the expert escape hatch, not the common path.

## The author's photograph

Drop a photograph at `art/author-photo.jpg`. Press's art department turns it
into an engraved author portrait plate in the house style rather than
printing the snapshot directly, so it sits with the book's other art. The
portrait's treatment is part of the book's visual identity:

```sh
press config set portrait.style "three-quarter engraving, plain ground"
```

Run the `art-direction` workflow from inside the book to commission the
plate, then bring the result into house format:

```sh
press art accept art/portrait.png --as portrait
```

With no photograph supplied, the portrait commission still works from the
book's description; the photograph is what makes it the *actual* author. The
full art path — covers, interior plates, the logomark — is its own guide;
this is only the portrait.

## An "about the author" page

There is no `about-the-author` config field: this one is authored matter.
Write it as a back-matter Markdown file and press will typeset it with the
rest of the book:

```sh
printf '# About the author\n\nJane Roe writes about ...\n' > book/appendices/z-about-the-author.md
```

Files in `book/appendices/` merge in filename order, so a leading letter
places the page — `z-` keeps it last. If you commissioned a portrait plate,
reference it here the way you reference any other figure.

## Also by this author, and further reading

Also authored matter, and also a known gap: press has no dedicated "also by"
field yet (a cross-book catalogue is planned but not built). Today, write it
as a short Markdown page and place it with a filename — front matter with an
early letter, or back matter with a late one:

```sh
printf '# Also by Jane Roe\n\n- *The First Book* (2021)\n- *The Second Book* (2023)\n' > book/appendices/y-also-by.md
```

## A preface, foreword, or introduction

These are chapters, not front-matter pages — you author them. Place them
with a filename that sorts before the numbered chapters:

```sh
printf '# Preface\n\nThis book began as ...\n' > book/chapters/00-preface.md
```

Chapters merge in filename order, so `00-` runs ahead of `01-`, `02-`, and
the rest.

## Footnotes and endnotes

Footnotes are part of the Markdown you write — no configuration needed. Use
the standard footnote syntax anywhere in a chapter:

```markdown
The press was proven on one book first.[^scars]

[^scars]: Every scar in the pipeline was paid for by that first production.
```

Press renders them per format: the PDF sets them at the foot of the page,
and the EPUB and web reader collect them as linked notes. There is no
separate "endnote mode" to switch on — the format decides where a note
sits, and the same Markdown produces both.

## The index

A real, page-accurate subject index, generated on every build. You curate
the *terms*; press finds the *locations*. Enable it by creating
`config/index-terms.yaml` — a list of terms, each with the patterns that
count as a mention:

```yaml
- term: "movable type"
  match: ["movable type", "moveable type"]
- term: "verification"
  match: ["verif", "proof-read"]
```

Press searches the manuscript for those patterns and builds the index
appendix from what it finds. It is deliberately strict: a term that matches
nothing in the text **fails the build**, because an index that cites a page
the word never appears on is worse than no index. Fix the patterns or remove
the term — silence is not allowed. To disable the index, delete the file;
the appendix disappears with it.

## A glossary

Authored matter, and a gap like "also by": press does not generate or verify
a glossary the way it does the index. Write one as a back-matter page using
a Markdown definition list or plain headings:

```sh
printf '# Glossary\n\n**Colophon**\n: The note at the back describing how the book was made.\n' > book/appendices/x-glossary.md
```

If you would like a *generated, verified* glossary — one press checks
against the text the way it checks the index — that is a feature worth
asking for rather than a setting that exists today.

## The bibliography: sources and authorities

Press's bibliography is a **table of authorities** — a ledger that maps each
claim of fact in the book to the source that warrants it, and then keeps
them honest. It lives in `config/authorities.yaml`, one entry per claim:

```yaml
- claim: "industrialize verification"
  file: "book/chapters/02-copy.md"
  authority: "Moxon, Mechanick Exercises (1683)"
  url: "https://archive.org/details/..."
  note: "establishes the shop practice the chapter draws on"
```

The `claim` is an exact fragment of your text. On every build press confirms
each claim still appears — exactly once, in its declared file — and
regenerates a standalone **Sources and authorities** companion document
published beside the book (`<slug>-sources.md`). A claim whose sentence you
later cut, reword, or move fails the build, naming where it went. So the
bibliography can never quietly describe a book that no longer exists.

The reliable way to populate it is the `authorities-research` workflow, run
from inside the book: it extracts the claims, researches each against web
sources, audits them adversarially, and writes the ledger. This is a
verified sources ledger, not a free-form reference list or an academic
citation engine (there is no BibTeX or CSL pipeline).

## Store and format metadata

The small facts that ride along into the EPUB, the landing page, and the
stores:

```sh
press config set description "A short history of proof-reading, and why it still matters." && \
press config set keywords '["printing", "proof-reading", "book history"]' --json && \
press config set lang "en-GB"
```

`description` is the one-sentence blurb; `keywords` is a list (hence
`--json`); `lang` is a BCP-47 tag passed through to the formats.

## Where each part comes out

| Part | Kind | Where it lives |
| --- | --- | --- |
| Byline, title, subtitle | generated | `config/metadata.yaml` |
| Dedication, epigraph, acknowledgements | generated | `config/front-matter.yaml` |
| Copyright, colophon, edition note | generated | `config/front-matter.yaml` (+ `copyright` etc.) |
| Author portrait | generated | `art/author-photo.jpg` → `press art accept` |
| Index | generated & verified | `config/index-terms.yaml` |
| Bibliography (sources & authorities) | generated & verified | `config/authorities.yaml` |
| Preface / foreword / introduction | authored | `book/chapters/00-*.md` |
| About the author | authored | `book/appendices/z-*.md` |
| Also by / further reading | authored | `book/*.md` (by filename order) |
| Glossary | authored | `book/appendices/*.md` |
| Footnotes | authored | inline Markdown, any chapter |

## Checking your work

After any change, three commands tell you where you stand:

```sh
press config list && \
press config validate && \
press check
```

`press config list` shows every field with its current value, `press config
validate` runs the typed model over the whole configuration, and `press
check` runs the full set of verifiers — including the index and authorities
checks that keep the generated matter honest against your text.
