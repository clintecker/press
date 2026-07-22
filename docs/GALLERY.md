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

Each card below is printed in its own book's palette, and everything on it —
the colours, the trim, the summary, the imprint, what the book exercises — is
read from that example's own files when this page is built. The page images
are rendered from each book's **actual PDF**, built by the same pipeline in
the same toolchain, and the whole PDF is one click away. Nothing here is
described or drawn by hand, so nothing here can drift.

(The example books carry no cover art — they are written to build without
commissioned images — so the previews show generated title pages and interior
typography: the real trim, front matter, and chapter openings.)

<!--GALLERY-CARDS-->

## What differs, and where it lives

Every difference above is a file in the book's own directory. Nothing in the
pipeline was touched, and no example is a special case.

| To change… | Set this | Seen in |
|---|---|---|
| Trim and binding | `print: profile:` in `config/metadata.yaml` | the 5×8 chapbook and novella |
| Palette and register | `config/aesthetic.yaml` | every book, most visibly the field guide vs the almanac |
| The initial that opens each chapter | `chapter-opening:` in `config/metadata.yaml` | the novella and the almanac (a three-line drop cap) |
| Binding | `print: binding:` in `config/metadata.yaml` | the saddle-stitched almanac |
| Dedication, epigraph, acknowledgements | `config/front-matter.yaml` | the chapbook, monograph, novella, cookbook |
| A subject index | `config/index-terms.yaml` | the cookbook |
| The reading measure and web styling | `assets/web/extra.css` | the chapbook, which opens the line spacing for verse |
| Back matter (also-by, about the author) | files in `book/appendices/` | the monograph and novella |
| Citations | Markdown footnotes in the chapter text | the monograph and field guide |

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
