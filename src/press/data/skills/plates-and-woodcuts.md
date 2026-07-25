---
name: plates-and-woodcuts
version: 1.0.0
description: Commission, prepare, caption, and place interior illustration plates (the house woodcut idiom) so they survive every output format, appear in the List of Plates with working links, and never trigger the empty-page LuaLaTeX failure.
compatibility: any-agent
---

# Plates and woodcuts

## Purpose

Interior plates carry the book's wit where prose should not. A good plate
illustrates an idea sideways: literal enough to recognize, absurd enough to
reward a second look. This skill covers commissioning them, preparing the
files, and the placement rules the pipeline enforces.

## Commissioning

- Write the prompt as a period engraver's brief: subject, composition,
  "wood engraving with dense hatching, single ink, no gray washes", and the
  emotional register ("solemn workers regarding a machine with suspicion").
- One idea per plate. A woodcut arguing two points argues neither.
- The joke belongs in the subject; the style stays dead serious. A
  ridiculous scene engraved earnestly is the house voice.
- Ask for a landscape or portrait composition deliberately; a square plate
  wastes the trim.
- State the drawing discipline or the model will improvise it: correct
  architectural perspective, level floor, true verticals, one
  consistent vanishing point, eye-level or gently raised vantage. The
  skew of a careless plate reads as error, not style.
- State the presentation: the image fills its rectangle to the edge (or
  sits in one plain thin rule); never a torn-paper mat, never a tilted
  or rotated "print" laid on a background, never drop shadows.
- Placard and signage text renders letter for letter WITHOUT quotation
  marks around it; models add quotes when the prompt quotes.
- The shop's machines are compact brass apparatus in the
  nineteenth-century instrument tradition: armatures, gears, a lens
  where sight is needed. Never humanoid skeletal robots; an android in
  a woodcut breaks the century.

## File preparation

- `assets/woodcuts/*.png`, descriptive kebab-case names; the filename is
  forever once referenced from a chapter.
- Take every plate through `press art accept <file> --as plate:<name>`. The
  intake keeps it as an **alpha PNG master** -- ink on transparency, the
  light ground keyed out with a luminance key -- so one graphic composites
  onto any surface: the white interior, a coloured cloth cover, a
  transparent web panel. Never hand-ship a baked-white JPEG; the intake
  segments a baked delivery for you. A plate that arrives already on
  transparency keeps its mask.
- Grayscale or near-grayscale; a colorful woodcut breaks the plate section
  (a colour interior, #214, is the exception and keeps its hues).
- `press art enhance` finishes a master (upscale, quantize, compress) while
  keeping its alpha, so the mask survives to the reader edition.

## Placement

- Place plates in chapter Markdown with a standard image line and a caption
  that reads as a Victorian plate legend: quiet, italic, slightly formal.
- The caption is the alt text and the List of Plates entry; write it to
  stand alone there.
- Keep any plate's rendered height at or under 7.1in on a 9in trim. Taller
  images plus a baseline exceed the text block and LuaLaTeX ships empty
  pages forever, silently.
- The List of Plates generates itself when woodcuts exist; never hand-list
  plates. Plate links are verified against the pages that actually hold
  images on every PDF verify (the hypcap scar), so a broken destination
  fails the build rather than shipping.
- Plates land in every image-capable format automatically (PDF, EPUB, HTML,
  DOCX, reader site, Pages). The DOCX and site verifiers count embedded
  images against `assets/woodcuts/`; removing a plate from prose without
  removing the file will fail verification, which is correct.
