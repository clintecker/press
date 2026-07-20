# Quickstart: from a blank machine to a verified book

This is the first path to walk. It takes you from nothing installed to a
book you can build, verify, and publish, with every command copyable and
every decision named. Reference detail lives in the canonical pages; this
guide links into them at the moment each becomes relevant.

## What you are building, and who does what

A book in the press is a folder of Markdown plus a little configuration.
You write prose; the press turns it into a PDF, an EPUB, a reading
website, and the other editions, then verifies each one is actually the
book you wrote. You never hand-set type, and you never run a store: a
print provider (Lulu) is the seller of record if you choose to sell, and
your book's CI, not your laptop, is the reference machine.

There are two kinds of thing in the steps below:

- **Yours to decide** — your title, your author name, your words, and the
  book's visual identity. Fonts, the color palette, and the design's
  register are all configurable in `config/aesthetic.yaml` (draft it from a
  one-line brief with `press aesthetic "<brief>"`); absent that file, a
  restrained house design applies. The press never invents your content.
- **The press owns** — the build order, the verification pipeline, the file
  names, and the formats it produces, so every book is made and checked the
  same way. A few craft laws are fixed rather than styled: in v1 the page
  trim is 6 x 9, print interiors are single ink, and your title and author
  appear verbatim on the art.

Every step below is one or the other, and says which.

## 1. Install a toolchain (mechanical)

The press is a Python package that drives Pandoc and TeX. Install them
once for your platform, then let `press doctor` tell you what is ready.

On macOS:

```sh
pip install "press @ git+https://github.com/clintecker/press@v1" && \
  brew install pandoc poppler && \
  brew install --cask mactex-no-gui
```

