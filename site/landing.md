# press

Write your book in Markdown. Run one command. Get a finished book — a
print-ready PDF, an ebook, and a reading website — all checked and verified
before they ship. press does the typesetting, the proofreading of its own
output, and the publishing, so you can spend your time writing.

New here? The **[quickstart](quickstart.html)** walks you from a blank
machine to your first built book, one copyable command at a time.

## What you write, what you get

You write chapters as plain Markdown files — no layout to fuss over, no
software to learn. Then one command, `press all`, produces:

- a print-ready **PDF** and an **EPUB** ebook,
- a **reading website** with a page for each chapter,
- **plain-text, Word, and Markdown** editions,
- and, when you are ready to sell, a **print pack** (interior, cover, and
  barcode) plus a link readers can order a physical copy from.

Every edition is checked and verified against your source before it ships,
so what a reader gets is exactly the book you wrote.

## Made with press

Real books, built with this pipeline — each is its own reading website press
produced:

- [**Mostly Done.**](https://2389-research.github.io/mostly-done/) — *A Brief
  Treatise on the Several Conditions under which Software may be Declared
  Finished.* press was extracted from its production, so the tool inherits
  the scars of making it.
- [**Make Ready**](https://clintecker.github.io/make-ready/) — *A Printer's
  Manual for the Age of Mechanical Compositors,* by Clint Ecker.

## Start a book

```sh
pip install "press @ git+https://github.com/clintecker/press@v2" && \
  press new my-book && \
  cd my-book && \
  press all
```

This installs press, scaffolds a complete book that already builds, and
produces every edition — so you can see the whole pipeline before you write
your first real word. The **[quickstart](quickstart.html)** explains each
step and what to do when something needs your attention.

## Make it yours

The look is yours to shape. Colors, fonts, and the whole design register
live in one small config file — or draft them from a one-line brief with
`press aesthetic "1970s pulp paperback"`. The words are always yours: press
never invents your content, and your title and author appear verbatim on
the cover.

## Where to go next

- **[Quickstart](quickstart.html)** — from nothing to a verified book.
- **[Install](install.html)** — the toolchain, per platform.
- **[Configuration](configuration.html)** — every setting a book can carry.
- **[Print ordering](print-ordering.html)** — let readers buy a copy.
- **[Command reference](reference.html)** — every `press` command.
- **[Architecture](architecture.html)** — how the machine fits together, if
  you like to know what is under the hood.

MIT licensed, code and bundled content alike. A book you make with press is
yours entirely.
