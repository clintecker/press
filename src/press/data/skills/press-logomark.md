---
name: press-logomark
version: 1.0.0
description: Use and produce the press logomark (imprint device) correctly across the colophon, landing page, and any new marks; sizing, format, and the restraint rules that keep an imprint device from becoming a logo.
compatibility: any-agent
---

# Press logomark

## Purpose

The logomark is an imprint device in the printer's-mark tradition: it
certifies the maker, it does not advertise. It appears small, late, and
without comment.

## Where it appears

- The colophon page of the print PDF, about 2.2in wide, centered, below the
  rights text. It ends the front matter; nothing follows it on the page.
- The landing page footer, small, above the structured imprint block
  (publisher, place, copyright, date drawn from metadata).
- Nowhere else. Not on the cover, not in chapters, not in the EPUB body.
  An imprint device that appears often stops being a certification.

## The file

One file: `assets/press-logo.png` in the book repository. PNG with
transparency (it sits on paper-colored and dark backgrounds both), source
around 900px wide, optimized. Unlike engravings, flat line-art marks
compress well as PNG; this is the one deliberate exception to the
JPEG-for-woodcuts rule.

## Producing a new mark

- Brief it as a printer's device: monogram or emblem, single ink, engraved
  line work, contained silhouette (roundel, shield, or lozenge), with the
  press name in a band or exergue if text is wanted.
- Text in the mark must be named verbatim in the prompt and proofread at
  final size; a misspelled imprint device certifies carelessness.
- It must survive at 0.5in wide in one ink. If it needs color or size to
  read, simplify the drawing, not the reproduction.
- Test on both the colophon (light) and the dark-mode landing footer before
  adopting it.
