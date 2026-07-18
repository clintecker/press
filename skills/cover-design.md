---
name: cover-design
version: 1.0.0
description: Direct, generate, and place book cover art for press books. Covers the house Victorian cloth idiom, the trim and text-block constraints that make LuaLaTeX loop forever when violated, file format choices for engraved textures, and where a cover plugs into each output format.
compatibility: any-agent
---

# Cover design

## Purpose

A cover is the one page every format shares and the only page most readers
judge before reading. This skill exists so cover work starts from the house
idiom and the known constraints instead of rediscovering either.

## The house idiom

The press look is Victorian bookcloth: a solid cloth-colored field, a
gilt-style ruled border, the full triple title set in stacked centered caps,
one central engraved emblem, the author's name low and quiet. The long
subtitle is a feature; a Victorian title page treats the subtitle as
argument, not decoration. Vary the cloth color per book; keep the grammar.

## Directing an image model

- Describe the object, not the style label: "a cloth book cover, deep green,
  ruled gilt border, central woodcut emblem of X, stacked centered
  letterpress caps" beats "Victorian style cover".
- Name every line of text the image must carry, verbatim and in reading
  order. Text the prompt leaves implicit will be misspelled or invented.
- Ask for the front board only, straight-on, no perspective, no mockup, no
  drop shadow; the layout wants a flat plate.
- Engraved emblems should be described as woodcut or steel engraving with
  hatching, never "detailed illustration"; that phrase produces gradients,
  and gradients read as digital.

## Constraints that are scars, not taste

- On a 6 x 9 trim the text block is 7.5in tall. An included image whose
  height plus baseline exceeds it makes LuaLaTeX ship empty pages forever,
  silently, at 100% CPU. Cap the cover plate at 7.1in tall (5.6in wide) in
  the title-page TeX, and never stack a third `titlepage` environment.
- Save covers as JPEG. Engraving grain and cloth texture barely compress in
  PNG; a q85-q90 JPEG is a fraction of the size with no visible loss at
  print resolution.
- Target roughly 2:3 aspect to match the trim; the EPUB cover and landing
  page use the same file uncropped.

## Where the file plugs in

One file: `assets/cover.jpg` in the book repository. The pipeline wires it
everywhere itself: EPUB cover, an embedded frontispiece in the single-file
HTML, the reader site, and the Pages landing card. The print PDF is the one
manual site: the book's `tex/title-page.tex` includes it as the
frontispiece plate, which is where the 7.1in cap lives. No other file or
config mentions the cover; keep it that way.
