# A gallery of very different books

The house Victorian idiom is the press's default, not its cage. Nothing about
a book's subject, shape, or look is hardcoded: the trim, the typography, the
palette, the cover grammar, the front matter, the reading measure, and the
structure are all configuration a book supplies. The strongest way to show
that is to show it, so this gallery is a set of complete example books that
each produce a visibly different object.

Every one is built by the **same pipeline**, with the same command. The only
thing that differs between them is the config in their directory. They live
under [`examples/`](https://github.com/clintecker/press/tree/main/examples) in
the press repository, and each is proven a real press book on every test run:
its config passes the same typed model a live build demands, the design
surfaces genuinely vary across the set, and every one passes the editorial law
(`press check`).

Each card below leads with the book's **cover**, then two real pages rendered
from its **actual PDF**, built by the same pipeline in the same toolchain.
Everything else on the card — the palette, the trim, the summary, the imprint,
what the book exercises — is read from the example's own files when this page
is built, and the whole PDF is one click away.

A book's interior prints in a **single ink**, so the two interior pages carry
one colour on their paper. The cover is where colour and image belong: each is
a Penguin-style woodcut in the book's own accent, on the classic tri-band grid,
commissioned once and committed as the book's cover art. The paper, ink, and
accent chips beneath each card name the palette both are drawn from. The
interior previews regenerate from the manuscript on every build; the cover, a
one-time commission, is a fixed asset, as a real book's would be.

<!--GALLERY-CARDS-->

## What differs, and where it lives

Every difference above is a file in the book's own directory. Nothing in the
pipeline was touched, and no example is a special case.

| To change… | Set this | Seen in |
|---|---|---|
| Trim | `print: profile:` in `config/metadata.yaml` | the 5×8 chapbook and novella |
| Palette and register | `config/aesthetic.yaml` | every book, most visibly the cookbook against the chapbook |
| The initial that opens each chapter | `chapter-opening:` in `config/metadata.yaml` | the novella and the almanac (a three-line drop cap) |
| Binding | `print: binding:` in `config/metadata.yaml` | the saddle-stitched almanac |
| Dedication, epigraph, acknowledgements | `config/front-matter.yaml` | the cookbook, monograph, chapbook, essays, novella |
| A subject index | `config/index-terms.yaml` | the cookbook and the manual |
| The reading measure and web styling | `assets/web/extra.css` | the chapbook, which opens the line spacing for verse |
| An about-the-author, an also-by | files in `book/appendices/` | every book (an also-by in the essays and the novella) |
| Citations | Markdown footnotes in the chapter text | the monograph, the manual, the essays, the field guide |

## Build them yourself

Every example builds with the same command you would run on your own book:

```sh
git clone https://github.com/clintecker/press && cd press
pip install -e . && cd examples/tidepool-field-notes && press all
```

Swap `tidepool-field-notes` for any other directory to build a different
book. `press all` runs the whole pipeline — build, check, verify — and puts
the results in that example's `dist/`.

To start your own rather than read someone else's, the
[quickstart](quickstart.html) goes from an empty directory to a verified book,
and [parts of a book](book-parts.html) is the catalogue of every piece you can
add. The trims come from versioned [print profiles](print-formats.html), and
the full set of knobs is in [configuration](configuration.html).

## About the art

Covers, plates, and author portraits are commissioned per book through the art
workflows and the aesthetic each example declares. The examples build and
validate without generated images, and degrade gracefully where art is absent
— which is why the cards above are typographic rather than photographic.
