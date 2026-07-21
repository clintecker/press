# Printing a book at Lulu

A top-to-bottom walk from the two files press builds to a copy in your hands.
Lulu is press's primary print route: you upload an interior PDF and a cover
PDF, order one copy, and inspect it. This page is the exact click path, the
Lulu settings that must match your config, and the file notes Lulu shows (all
handled or harmless).

::: {.lede}
You upload two files: the interior (`dist/<slug>-interior.pdf`) and the cover
wrap (`dist/<slug>-coverwrap.pdf`). Press builds both; Lulu prints and ships.
:::

## Build the two files

From inside the book, one command builds the interior and the cover wrap and
verifies both:

```sh
press verify-print
```

It writes:

- `dist/<slug>-interior.pdf` — the typeset 6×9 interior.
- `dist/<slug>-coverwrap.pdf` — the full cover: back, spine, and front in one
  page, with 0.125in bleed. Built only when `assets/cover.jpg` exists.

The spine width is computed from the page count and the paper you set, not
typed by hand. Set the paper first so the spine math is right:

```sh
press config set print.paper cream    # or: white
```

## Choose the right Lulu product

This is the step that trips people up. Lulu's cover templates differ by
product, and **press builds a flat wrap sized for one of them**:

::: {.callout}
**Press's cover wrap is for Paperback, Perfect Bound.** For a 6×9 book its
dimensions are the full cover — back, spine, front, plus bleed — with no
flaps. That is exactly what Lulu's paperback perfect-bound cover expects.
Pick that product and `dist/<slug>-coverwrap.pdf` drops in without resizing.
:::

::: {.callout .tip}
**Hardcover is supported — select it.** For a case wrap or a linen dust
jacket, set the binding and provider and press builds the right geometry (the
board turn-in for a case wrap, the flaps for a jacket), sized to Lulu's own
formulas:

```sh
press config set print.provider lulu && \
press config set print.binding casewrap    # or dust-jacket
```

Then pick the matching hardcover product on Lulu. See
[trim & binding](https://github.com/clintecker/press/blob/main/docs/PRINT-FORMATS.md)
for the full set of choices.
:::

On the first screen, choose **Print Your Book** (upload and buy copies).
**Publish Your Book** is for listing in Lulu's retail and distribution
channels — a later step, and a separate decision.

## The Lulu settings that must match your config

Lulu asks for the book's physical spec before you upload. Each must match
what press built, or the files will not fit:

| Lulu setting | Set it to | Why |
| --- | --- | --- |
| Page size / trim | your `print.profile` trim (6 × 9 default) | the profile sets the interior geometry |
| Binding | match your `print.binding` (paperback default) | the wrap is sized for it |
| Interior color | Black & white | press interiors are single-ink |
| Paper | match your `print.paper` | the spine width depends on it |
| Cover finish | Glossy or Matte | your choice; no file impact |

If you pick a different paper at Lulu than the `print.paper` in your config,
the real spine will differ from the one press drew, and the spine text will
sit off-center. Keep them the same.

## Upload, in order

1. **Interior.** Upload `dist/<slug>-interior.pdf`. Lulu renders a preview
   and runs its file checks (see the warnings below).
2. **Cover.** Choose to upload a one-piece PDF cover and upload
   `dist/<slug>-coverwrap.pdf`. Lulu overlays its safety and barcode guides;
   confirm the spine text sits within the spine and nothing important falls
   in the 0.5in safety margin.
3. **Barcode.** If you have a print ISBN in `registrations.isbn.print`, press
   draws a real EAN-13 on the back; leave Lulu's own barcode off. With no
   ISBN, press draws an honest placeholder — let Lulu add its barcode, or add
   your own later. If you own an ISBN prefix (bought once from your agency),
   `press isbn assign print` mints and records the next one for you.

## File warnings — press handles these for you

Lulu used to flag two things on a press interior: *transparency* (the press
logomark is stored as ink on a transparent background) and *images over 600
PPI* (that 1024px logo at 1.7in was ~602 PPI). The `print` build now runs a
**print-safe pass** (`press.print_safe`) that flattens every image onto white
and caps resolution, so a current `press verify-print` interior triggers
**neither** warning — nothing to do.

::: {.callout .tip}
**If you do see them,** you are looking at an older upload or a book whose
hand-authored title page still points at the un-flattened logo. Rebuild with
`press verify-print` and re-upload the interior; the warnings clear. (A book
with a custom `tex/title-page-print.tex` should point its logo at
`build/print-assets/`.)
:::

You may also see an informational **"a white bleed margin was added"** note if
your interior has no full-bleed images — that is expected and harmless; press
interiors keep their art inside the margins.

## Order one copy — the golden copy

Choose **Print Your Book**, set the quantity to **1**, ship it to yourself,
and place the order. This is the capped, real spend that proves paper, trim,
spine, binding, barcode, and color on a physical object — the qualification
step in
[print ordering](https://github.com/clintecker/press/blob/main/docs/PRINT-ORDERING.md).
When it arrives, inspect it against the eleven-point checklist in
[provider qualification](https://github.com/clintecker/press/blob/main/docs/PROVIDER-QUALIFICATION.md)
and record the result in `config/qualification.yaml`.

## Troubleshooting

| Lulu says | Cause | Fix |
| --- | --- | --- |
| Cover is the wrong size | Lulu product ≠ your `print.binding` | Match the binding (or set `print.binding`), rebuild |
| Spine text is off-center | Lulu paper ≠ your `print.paper` | Match the paper, rebuild |
| Transparency detected | An old upload (print-safe now flattens) | Rebuild with `press verify-print`, re-upload |
| Images over 600 PPI | An old upload (print-safe now caps PPI) | Rebuild with `press verify-print`, re-upload |
| No cover was built | No `assets/cover.jpg` | Add cover art, then `press coverwrap` |
| Fonts not embedded | Not from a press build | Rebuild with `press verify-print` |
