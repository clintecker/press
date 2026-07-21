# Print profiles and provider specs — v2 design

Internal design record for the v2 work that makes trim, binding, cover
material, and page size configurable (#172), and does so correctly for Lulu,
KDP, and IngramSpark at once. Not published to the docs site; it lives in the
repo and issues like the direct-ordering plan.

## The goal, stated as a failure to avoid

A book is *designed* once (its interior look) and can be *manufactured* by
any of several print-on-demand vendors. The failure to avoid: baking one
vendor's manufacturing numbers into the book's design, so that a 6×9
paperback laid out for KDP prints with the wrong spine at Lulu. That is not
hypothetical — it is the current state. `gen_coverwrap` hardcodes KDP's
per-page calipers (`white 0.002252, cream 0.0025`) and a single perfect-bound
wrap formula, so a Lulu- or Ingram-printed book gets KDP's spine math.

## What actually varies across providers (researched, sourced)

The spine caliper and the cover-wrap geometry are the big per-vendor
variables, and they do not even share a formula *shape*:

| Dimension | Lulu | KDP | IngramSpark |
| --- | --- | --- | --- |
| Spine formula shape | single divisor `pages/444 + 0.06` (PB, stock-independent); **lookup table** (HC) | **constant per stock** `pages×caliper (+0.06 PB)` | **PPI table per stock** `pages/PPI` |
| White caliper | ≈0.002252 | 0.002252 | **0.001953** (50#) / 0.002653 (70#) |
| Cream caliper | via divisor/table | 0.0025 | 0.002252 |
| Cover safety margin | 0.5″ | 0.25″ (0.375″ w/ bleed) | 0.125–0.25″ |
| Hardcover wrap/turn-in | 0.75″/edge | ≈0.591″/side\* | 0.625″ fold |
| Dust jacket | yes (linen case) | **none** | yes (jacketed/cloth) |
| Saddle-stitch / coil | yes | no | no |
| Min pages | PB 32 / HC 24 | PB 24 / HC 75 | 18 (all) |
| Max pages | HC table → 800 | PB 828 / HC 550 | channel-dependent |
| Spine-text threshold | 80 pp | 79 pp | 48 soft / 18 hard |
| Barcode zone | optional, unspecified | 2″×1.2″ bottom-right | **mandatory** 1.75″×1.0″ (EAN) |
| Even-page rule | none | even only | stored ÷2, blank last page |

\* KDP hardcover wrap constants are from its calculator, not a text spec —
confirm before encoding. Full source URLs at the end.

**Shared (model once):** 0.125″ cover bleed; the paperback full-cover shape
`(2·trim_w + spine + 2·bleed) × (trim_h + 2·bleed)`; no bleed on the
bind/gutter edge; the 300-PPI / embedded-fonts / flattened-transparency /
integrated-cover rules; the general `spine = pages × caliper` relationship
(only the caliper and the `+0.06` allowance vary).

## The model: four orthogonal layers that compose

A build's physical form is the composition of four independent choices, not
one monolithic profile. This is what keeps the design sealed while the
manufacturing numbers stay per-vendor.

1. **Design profile** — the interior *look*: trim, interior geometry
   (margins, gutter growth), figure cap, typography. Sealed and versioned by
   design-major (#172): appearance cannot change without a version bump. This
   is what v1 froze, and what the byte-identical geometry projection already
   ships. *Independent of who prints it*, constrained by manufacturing only
   through the safety margin the text block must respect, bleed on full-page
   art, the caliper→spine feedback (page count sets spine), and the image
   resolution floor.
2. **Binding** — cover *topology*, provider-independent: perfect-bound
   (spine + gutter), saddle-stitch / coil (no spine, no gutter), hardcover
   case wrap (board turn-in + hinge + overhang), dust jacket (flaps +
   flap-fold + connecting strip). Determines *which* geometry formula runs.
3. **Material** — cover *treatment*: paperback, printed case laminate, or
   **linen/cloth** — where the printed cover is *suppressed* because the cloth
   is the finish (only a dust jacket is printed). This is the fix for the
   "don't bake a cloth field into a linen cover" scar.
4. **Provider spec** — the manufacturing *numbers*: the caliper model (its
   shape and the stocks it offers), the `+0.06` allowance, cover safety, the
   wrap/turn-in and flap dimensions per binding, the barcode zone, page
   bounds and even-page rules, and the trim×binding availability matrix. One
   per provider. **The verifier's tolerances come from here** — selecting a
   provider selects the verification contract (#172).

### Composition and precedence

A book selects: a design profile (or just a trim, which maps to one), a
binding, a material, a provider, and a paper stock. Resolution is
deterministic, no silent fallback:

- **Interior geometry** ← design profile, only.
- **Spine width** ← provider spec's caliper model, applied to the binding
  (saddle/coil → no spine) and the page count and paper.
- **Cover wrap size and panels** ← binding topology, with the provider spec's
  wrap/turn-in/flap/safety numbers.
- **Cover treatment** (cloth field, printed-cover suppression) ← material.
- **Legality** (is this trim offered in this binding at this provider? is the
  page count in range? even-page rule?) ← provider spec, checked *before*
  rendering.

An unsupported combination (a dust jacket at KDP; a trim a provider does not
cut; a page count under the minimum) fails at config time with a locatable
message, never at the printer.

## The spine model must be pluggable

Because the three providers use three formula shapes, the caliper model is an
interface, not a constant:

- `constant`: `pages × caliper[stock] + allowance` (KDP).
- `divisor`: `pages / divisor + allowance` (Lulu paperback, stock-independent).
- `ppi-table`: `pages / ppi[stock]` (IngramSpark).
- `lookup`: a stepped table keyed by page-count band (Lulu hardcover).

Each provider spec declares its shape and its stock table. `spine_width`
becomes `provider.spine(pages, binding, paper)`, and the current
`gen_coverwrap.PAPER_THICKNESS` constants become the *house/KDP* provider
spec — which must reproduce today's output for the compatibility gate.

## v1 compatibility

- The **house design profile** already reproduces v1 interior geometry
  byte-for-byte (proven: same page hash on the reference book).
- A **house provider spec** must reproduce today's `gen_coverwrap` output for
  the existing 6×9 paperback so the coverwrap stays identical until a book
  opts into a different provider. Note: today's spine omits the `+0.06`
  paperback allowance; the house spec preserves that (bug-for-bug) so v1
  covers do not shift, and the corrected allowance ships only under real
  provider specs a book opts into. (Flag this in the migration notes.)
- Unlocking trim, adding bindings/materials/providers is a **design-major
  (v2)** change per the ARCHITECTURE versioning contract. This work lives on
  the `v2-print-profiles` branch; nothing merges to a v1 release.

## Schemas (target)

Design profile (`data/profiles/<id>.yaml`) — interior only:

```yaml
id: house-6x9
design-major: 1
trim: {width: 6.0, height: 9.0}
interior:
  margins: {inner: 0.78, outer: 0.68, top: 0.72, bottom: 0.78, headsep: 0.20, footskip: 0.38}
  figure-cap: 6.3
```

Provider spec (`data/provider-specs/<id>.yaml`) — manufacturing only:

```yaml
id: lulu
spine:
  shape: divisor          # constant | divisor | ppi-table | lookup
  divisor: 444
  paperback-allowance: 0.06
  hardcover:
    shape: lookup
    table: [[24, 84, 0.25], [85, 140, 0.5], ...]
cover:
  bleed: 0.125
  safety: 0.5
  bindings:
    perfect-bound: {spine: true, gutter: true}
    saddle-stitch: {spine: false}
    casewrap:      {wrap: 0.75, hinge: 0.25, overhang: 0.125}
    dust-jacket:   {flap: 3.25, flap-fold: 0.25, strip: 0.25, material: linen}
  barcode: {zone: [3.625, 1.25], mandatory: false}
trims:                    # trim -> which bindings that trim allows
  {width: 6, height: 9}: [perfect-bound, casewrap, dust-jacket]
pages: {perfect-bound: {min: 32}, hardcover: {min: 24, max: 800}, spine-text-min: 80}
```

## Revised staged plan

| Stage | Work | Ships |
| --- | --- | --- |
| ✅ 1 | Design-profile foundation + geometry projection, v1 byte-identical | done |
| 2 | Provider-spec model + house/KDP spec reproducing current coverwrap; pluggable spine (`constant/divisor/ppi-table/lookup`); `gen_coverwrap` + `verify_coverwrap` read the spec | branch |
| 3 | Binding topology in the cover generator: saddle/coil (no spine), casewrap (turn-in), dust jacket (flaps); material treatment (suppress cloth field / printed cover for linen) | branch |
| 4 | `print.{profile,binding,material,provider,paper}` config; unlock trim (derive from profile); relax `INV-config-trim`, selftest, `verify_pdf`; legality checks (trim×binding, page bounds) fail before render | branch (v2) |
| 5 | Encode Lulu / KDP / IngramSpark specs from the sourced numbers; qualify at least two designs per #172; scaling tails (front-matter cap, print_safe, cover aspect); docs | branch |

## Open questions to confirm before encoding

- KDP standard-vs-premium **color caliper** (0.002252 vs 0.002347) — confirm on the live cover calculator.
- KDP hardcover **wrap constants** (0.591/0.394/0.236) — calculator-derived, not a text spec.
- IngramSpark **dust-jacket flap width** — the guide defines the 0.25″ strip but ships exact flap size only via the emailed template; "3.25″" is third-party.
- IngramSpark **max page count** — varies by binding/channel, no single published number.
- Whether to correct the missing **`+0.06` paperback allowance** in a v2 provider spec (recommended) while the house spec keeps the v1 value.

## Sources

- Lulu Book Creation Guide: <https://assets.lulu.com/media/guides/en/lulu-book-creation-guide.pdf>
- Lulu casewrap 0.75″ wrap: <https://help.lulu.com/en/support/solutions/articles/64000308572-creating-your-hardcover-casewrap-cover>
- IngramSpark Paper Specifications (PPI table): <https://www.ingramspark.com/hubfs/downloads/Paper_Specs_Spark.pdf>
- IngramSpark File Creation Guide (bleed, safety, 0.625″ fold, jacket strip, barcode): <https://myaccount.ingramspark.com/documents/IngramSpark%20File%20Creation%20Guide.pdf>
- IngramSpark trim/binding matrix: <https://www.ingramspark.com/hubfs/downloads/trim-sizes.pdf>
- KDP cover calculator: <https://kdp.amazon.com/cover-calculator>
- KDP print options / trim & margins: <https://kdp.amazon.com/en_US/help/topic/G201834180>