On Debian or Ubuntu, and for the container path (no local toolchain at
all), follow [the installation guide](https://github.com/clintecker/press/blob/main/docs/INSTALL.md);
it is the authority on packages per platform. Then, from anywhere, ask
the press what it sees:

```sh
press doctor
```

`press doctor` names every dependency, tells missing apart from
present-but-broken, and says what each absence would cost. It is the one
authority on a machine's readiness; run it now and after any install
step. You do not need every optional tool to build your first book.

Two discovery commands work anywhere, with no book or toolchain:
`press --version` reports the installed version, and `press --help` lists
every command (`press <command> --help` explains one).

## 2. Scaffold a book (mechanical)

The directory name becomes the book's slug (its file-name identity), so
pick a short, lowercase, hyphenated name.

```sh
press new my-first-book
cd my-first-book
```

You now have a complete, buildable book: a one-paragraph preface that
exists only so the empty book already builds and verifies, a
`config/metadata.yaml`, and the CI workflow that will build it on GitHub.
Nothing here is a placeholder you must decode; every default is a real,
working value you may keep or replace.

## 3. Enter the minimum identity facts (decisions)

Set the four facts only you can supply. The simplest way is `press
config`, which validates each value before it writes:

```sh
press config set title "My First Book" && \
  press config set subtitle "And how it came to be" && \
  press config set author '["Your Name"]' --json && \
  press config set description "One honest paragraph on what this book is."
```

`press config list` shows every field you can set, `press config get
<field>` reads one, and `press config validate` checks the whole
configuration. Prefer a screen? If you installed the desk (`pip install
'press[tui]'`), run `press desk` and press `w` for a guided setup wizard
that previews the exact diff and validates before it writes.

If you would rather edit YAML by hand, the same four facts live in
`config/metadata.yaml`:

```yaml
title: "My First Book"
subtitle: "And how it came to be"
author:
  - "Your Name"
description: >-
  One honest paragraph on what this book is.
```

Everything else in the metadata file is a mechanical default with a comment
explaining it. Two you will meet later, not now:

- **`verify-sentinels`** are short, distinctive phrases from your own
  prose — a memorable clause, not a common word. The verifiers search for
  them in every finished edition to prove your words actually made it in.
  Empty is fine for a draft; a release build requires at least two. The
  [configuration reference](https://github.com/clintecker/press/blob/main/docs/CONFIGURATION.md)
  explains the release rules.
- **`repository` and `site-url`** are filled in for you if you passed
  `--owner` to `press new`; otherwise they wait, commented, until you have
  a GitHub home for the book.

You do not have to invent any value the press did not ask for.

## 4. Add a first chapter (decisions)

Chapters live in `book/chapters/`, ordered by their number prefix. Add
one:

```sh
press wordcount
```

Create `book/chapters/01-beginning.md` with a heading and a paragraph in
your own voice. The house rules the checker enforces — straight quotes,
no em dashes, sentence-case headings, paragraphs under 190 words — are
listed in the book's own `CLAUDE.md`; write to them rather than fixing
after. When you are ready, delete the scaffolded preface's two throwaway
sentences and make it yours.

## 5. Check and build (mechanical)

Two commands. The first is editorial law; run it after every change:

```sh
press check
```

`press check` runs the source, style, and jargon checks and tells you
exactly what to fix. When it passes, build every edition:

```sh
press all
```

`press all` checks, builds each format, and verifies each artifact is the
book you wrote. The first LuaLaTeX run on a fresh machine triggers a
several-minute font scan that looks like a hang. It is not a hang; let it
finish.

## 6. When something is refused (mechanical, and deliberate)

The press fails loudly and specifically rather than shipping a wrong book.
The common first-run refusals and what they mean:

| What you see | What it means | What to do |
| --- | --- | --- |
| `pandoc is required` | The toolchain is not installed | Run `press doctor`, then [install](https://github.com/clintecker/press/blob/main/docs/INSTALL.md) what it reports missing |
| A style or jargon failure from `press check` | Prose broke a house rule | Read the named line and rule; rewrite to it |
| `sentinel ... not found` in a release build | A verify-sentinel is no longer in your prose | Restore the phrase, or update the sentinel to text that exists |
| A build that hangs for minutes on the first run | The one-time LuaLaTeX font scan | Wait; it is not a hang |
| CI dies at "Initialize containers" | The runner could not pull the toolchain image | Retry; the image is public, so no grant is needed |

A refusal is the press protecting the book. None of these are dead ends;
each names its own fix.

## 7. View every generated edition (mechanical)

Everything the build made lands in `dist/`:

```sh
ls dist/
```

You will find the PDF, the EPUB, the reading HTML, plain text, Word, the
source archive, and — if you built it — the site. To preview the reading
website locally before publishing, build the pages bundle and open its
`index.html`:

```sh
press pages
```

## 8. Push (mechanical)

Put the book on GitHub so its CI builds and publishes it:

```sh
git init && \
  git add -A && \
  git commit -m "First book" && \
  git remote add origin https://github.com/OWNER/my-first-book && \
  git push -u origin main
```

The book's CI builds inside a public, versioned toolchain image, so a book
under any account builds with no package grant and no configured secret:
the pull is authenticated with the workflow's own `GITHUB_TOKEN`, which
works for a public image even on fork and Dependabot pull requests. Every
push then builds and verifies the book and publishes the site. Enabling
GitHub Pages once (Settings → Pages → Source: GitHub Actions) turns on the
published reading site.

## Optional: shape the look (decision)

The reading site and PDF ship with a restrained house design. To make it
yours, draft a visual identity from a one-line brief:

```sh
press aesthetic "1970s pulp paperback"
```

That writes `config/aesthetic.yaml` — the color palette, web and PDF fonts,
and the cover, plate, and logomark direction — which every build and art
commission then applies. `press aesthetic` with no argument shows the
effective design. The craft laws stay fixed: the trim, single-ink print
interiors, and your title and author verbatim on the art.

## Optional: sell a print copy (decision)

When your edition is final and you want readers to be able to order a
physical copy, the press can add an accessible "Order a print copy" link
to your book site. The print provider is the seller of record: they take
payment, calculate tax, print, ship, and own support — the press holds no
payment credential and sees no reader's address. Any support, privacy, or
returns page you do not host yourself is generated for you, disclosing who
the seller is and what they handle.

This has its own guide, including how to qualify an edition before you
sell it: [print ordering](https://github.com/clintecker/press/blob/main/docs/PRINT-ORDERING.md).

## Where to go next

- [Configuration reference](https://github.com/clintecker/press/blob/main/docs/CONFIGURATION.md) — every knob in `config/`.
- [Command reference](https://github.com/clintecker/press/blob/main/docs/REFERENCE.md) — every `press` target.
- [Installation](https://github.com/clintecker/press/blob/main/docs/INSTALL.md) — platforms, the container, and the public toolchain image.
- [Support](https://github.com/clintecker/press/blob/main/SUPPORT.md) — where to ask when a refusal is not self-explanatory.
