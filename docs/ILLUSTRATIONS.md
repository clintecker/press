# Illustrations

An illustration is a [cover style](cover-styles.html) pointed inward. It prints
in a **single ink** — the interior print law, of which a full-colour cover is
the one exception — carries no lettering, and lands as a **plate**: a figure the
build sets into the text and lists in the plates. You draw it from a subject, or
from **source material you supply** — a photograph you took, a rough map, a
sketch — redrawn into the book's own hand. Each sample below is a different
subject in a different ink, to show the range a medium covers; a real book prints
all of its plates in its own single ink.

<!--ILLUSTRATION-STYLES-->

## Commissioning one

Name the plate and, if you like, a style and a subject:

```sh
press illustrate limpet --style wood-engraving --subject "a limpet on a wet rock"
press illustrate coast-map --style engraved-map --from maps/rough-sketch.png
press illustrate --list
```

`press illustrate` writes the art to `build/illustrations/` and prints the one
command that installs it — `press art accept build/illustrations/<name>.png --as
plate:<name>` — the same intake every plate passes through, which **greys it to
the single interior ink** and records it. Then reference it in your manuscript
like any figure. A book's default style comes from `config/aesthetic.yaml`
(`plates: {style: wood-engraving}`); `--style` overrides. With no image-model
key set, `press illustrate` prints the prompt instead, so the press stays
offline by default.

## Source material

The strongest illustrations start from something real. Give `press illustrate`
a photograph or a map with `--from`, and the style redraws it — keeping the
composition, changing the medium:

```sh
press illustrate harbour --style figure-from-photo --from photos/harbour.jpg
press illustrate parish --style engraved-map --from maps/ordnance.png
```

Your snapshot becomes a wood engraving that belongs in the book; a real map
becomes an engraved map in the book's ink. The `figure-from-photo` style needs a
`--from`; every other style accepts one and will lean on it.

Each pair below is a real, public-domain photograph and the plate the engine
drew from it — the composition kept, the medium and the ink the book's:

<!--FROM-DEMO-->

## What does *not* belong here

**Data figures — bar charts, line graphs — are not illustrations.** An image
model would invent the numbers. Chart a real data file, rendered exactly, in the
book's palette; keep `press illustrate` for illustrative art. (The data-figure
path is the natural next step for this system.)

## Building your own

Add `config/illustration-styles.yaml` to your book with the same shape as the
house library, and your styles merge over it:

```yaml
styles:
  my-plate:
    name: "My plate"
    note: "what it looks like, in a line"
    source: required     # optional: this style only makes sense with --from
    prompt: |
      A plate of {subject}, drawn as ... in {ink} on {paper}.
```

A template may use `{subject}`, `{ink}` (your interior ink), and `{paper}`; the
press adds the wordless, single-ink guardrail. Then `press illustrate fig1
--style my-plate`.

## Finishing a plate for print and web

A commissioned plate is a modest raster; the print interior wants it large and
crisp, the reader wants it small and clean. `press art enhance` does both in
three stages matched to the art's own grain:

```sh
press art enhance                         # finish every plate under assets/woodcuts/
press art enhance assets/woodcuts/shop.jpg  # or just one
```

1. **Upscale** through a Real-ESRGAN model chosen for the medium in
   `config/aesthetic.yaml` -- a line model (remacri) for an engraving, which
   keeps the hatching crisp instead of inventing the smooth gradients a photo
   model would. The upscaler is an external tool, detected not bundled: install
   [Upscayl](https://upscayl.org) or a standalone `realesrgan-ncnn-vulkan` and
   `press doctor` will report it. Absent, the command still runs -- it resamples
   instead of upscaling, so the rest of the win lands.
2. **Resample** to a print-grade long edge (2400px by default; `--max-edge`).
3. **Quantize** to a small palette (`--colors`, default from the medium) and
   write a lossless PNG. An engraving is a few grays, so this is visually
   lossless and turns a multi-megabyte truecolor image into a small one -- small
   enough that a plate ships as a lossless PNG rather than a lossy JPEG.
