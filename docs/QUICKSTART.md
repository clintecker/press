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

- **Decisions only you can make** — your title, your author name, your
  words. The press never invents these.
- **Mechanical defaults** — layout, fonts, file names, the build order.
  The press owns these so your book matches every other book it makes.

Every step below is one or the other, and says which.

## 1. Install a toolchain (mechanical)

The press is a Python package that drives Pandoc and TeX. Install them
once for your platform, then let `press doctor` tell you what is ready.

On macOS:

```console
pip install "press @ git+https://github.com/clintecker/press@v1"
brew install pandoc poppler
brew install --cask mactex-no-gui
```

On Debian or Ubuntu, and for the container path (no local toolchain at
all), follow [the installation guide](https://github.com/clintecker/press/blob/main/docs/INSTALL.md);
it is the authority on packages per platform. Then, from anywhere, ask
the press what it sees:

```console
press doctor
```

`press doctor` names every dependency, tells missing apart from
present-but-broken, and says what each absence would cost. It is the one
authority on a machine's readiness; run it now and after any install
step. You do not need every optional tool to build your first book.

## 2. Scaffold a book (mechanical)

The directory name becomes the book's slug (its file-name identity), so
pick a short, lowercase, hyphenated name.

```console
press new my-first-book
cd my-first-book
```

You now have a complete, buildable book: a one-paragraph preface that
exists only so the empty book already builds and verifies, a
`config/metadata.yaml`, and the CI workflow that will build it on GitHub.
Nothing here is a placeholder you must decode; every default is a real,
working value you may keep or replace.

## 3. Enter the minimum identity facts (decisions)

Set the four facts only you can supply. You can edit
`config/metadata.yaml` directly:

```yaml
title: "My First Book"
subtitle: "And how it came to be"
author:
  - "Your Name"
description: >-
  One honest paragraph on what this book is.
```

or set them without touching YAML, which validates each value before it
writes:

```console
press config set subtitle "And how it came to be"
press config get subtitle
```

`press config list` shows every field you can set; `press config validate`
checks the whole configuration. Everything else in the metadata file is a
mechanical default with a comment explaining it. Two you will meet later, not now:

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

```console
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

```console
press check
```

`press check` runs the source, style, and jargon checks and tells you
exactly what to fix. When it passes, build every edition:

```console
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
| CI dies at "Initialize containers" | The private toolchain image is not granted to your repo | Grant it once (step 8) |

A refusal is the press protecting the book. None of these are dead ends;
each names its own fix.

## 7. View every generated edition (mechanical)

Everything the build made lands in `dist/`:

```console
ls dist/
```

You will find the PDF, the EPUB, the reading HTML, plain text, Word, the
source archive, and — if you built it — the site. To preview the reading
website locally before publishing, build the pages bundle and open its
`index.html`:

```console
press pages
```

## 8. Push, and the container boundary (mechanical, one grant)

Put the book on GitHub so its CI builds and publishes it:

```console
git init
git add -A
git commit -m "First book"
git remote add origin https://github.com/OWNER/my-first-book
git push -u origin main
```

The book's CI builds inside a private toolchain image. Each new repository
needs a one-time read grant to that image, done by hand under the
package's Manage Actions access settings; until then the build stops at
"Initialize containers" with a pull denial. This is the only cross-repo
step, and [the installation guide](https://github.com/clintecker/press/blob/main/docs/INSTALL.md)
explains it. After the grant, every push builds and verifies the book, and
publishes the site.

## 9. Optional: sell a print copy (decision)

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
- [Installation](https://github.com/clintecker/press/blob/main/docs/INSTALL.md) — platforms, the container, and the toolchain grant.
- [Support](https://github.com/clintecker/press/blob/main/SUPPORT.md) — where to ask when a refusal is not self-explanatory.
