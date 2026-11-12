# The parts of a book

::: {.lede}
A finished book carries parts its manuscript does not: a title page, a
dedication, an index, a list of sources, a note on the author. Press builds
some of them from configuration and typesets the rest from Markdown you
write.
:::

To see these parts assembled into very different finished books, browse the
[gallery](https://github.com/clintecker/press/blob/main/docs/GALLERY.md): a
field guide, a poetry chapbook, a monograph, a novella, and a cookbook, each
the same pipeline with different config.

Every part is one of two kinds, and the kind tells you where it lives.

- [generated]{.tag .gen} &nbsp;**Generated matter** — press builds it from
  configuration: the title page, colophon, dedication, epigraph,
  acknowledgements, the index, the table of authorities. You set a value;
  press typesets the page.
- [authored]{.tag .made} &nbsp;**Authored matter** — Markdown you write in
  `book/`. Press stitches `book/chapters/*.md` and then
  `book/appendices/*.md` in filename order. You write the file and name it
  so it sorts where you want.

## A book, front to back

<div class="anatomy">
<div class="an-band">
<p class="an-band-label">Front matter</p>
<ul>
<li class="gen"><span class="an-name">Half-title &amp; title page</span><span class="an-where">config/front-matter.yaml</span></li>
<li class="gen"><span class="an-name">Copyright &amp; colophon</span><span class="an-where">config/front-matter.yaml</span></li>
<li class="gen"><span class="an-name">Dedication</span><span class="an-where">config/front-matter.yaml</span></li>
<li class="gen"><span class="an-name">Epigraph</span><span class="an-where">config/front-matter.yaml</span></li>
<li class="gen"><span class="an-name">Acknowledgements</span><span class="an-where">config/front-matter.yaml</span></li>
</ul>
</div>
<div class="an-band">
<p class="an-band-label">The book</p>
<ul>
<li class="made"><span class="an-name">Preface or foreword</span><span class="an-where">book/chapters/00-*.md</span></li>
<li class="made"><span class="an-name">Chapters</span><span class="an-where">book/chapters/*.md</span></li>
</ul>
</div>
<div class="an-band">
<p class="an-band-label">Back matter</p>
<ul>
<li class="made"><span class="an-name">About the author</span><span class="an-where">book/appendices/*.md</span></li>
<li class="made"><span class="an-name">Also by &amp; further reading</span><span class="an-where">book/appendices/*.md</span></li>
<li class="made"><span class="an-name">Glossary</span><span class="an-where">book/appendices/*.md</span></li>
<li class="gen"><span class="an-name">Index</span><span class="an-where">config/index-terms.yaml</span></li>
<li class="gen"><span class="an-name">Sources &amp; authorities</span><span class="an-where">config/authorities.yaml</span></li>
</ul>
</div>
</div>

Cinnabar marks generated matter; graphite marks the pages you author.

## Setting a value

There are two ways to set any configured value. The easy one:

```sh
press config set <path> <value>     # validated before it is written
press config list                   # every field and its current value
press config validate               # check the whole configuration
```

`press config set` checks your edit against the same typed model that
validates a build, so press refuses a bad value before writing anything. The
other way is editing the YAML under `config/` by hand: same result, but
nothing checks it. List and mapping values arrive as JSON, with `--json`;
plain text needs no flag. The
[configuration reference](https://github.com/clintecker/press/blob/main/docs/CONFIGURATION.md)
lists every field.

## The byline [generated]{.tag .gen}

Who wrote the book. It feeds the title page, the EPUB metadata, and the
landing page. `author` is a list, so pass it as JSON:

```sh
press config set author '["Jane Roe"]' --json
```

Two authors, in the order they print:

```sh
press config set author '["Jane Roe", "Sam Okafor"]' --json
```

## The generated front matter [generated]{.tag .gen}

Setting any front-matter field creates `config/front-matter.yaml`, and its
presence tells press to generate the title page, colophon, and the pages
below. Turning it on makes three identity facts required alongside the title
and author — set them together:

```sh
press config set copyright "© 2026 Jane Roe" && \
press config set publisher "Old Street Press" && \
press config set publisher-place "London"
```

Then add the pages you want. Each is optional; a field you never set does not
render:

```sh
press config set dedication "For my mother, who kept every letter." && \
press config set acknowledgements "Thanks to the librarians of the Bodleian, and to R., who read every draft."
```

An epigraph is a quote and its attribution; without the quote, the page does
not render:

```sh
press config set epigraph.quote "We are what we pretend to be." && \
press config set epigraph.attribution "Kurt Vonnegut"
```

The colophon — the note at the back on how the book was made — has its own
optional lines:

```sh
press config set edition-note "First edition" && \
press config set manufacture "Printed on acid-free paper." && \
press config set colophon-note "Set in Libertinus." && \
press config set rights-notice "All rights reserved." && \
press config set contact "hello@example.test" && \
press config set motto "Made slowly."
```

Press lays out the title page, half-title, copyright page, and table of
contents; you do not write them. For complete control, an optional
`tex/title-page.tex` replaces the generated front matter. Most books never
need it.

## The author's photograph [generated]{.tag .gen}

Put a photograph at `art/author-photo.jpg`. Press engraves it into an author
portrait plate in the house style rather than printing the snapshot, so it
matches the book's other art. Set the treatment:

```sh
press config set portrait.style "three-quarter engraving, plain ground"
```

Run the `art-direction` workflow inside the book to commission the plate,
then convert the result to house format:

```sh
press art accept art/portrait.png --as portrait
```

Without a photograph, press still commissions a portrait, but it invents a
face from the book's description; the photograph is what makes the portrait
the author. Covers, interior plates, and the logomark follow the same path
and have their own guide.

## An "about the author" page [authored]{.tag .made}

Press has no about-the-author field: you write this one. Ask press for a
back-matter page and it typesets the file with the book:

```sh
press add appendix about-the-author     # -> book/appendices/z-about-the-author.md
```

Files in `book/appendices/` merge in filename order, and `press add
appendix` owns the leading letter that places the page — the first
back-matter part it makes lands at `z-` to keep it last, the next at `y-`,
and so on. It refuses to overwrite a page you have already drafted, so
running it twice never eats your work. Open the new file, replace the
placeholder line, and write. If you commissioned a portrait plate,
reference it here as you would any figure.

## Also by this author, and further reading [authored]{.tag .made}

Also authored, and a stated gap: press has no "also by" field yet — a
cross-book catalogue is planned but not built. Make it a short back-matter
page and press places it by filename; add `--front` if you would rather it
sort ahead of the other appendices:

```sh
press add appendix also-by              # -> book/appendices/y-also-by.md
```

## A preface, foreword, or introduction [authored]{.tag .made}

These are chapters, not front-matter pages. Ask press for one with
`--front` and it sorts before the numbered chapters:

```sh
press add chapter preface --front       # -> book/chapters/00-preface.md
```

Chapters merge in filename order, so the `00-` prefix `--front` assigns
runs ahead of `01-` and the rest. Without `--front`, `press add chapter`
takes the next numbered slot:

```sh
press add chapter "The Long Winter"     # -> the next NN- chapter
```

The title can carry spaces and apostrophes; press makes the filename from
it and seeds the heading, so you never quote Markdown into a shell.

A part whose heading is marked `{.unnumbered}` (or `{-}`) -- a preface, an
appendix, a colophon -- takes no chapter number, and in the PDF its pages
carry its own title in the running head, with no number.

## Footnotes [authored]{.tag .made}

Footnotes are part of the Markdown you write. Use the standard syntax
anywhere in a chapter:

```markdown
The press was proven on one book first.[^scars]

[^scars]: Every scar in the pipeline was paid for by that first production.
```

Press renders them per format: the PDF sets them at the foot of the page; the
EPUB and web reader collect them as linked notes. There is no separate
endnote setting — the format decides where a note sits, and the same Markdown
produces both.

## Code [authored]{.tag .made}

Code blocks are the fenced Markdown you already know, with or without a
language tag:

````markdown
```python
def chapter_count(book):
    return len(book.chapters)
```

```
# a fence with no tag is set the same way, in black ink
```
````

The PDF sets every fence as a house listing: the monospace face a size
below the prose (`\small`), between two hairline rules the full width of the
measure, with a little air above and below. It wraps a line that is longer
than the measure (about 70 columns on the 6x9 trim at that size), tagged or
untagged, with a small continuation mark at the head of the carried-over
part; nothing is cut at the page edge (#279). A listing longer than the
page breaks where it must; the rules mark only its true top and bottom, so
a rule never reads as the end of a block that continues overleaf. Prefer
breaking long command lines yourself with a trailing `\` where the language
allows it: the wrap is a safety net for the line you forgot, not a layout
choice. HTML and EPUB keep their own code panel.

### Examples and listings

A numbered example is a caption over its listing: **Example 2.4.**
*Installing the toolchain on macOS*. Write it either way; both give the
same result.

The bold paragraph you may already write, directly before the fence:

````markdown
**Example 2.4. Installing the toolchain on macOS**

```text
$ brew install pandoc poppler
```
````

Or the caption on the fence itself, with an optional `id` a link can
target (`[Example 2.4](#ex-toolchain)`):

````markdown
```{.text #ex-toolchain caption="Example 2.4. Installing the toolchain on macOS"}
$ brew install pandoc poppler
```
````

The number is yours: write `Example 2.4.` (chapter and number),
`Example 4.` (a book that numbers straight through), or `Example A.1.` (an
appendix), the way you number tables. Press does not count examples. A
`caption=` with no number is set as the title alone.

In the PDF the caption sits just above the listing's top rule, the number
in bold and the title in italic, and it never strands: when the caption,
the rule, and two lines of code do not fit at the foot of a page, all of
them move to the next. The web reader, the HTML edition, and the EPUB set it
as a small caption paragraph (class `example-caption`) directly above the
code; a DOCX takes it in the `Caption` style, and plain text keeps it as the
paragraph it was.

The bold form is recognised only when the paragraph holds nothing but the
bold caption and the next block is a fence. A bold paragraph before prose,
a list, or a table (`**Example.** Press lowercases the name...`) stays an
ordinary paragraph, and so does a number in another form
(`**Example 6-1. ...**`); rewrite it as `Example 6.1.` to make it a caption.

A tagged fence is syntax-highlighted in every edition. Under a single-ink
print profile the highlighting is monochrome by design: the print build
highlights with the press's single-ink theme, so a tagged fence prints in
black and passes `press verify-print` (#273). A profile that declares
`ink: color` keeps the default coloured highlighting, as do the reading PDF,
HTML and EPUB. An untagged fence is black ink everywhere.

## The index [generated]{.tag .gen}

A page-accurate subject index, generated on every build. You curate the
terms; press finds the locations. Create `config/index-terms.yaml` — a list
of terms, each with the patterns that count as a mention:

```yaml
- term: "movable type"
  match: ["movable type", "moveable type"]
- term: "verification"
  match: ["verif", "proof-read"]
```

Press searches the manuscript for those patterns and builds the index from
what it finds. Delete the file to remove the index. A location is a chapter
number, an appendix letter, or, for an unnumbered back-matter part not titled
as an appendix (a colophon), the part's own title.

::: {.callout}
**Press will not print a wrong page number.** A term that matches nothing in
the text fails the build. Fix the patterns or remove the term; press will not
skip it silently.
:::

## A glossary [authored]{.tag .made}

Authored, and a gap like "also by": press does not generate or check a
glossary the way it does the index. Make one as a back-matter page and
fill it with a Markdown definition list, or with a two-column pipe table of
term and meaning: when the meanings run to a sentence, press sets that table
as a ledger, hanging entries in the manpage form (see [tables](tables.html)):

```sh
press add appendix glossary             # -> book/appendices/x-glossary.md
```

::: {.callout .gap}
**Not generated yet.** Press cannot build or check a glossary against the
text today. A generated glossary that works like the index — curated terms,
a build that fails on a term it defines but never uses — is a feature to ask
for.
:::

## The bibliography: sources and authorities [generated]{.tag .gen}

Press's bibliography is a table of authorities: a ledger mapping each claim
of fact in the book to the source that warrants it. It lives in
`config/authorities.yaml`, one entry per claim:

```yaml
- claim: "industrialize verification"
  file: "book/chapters/02-copy.md"
  authority: "Moxon, Mechanick Exercises (1683)"
  url: "https://archive.org/details/..."
  note: "establishes the shop practice the chapter draws on"
```

The `claim` is an exact fragment of your text. On every build press confirms
each claim still appears — once, in its declared file — and regenerates a
standalone **Sources and authorities** document published beside the book
(`<slug>-sources.md`). Reword or cut a claim's sentence and the build fails,
naming where the claim went, so the bibliography always matches the current
text.

Populate it with the `authorities-research` workflow, run inside the book: it
extracts the claims, researches each against web sources, audits them, and
writes the ledger. It verifies a sources ledger; it is not a BibTeX or CSL
citation engine.

## Store and format metadata [generated]{.tag .gen}

The small facts that ride into the EPUB, the landing page, and the stores:

```sh
press config set description "A short history of proof-reading, and why it still matters." && \
press config set keywords '["printing", "proof-reading", "book history"]' --json && \
press config set lang "en-GB"
```

`description` is the one-sentence blurb; `keywords` is a list, so `--json`;
`lang` is a BCP-47 tag passed to the formats.

## At a glance

<div class="partgrid">
<div class="part gen">
<span class="part-name">Byline</span>
<p class="part-what">Who wrote the book; feeds the title page, EPUB, and landing page.</p>
<span class="part-where">config/metadata.yaml</span>
</div>
<div class="part gen">
<span class="part-name">Front matter</span>
<p class="part-what">Dedication, epigraph, acknowledgements, and the colophon.</p>
<span class="part-where">config/front-matter.yaml</span>
</div>
<div class="part gen">
<span class="part-name">Author portrait</span>
<p class="part-what">An engraved portrait plate made from your photograph.</p>
<span class="part-where">art/author-photo.jpg</span>
</div>
<div class="part gen">
<span class="part-name">Index</span>
<p class="part-what">A page-accurate subject index; press checks every term against the text.</p>
<span class="part-where">config/index-terms.yaml</span>
</div>
<div class="part gen">
<span class="part-name">Sources &amp; authorities</span>
<p class="part-what">Each claim mapped to its source, rechecked on every build.</p>
<span class="part-where">config/authorities.yaml</span>
</div>
<div class="part made">
<span class="part-name">Preface / foreword</span>
<p class="part-what">A chapter that sorts before the numbered ones.</p>
<span class="part-where">book/chapters/00-*.md</span>
</div>
<div class="part made">
<span class="part-name">About the author</span>
<p class="part-what">A back-matter page you write.</p>
<span class="part-where">book/appendices/z-*.md</span>
</div>
<div class="part made">
<span class="part-name">Also by / further reading</span>
<p class="part-what">A short list, placed by filename.</p>
<span class="part-where">book/appendices/*.md</span>
</div>
<div class="part made">
<span class="part-name">Glossary</span>
<p class="part-what">A definition list; authored, not checked.</p>
<span class="part-where">book/appendices/*.md</span>
</div>
<div class="part made">
<span class="part-name">Code blocks</span>
<p class="part-what">Tagged fences, highlighted; single-ink on a single-ink print profile.</p>
<span class="part-where">inline Markdown</span>
</div>
<div class="part made">
<span class="part-name">Footnotes</span>
<p class="part-what">Standard <code>[^1]</code> footnotes, in any chapter.</p>
<span class="part-where">inline Markdown</span>
</div>
<div class="part made">
<span class="part-name">Code</span>
<p class="part-what">Fenced blocks, tagged or not, set between hairlines; long lines wrap instead of running off the page; an <code>Example C.N.</code> caption stays with its listing.</p>
<span class="part-where">inline Markdown</span>
</div>
</div>

## Checking your work

After any change, three commands show where you stand:

```sh
press config list && \
press config validate && \
press check
```

`press config list` shows every field with its value, `press config validate`
runs the typed model over the configuration, and `press check` runs the
verifiers — including the index and authorities checks that hold the
generated matter to your text.
