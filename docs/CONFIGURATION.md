# Configuring a book

Everything the press knows about a book arrives through the book's
own files. This is the complete reference: every key the code reads,
sourced from the consumers, with what happens when a file or key is
absent. The general rule is graceful degradation: a required fact
refuses loudly with a locatable message, an optional fact defaults
or switches its feature off, and nothing fails silently.

The book root is the directory holding `config/metadata.yaml`; a
directory without that file is refused as not a book. Every YAML
file here must be a mapping (or, where stated, a list) at the top
level; a parse error refuses with the file and line.

For a first book, the
[quickstart](https://github.com/clintecker/press/blob/main/docs/QUICKSTART.md)
names the handful of facts you must supply and leaves the rest at their
defaults; this page is the exhaustive reference behind it.

You do not have to edit YAML by hand. `press config` reads and writes every
field below through the same typed model that validates a build, so an edit
is checked before it touches a byte and a rejected edit changes nothing:

```sh
press config list                       # every field, its type, and status
press config get commerce.print-ordering.seller-of-record
press config set print.paper cream      # refused unless white or cream
press config set keywords '["essays"]' --json   # lists/mappings as JSON
press config unset motto
press config validate                   # run every config validator
```

A field the CLI marks immutable (the v1 trim) or structured (the
authorities and index lists, managed by their workflows) is classified,
not writable; direct YAML editing remains available for experts and for
anything the CLI does not cover. The examples below are the schema of
record either way.

## config/metadata.yaml (required)

The book's identity, read once into a typed model (`bookmodel`) with
all problems collected and reported together. Pandoc also reads the
raw file directly, so standard pandoc metadata (`lang`, `keywords`,
`rights`) reaches the formats even where the model ignores it.

```yaml
title: An Example
subtitle: "or, A Subtitle; or, Another"
author: A. Author
date: 2026
copyright: "Copyright 2026 A. Author"
publisher: Example Press
publisher-place: Denver
description: One sentence for the landing page and stores.
slug: an-example
repository: https://github.com/you/an-example
site-url: https://you.github.io/an-example
verify-sentinels:
  - "a phrase that must survive into every artifact"
  - "another one"
verify-min-pages: 40
```

- `title`, `author`, and `slug` are required by the typed model on every
  load; `author` may be a single string or a list. `check` additionally
  requires `description`.
- `slug` must match `[a-z0-9][a-z0-9-]*` exactly: it becomes every
  artifact's basename, so dots, spaces, and shell- or HTML-active
  characters are refused.
- `date` is free text; the first plausible year in it becomes the
  EPUB date and the title page's roman numerals.
- `copyright`, `publisher`, and `publisher-place` are optional until
  `config/front-matter.yaml` exists, which makes them required (the
  generated front matter refuses to render without them).
- `repository` and `site-url` are optional; absent, the landing page
  omits the source paragraph and the public download links.
- `verify-sentinels` (default empty) are phrases proven present in
  the source and in every artifact. `verify-min-pages` (default 40)
  is the PDF's floor. Drafts may leave both loose; a tag build runs
  with `PRESS_RELEASE=1`, which refuses fewer than two sentinels or
  a floor under 24 pages.
- `trim` (optional mapping `{width, height}`, default 6 x 9) is
  validated: anything other than exactly 6 x 9 is refused in v1,
  because the design contract is built around that trim.

Print pack keys, all optional:

```yaml
print:
  paper: cream          # or white; sets per-page thickness
  # page-thickness: 0.0025   # inches; overrides paper if set
registrations:
  isbn:
    print: "9780306406157"   # or pending
    epub: "9780306406164"
  lccn: "2026000000"          # or pending
  issn: "0378-5955"           # or pending
  retail: false
```

- `print.paper` must be `white` or `cream` (default cream); an
  unknown stock is refused. `print.page-thickness` wins when set.
  Both feed the cover wrap's spine arithmetic.
- `registrations.isbn` must be a mapping of editions. The print
  ISBN drives the wrap's EAN-13 (check digit validated) and the
  colophon; `pending` or absent renders an honest placeholder. The
  epub ISBN becomes the EPUB identifier, verified in the OPF.
- `registrations.retail: true` turns missing or pending numbers
  into check failures; false leaves them advisory.

Direct print ordering (optional) adds a reader-facing "Order a print
copy" link to a provider-hosted checkout. The provider is the seller of
record and owns payment, tax, fulfillment, and support; this block holds
only URLs and a name, never a credential or a price.

```yaml
commerce:
  print-ordering:
    enabled: true
    edition: paperback
    storefront-url: "https://www.lulu.com/shop/..."
    seller-of-record: "Lulu"
    support-url: "https://example.test/support"   # optional; omit to generate
    # privacy-url / refund-url omitted -> press generates those pages
    policies:                                      # optional publisher text
      privacy: "We keep no reader data; the provider handles your order."
```

- When `enabled`, the landing page generates an accessible, script-free
  CTA linking to `storefront-url`, disclosing the `seller-of-record`
  before the reader leaves the site, alongside the three policy links.
- Each policy link (`support-url`, `privacy-url`, `refund-url`) is
  **optional**: give a URL to link your own hosted page, or omit it and
  press generates an honest page on the book site (`support.html`,
  `privacy.html`, `refunds.html`) that discloses the seller of record and
  what they handle. `policies.{support,privacy,refund}` appends your own
  text to a generated page; press never invents legal terms.
- `storefront-url` and any policy link you supply must be `https`;
  `press check` refuses a non-HTTPS origin, an unnamed seller, an unknown
  key, or anything that looks like a secret.
- Disabled or absent: no CTA is generated, and `press verify` refuses a
  stray CTA or a missing generated policy page.
- A release of an ordering-enabled book fails closed (`press all` under
  `PRESS_RELEASE=1`, advisory otherwise) unless its exact edition passed a
  physical qualification recorded in `config/qualification.yaml`.

Absent file: refusal. There is no book without metadata.

## config/qualification.yaml (optional)

The record that an ordered copy of a named edition passed every physical
inspection point. Required only for a book that enables print ordering;
the release gate refuses to advertise a copy no one has verified a
provider can print.

```yaml
schema_version: 1
inspections:
  - provider: lulu                # a key from the provider record
    product_id: "PB-BW-6x9"
    region: US
    edition_id: "<the edition_id the copy was ordered against>"
    inspector: "Your Name"
    results:
      content: pass
      pagination: pass
      trim: pass
      bleed: pass
      spine: pass
      barcode: pass
      color: pass
      paper: pass
      binding: pass
      packaging: pass
      tracking: pass
```

- `edition_id` scopes the inspection to an exact edition; a
  production-affecting change mints a new identity, so the old inspection
  becomes stale and the release gate fails until a new copy is inspected.
- Every checklist point must be `pass`; a single failure cannot qualify.
  See [provider qualification](https://github.com/clintecker/press/blob/main/docs/PROVIDER-QUALIFICATION.md) for the checklist and the
  researched providers.

Absent file: no qualification, so an ordering-enabled release fails closed.

## config/house-rules.yaml (optional)

The book's own editorial law, layered over the press's universal
checks.

```yaml
banned-patterns:
  "\\bvery unique\\b": "very unique (unique does not grade)"
jargon-allow:
  - leverage
audit-dirs:
  - appendices
```

- `banned-patterns` maps a regex to the label reported on match; an
  invalid regex is refused by name. Applied to manuscript prose by
  the style audit.
- `jargon-allow` lists watchlist terms this book may use; matches
  are case-folded. The watchlist itself lives in the press's jargon
  skill and is not configurable here.
- `audit-dirs` adds directories (relative to the root) to the
  default `book/` for markdown discovery.

Absent file: no book-specific rules; the universal checks still run.

## config/index-terms.yaml (optional)

Curated subject-index terms, a list of entries. The index appendix
regenerates on every build; locations are never stored.

```yaml
- term: Margins
  match: [margin, margins]
- term: Spine width
  match: [spine width, spine arithmetic]
```

- `term` is the printed label; `match` lists the alternatives, each
  matched on word boundaries against markup-stripped chapter text.
- A curated term that matches nothing in the text fails the build by
  name; silence is not allowed. Fix the patterns or remove the term.

Absent file: no subject index is generated.

## config/authorities.yaml (optional)

The table of authorities: a list of entries, each binding an exact
text fragment (a claim of fact) to the source that warrants it.
Populate it with the `authorities-research` workflow.

```yaml
- claim: "the Model T sold for $260 in 1925"
  authority: "Ford Motor Company annual report, 1925"
  url: https://example.org/ford-1925
  file: book/chapters/03-price.md
  note: "list price, not average transaction price"
```

- `claim` (required): the fragment, matched whitespace-normalized
  against the manuscript.
- `authority` (required): the source.
- `file` (optional but preferred): the book-relative path pinning
  the claim to one chapter.
- `url` and `note` (optional): a durable locator and a dry aside,
  both rendered in the companion.

The companion (`dist/<slug>-sources.md`) regenerates on every build.
The run fails, with every problem listed, when an entry is
malformed, a claim is duplicated, a claim's sentence has left the
text, a fragment matches more than one place (lengthen it or declare
`file:`), or a claim has moved out of its declared file.

Absent file: no companion, and the `sources` artifact is skipped.

## config/aesthetic.yaml (optional)

The book's visual identity, merged over the house default
(`data/aesthetic-house.yaml`, the Victorian idiom). The merge is a
top-level replace: any section the book names replaces the house
section wholesale, so restate a whole section when you touch it.
Draft the file by interview (the book-aesthetics skill) or with
`press aesthetic "<brief>"`; `press aesthetic` shows the effective
merge.

```yaml
name: "1970s pulp paperback"
register: >-
  Lurid, confident, mass-market; the design of a book meant to be
  read to pieces.
cover:
  medium: painted illustration, airbrushed
  field: full-bleed scene
  ink: "process color"
  type-treatment: condensed grotesque, tightly set
  ornament: none
  emblem: publisher colophon, bottom spine
plates:
  medium: halftone reproduction
  composition: single subject, high contrast
logomark:
  tradition: midcentury paperback colophon
portrait:
  style: press-kit photograph, high grain
web-palette:
  cloth: "#8a2f1d"
  cloth-deep: "#6e2415"
  foil: "#d9a441"
  foil-bright: "#e8bd6a"
  foil-deep: "#a87a2a"
  paper: "#f6f1e4"
  paper-warm: "#efe7d2"
  ink: "#221f1a"
  ink-soft: "#4f483c"
web-palette-dark:
  cloth: "#1b0d09"
  paper: "#1e1b15"
  paper-warm: "#27231b"
  ink: "#e9e1cd"
  ink-soft: "#b6ac94"
typography:
  web-family: 'Georgia, "Times New Roman", serif'
  pdf-family: ""        # empty keeps the packaged Libertinus
book-colors:
  ink: "171717"
  muted: "5C5C5C"
  accent: "8A2F1D"
  link: "6E2415"
```

Two kinds of keys live here:

- Prose sections (`name`, `register`, `cover` with `medium`,
  `field`, `ink`, `type-treatment`, `ornament`, `emblem`; `plates`
  with `medium`, `composition`; `logomark.tradition`;
  `portrait.style`) are prompt material: every art commission reads
  them, the build machinery does not.
- Programmatic keys are consumed directly. `web-palette` and
  `web-palette-dark` substitute hex values into the reader and
  landing-page stylesheets (light tokens before the dark-scheme
  seam, dark tokens after it). `typography.web-family` replaces the
  house web font stack; `typography.pdf-family` names a LaTeX main
  font, with the empty string keeping the packaged Libertinus.
  `book-colors` (`ink`, `muted`, `accent`, `link`, hex without `#`)
  become the PDF's TeX colors; only the keys present are emitted,
  written to `build/aesthetic.tex` and included optionally.

Craft laws are not configurable: the exact title and author text
appear verbatim on art, cover plates are flat (no mockups), print
interiors are single ink, and the trim is the trim. The aesthetic
styles them; it does not repeal them.

Absent file: the house Victorian idiom applies, byte for byte.

## config/front-matter.yaml (optional)

Its presence is the switch: when the file exists (and no
`tex/title-page.tex` overrides it), the press generates the PDF
title page, copyright page, and surrounding pages from config, and
requires `title`, `author`, `copyright`, `publisher`, and
`publisher-place` in the metadata. Every key below is optional; an
absent key simply does not render its block.

```yaml
edition-note: first edition
dedication: "For the compositors."
epigraph:
  quote: "Whatever is worth doing at all is worth doing well."
  attribution: Lord Chesterfield
acknowledgements: >-
  The author thanks the readers of the early drafts.
rights-notice: >-
  No part of this book may be reproduced without permission.
manufacture: Printed in the United States of America.
colophon-note: Set in Libertinus Serif.
contact: press@example.org
motto: festina lente
```

- `edition-note` falls back to the metadata `date` before its first
  comma, lowercased.
- `epigraph` renders only when `epigraph.quote` is present;
  `attribution` sets under the quote.
- `dedication` and `acknowledgements` each add their own page.
- `rights-notice`, `manufacture`, `colophon-note`, `contact`, and
  `motto` are colophon lines, each independently omissible.

The title page stacks the subtitle's OR clauses: the metadata
subtitle splits on `or,` seams, and each clause after a seam gets
its own small-caps "or," line. Cover plate, press logo, and
registration lines come from the assets and metadata, not this file.

Absent file: no generated front matter; the formats build with
pandoc's plain title handling.

## tex/title-page.tex (optional)

The whole-cloth override: cover plate, title page, and colophon,
hand-authored. When it exists the generated front matter stands down
entirely, and the design is the book's own. A print-only variant at
`tex/title-page-print.tex` replaces it for the print interior so the
two never stack. Keep the image-height cap from the template; a
figure taller than the text block ships empty pages forever.

## Assets (all optional)

- `assets/cover.jpg`: the cover plate on the PDF, the cover block on
  the HTML, site, and landing page. Absent, every consumer drops its
  cover block cleanly.
- `assets/press-logo.png`: the imprint device on the colophon and
  the landing page. Absent, omitted.
- `assets/woodcuts/*.jpg`: interior plates (JPEG on purpose; PNG
  barely compresses engraving grain). Any plate on disk never
  referenced by the manuscript fails `check`. The List of Plates
  appears only when at least one exists.
- `art/author-photo.jpg`: makes the portrait commission engrave the
  actual author instead of an invented one. Not a build input.
- `assets/web/reader.css`: replaces the house reader stylesheet
  entirely.
- `assets/web/extra.css`: appended last, winning the cascade on both
  the reader and the landing page.

## tests/known-bad/ (optional)

Fixtures proving the book's own house rules can fail. Each fixture
is a markdown file that must be rejected on every build; it declares
the rule it exists to trip with a comment anywhere in the file:

```markdown
This sentence is very unique. <!-- expect: very unique -->
```

The checker harness runs the style audit and the jargon lint over
each fixture and requires a diagnostic containing the declared rule
(case-insensitive). A fixture without an `expect:` comment must
simply be rejected by some checker. A fixture nothing rejects fails
the build: a rule that cannot fail is not a rule.

Absent directory: only the press's universal known-bad fixtures are
proven.
