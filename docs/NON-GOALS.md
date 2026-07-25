# What press deliberately does not do

Press is a prose engine. It takes a manuscript written in Markdown and
typesets it into a book: a print-ready PDF, reflowable EPUB and HTML
editions, front matter, an index, a sources companion, a print pack,
and registrations. Everything it does starts from text it lays out
itself.

That is a deliberate shape, and the shape has an edge. Some kinds of
book are *designed* page by page rather than *typeset* from prose, and
press does not become that kind of tool. This page records where the
edge is so it cannot quietly drift, and names the supported path for
each thing on the far side of it.

The heuristic underneath every line below: a new profile of the prose
engine -- another trim, a colour interior, large print -- is core
press work; a new *engine* is not. When a book's pages are composed in
a layout application instead of flowing from a manuscript, press does
not typeset them. It finishes them.

## Press is not a page-layout or design application

Press does not give you a canvas, frames, guides, or manual control
over where a word sits on a page. It does not replace InDesign,
Affinity Publisher, Scribus, or QuarkXPress. Layout is the house
design's job, applied uniformly from the manuscript and the
configuration; a build has no notion of nudging one paragraph or
hand-setting one spread. The typography and layout of a valid book are
part of [the contract](https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md),
fixed within a major on purpose -- the opposite of a design surface you
open to move things around.

**The supported path:** design the interior in the layout tool of your
choice, export a print-ready PDF, and hand it to the *finisher* -- the
supplied-interior source mode. A book declares `interior:
path/to/interior.pdf` (with its trim, bleed, and page count) instead of
Markdown chapters, and press does everything around the pages it did
not set: the print pack (cover, spine, barcode) off the supplied page
count and stock, registrations, front matter, colophon, and the sources
companion, all still driven from metadata. The finisher is planned work
on the [roadmap](https://github.com/clintecker/press/blob/main/ROADMAP.md)
(the *Book breadth* milestone), not a shipped source mode today.

## Press is not a fixed-layout picture-book designer

Press does not compose a fixed-layout book -- a children's picture
book, a comic, a photography monograph, a designed cookbook, a
magazine -- where image and text are placed together on each page as an
intentional composition. Markdown figures are flowed into the running
text and capped in height so they cannot break the build; they are not
a layout grid. Designing those pages is exactly the work a
page-layout application exists to do, and press does not duplicate it.

**The supported path:** the same finisher. Design the fixed-layout
interior externally, supply the print-ready PDF, and press publishes,
verifies, registers, and print-packs it. Because press did not set the
pages, it *verifies* the supplied PDF against its declared facts --
trim, page count, bleed, ink, embedded fonts, print-readiness -- and
refuses a mismatched or non-print-ready file with a specific diagnosis
rather than shipping a broken interior.

## Press is not an interactive or rich-media ebook builder

Press does not build interactive or rich-media ebooks: no embedded
video or audio, no scripted animation, no read-aloud media overlays,
no tap-to-play widgets, no EPUB fixed-layout ebook where each screen is
a designed page. The reflowable EPUB and HTML editions press produces
are text that reflows to the reader's device and settings; that
reflowability is the point, and rich-media fixed-layout is its
opposite.

**The supported path:** for a book whose interior is genuinely
fixed-layout, the finisher degrades the reading experience *honestly*
rather than pretending. A reflowable EPUB cannot be derived from a
fixed-layout PDF, so a supplied-interior book gets a PDF-based reader
and landing page, `pdftotext` extraction for search and accessibility,
and a plain statement of which reflowable editions are unavailable and
why -- never a silently broken EPUB claiming to be reflowable.

## Why record this

An engine grows by accretion, and the easy accretion is the wrong one:
a figure-placement flag here, a fixed-layout EPUB switch there, and the
prose engine slowly becomes a worse version of a design application it
was never meant to be. Naming the non-goals keeps the line visible, so
adding a capability that crosses it is a conscious decision against a
recorded boundary rather than a drift nobody noticed. When a book needs
page design, the honest answer is a real design tool for the pages and
the finisher for everything else -- not a design surface bolted onto
the prose engine.

Related boundaries: what the toolchain supports and how a support change
is governed is in [compatibility](https://github.com/clintecker/press/blob/main/docs/COMPATIBILITY.md);
the whole plan, including where the finisher sits, is in the
[roadmap](https://github.com/clintecker/press/blob/main/ROADMAP.md).
