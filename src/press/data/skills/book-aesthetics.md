---
name: book-aesthetics
version: 1.0.0
description: Elicit and write a book's visual identity into config/aesthetic.yaml - the schema, the interview questions that surface an author's taste, and worked examples from Victorian treatise to pulp paperback. Use when an author wants their book to look like something, before running art-direction.
compatibility: any-agent
---

# Book aesthetics

## Purpose

A book's look is a book fact, and book facts live in config. The
`config/aesthetic.yaml` file states the visual identity every art
commission applies: the cover's grammar, the plates' medium, the
imprint's tradition, the register that binds them. Absent the file,
the house default applies (a Victorian treatise; see the press's
`aesthetic-house.yaml`). This skill is for producing that file well,
usually by interviewing the author.

## The schema

Top-level sections replace the house default wholesale when present.
Values are prose: they become prompt material for image models, so
concrete craft language beats adjectives.

```yaml
name: short label for the identity
register: >-
  The tonal contract every piece of art signs. One or two sentences.
cover:
  medium: what the cover physically is (cloth, glossy paperback, matte board)
  field: the ground: color, texture, finish
  ink: how text and ornament are rendered (foil, offset ink, embossing)
  type-treatment: how the title, subtitle, author are set
  ornament: borders, rules, flourishes, or their deliberate absence
  emblem: the central imagery and its style
plates:
  medium: the illustration technique, named as a craftsman would
  composition: rules for what a single plate carries
logomark:
  tradition: what kind of mark the imprint device is
portrait:
  style: how the author appears
web-palette:            # the reading site and landing page, light theme;
  paper: "#f8f5ef"      # keys are the reader stylesheet's CSS tokens:
  ink: "#2a2622"        # paper, paper-warm, ink, ink-soft, cloth,
  cloth: "#1d3a2f"      # cloth-deep, foil, foil-bright, foil-deep,
  foil: "#b08d3e"       # hairline, link, ornament
  link: "#1d5c3f"
web-palette-dark:       # the same tokens for the dark theme; omit to
  paper: "#161513"      # keep the house dark values
  ink: "#ded9d0"
typography:
  web-family: CSS font stack for the reading surfaces
  pdf-family: a LaTeX-known family name for the book's body face
book-colors:            # the PDF's inks
  ink: "#1a1a1a"        # body ink
  muted: "#5a5a50"      # captions and folios
  accent: "#7a2d26"     # rules and display accents
  link: "#1d5c3f"       # hyperlink ink
```

The page look is as configurable as the art: `web-palette` and
`web-palette-dark` restyle the reading site and landing page,
`typography` sets the web stack and the PDF body face, and
`book-colors` sets the PDF inks. A brief that names a period or mood
should draft all four; leaving them out keeps the Victorian house
palette, which contradicts most briefs.

What is NOT configurable: text named verbatim, flat cover plates (no
mockups), single-ink print interiors, print resolutions, the trim.
Those are craft and pipeline law; the aesthetic styles them, it does
not repeal them.

## The interview

Ask, in this order, and push past adjectives to referents:

1. Point me at three covers you wish this book sat beside. What do
   they share?
2. When a reader holds the book, what era and shelf does their hand
   believe? (A real shelf: drugstore spinner rack, university press,
   airport bestseller wall.)
3. What does the cover physically feel like in the mind's eye: cloth,
   lamination, uncoated card?
4. Is the title doing the selling, or is the image? Which is louder?
5. What must the interior art never do? (Photographs? Color? Humor?)
6. Read back a drafted `register` sentence and ask what word is wrong.

Write the file, run `press aesthetic` to show the effective merge, and
read it back to the author before any commission spends money.

## Worked examples

A 1970s pulp science-fiction paperback:

```yaml
name: "1970s pulp science fiction"
register: >-
  Breathless and sincere; the cover promises more than any book could
  deliver, and means it.
cover:
  medium: glossy mass-market paperback, slight ink bloom on cheap stock
  field: airbrushed nebula gradient, deep violet into hot orange
  ink: solid process colors, no foil
  type-treatment: >-
    Title in chrome-effect extended display capitals, arched; author
    small at the foot in white; a burst blurb top right.
  ornament: none; the painting runs full bleed
  emblem: >-
    A central painted scene in the manner of a gouache paperback
    illustrator: hardware rendered lovingly, figures small and heroic.
plates:
  medium: stark black-and-white ink illustration, heavy blacks, zip-a-tone dots
  composition: one wonder per plate, seen from a human vantage
logomark:
  tradition: a compact space-age monogram in a circle, single ink
portrait:
  style: halftone photograph look, back-of-jacket, confident and dated
```

An educational textbook: field flat and pale, type-treatment quiet and
gridded, emblem a labeled diagram, plates as clean labeled figures,
register patient and exact. A romance novel: field soft-focus painted
scene, type-treatment flowing script foil, register ardent without
irony. The grammar of the schema holds; only the values change.
