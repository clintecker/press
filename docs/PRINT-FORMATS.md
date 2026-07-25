# Trim, binding, and cover

::: {.lede}
A book's physical form is four independent choices — its trim (page size),
its binding, its cover material, and the vendor that prints it. Press models
each as configuration, so the same manuscript can be a 6×9 paperback or a
5×8 hardcover with a linen case, and the cover geometry follows.
:::

The default is a 6×9 paperback, perfect-bound — the sealed house design. A
book that sets none of the keys below builds exactly that, unchanged. Every
other combination is opt-in.

## The four choices

Each is a `print.*` key you set with `press config`:

| Choice | Key | Default | What it controls |
| --- | --- | --- | --- |
| Trim & interior | `print.profile` | `house-6x9` | page size and interior geometry |
| Binding | `print.binding` | `perfect-bound` | the cover's topology (spine, flaps) |
| Cover material | `print.material` | `paperback` | the cover treatment (cloth vs printed) |
| Provider | `print.provider` | `house` | the spine, bleed, and wrap **numbers** |

```sh
press config set print.profile novella-5x8 && \
press config set print.provider lulu && \
press config set print.binding casewrap && \
press config set print.material casewrap
```

An unsupported combination — a trim a vendor does not cut, a dust jacket at a
vendor that offers none, a colour interior at a vendor that prints none — is
**refused by `press check`**, before any render, naming what went wrong. (The
page-count bounds are checked at build time, where the real page count is
known.) The trims and inks each vendor supports are captured as data in its
provider spec, so the gate is one reviewed matrix, not scattered rules.

## Trim comes from a design profile

The trim is not a hand-entered number: it comes from the **design profile**
named by `print.profile`, because a profile is a sealed, verified geometry —
the trim can never disagree with the interior it was laid out for. The house
profile is 6×9; other profiles carry their own trim and margins.

```sh
press config set print.profile novella-5x8   # a 5x8 Digest/Novella
```

Selecting a profile changes the page for both the reading PDF and the print
interior. Adding a new trim is adding a profile, not editing the pipeline.

A profile carries more than trim. It also seals the interior's **structural
typography** — the paragraph indent and leading — and the **web reading
measure** — the maximum line length, base font size, and line height of the
reader site. These are the design: `house-6x9` uses the values the press has
always used, and `novella-5x8` sets a tighter measure and more open leading to
suit the narrower digest page. What a profile does *not* touch is your book's
identity — the font family and the colour palette — which stay with the
[aesthetic](https://github.com/clintecker/press/blob/main/docs/CONFIGURATION.md)
and override the profile. So choosing a profile changes the design's
proportions; choosing an aesthetic changes its voice.

## Colour interiors

The interior prints in a single black ink by default — the cheapest, sealed
house discipline, and the honest space for an engraving. A book whose interior
wants **colour** — a cookbook of food photographs, an early reader, a
photo-essay — selects a colour design profile:

```sh
press config set print.profile house-6x9-color && \
press config set print.provider kdp
```

`house-6x9-color` is the 6×9 house geometry, byte-for-byte, with one difference:
the interior prints in colour. A text-only page renders identically to
`house-6x9`; the change lifts the print verifier's single-ink rule and keeps
your commissioned plates in colour instead of graying them at intake.

Colour is a **profile** choice, not an aesthetic one: the aesthetic still cannot
tint the interior, so the single-ink craft law is intact — colour is a
deliberate, sealed design decision.

### It must be paired with a provider that prints colour

Colour stock is a different, heavier paper, so the spine is computed from the
provider's **colour caliper**, not the white/cream one. Only a provider whose
colour stock is documented can be trusted with that number, so a colour
interior is **refused by `press check`**, before any render, at a provider
that does not specify one — the press will not guess a thickness. Today that
provider is **KDP**;
Lulu and IngramSpark refuse a colour interior until their colour stock is
researched and sourced.

Colour costs more to print, and the page is thicker: KDP offers a
**standard** and a **premium** colour grade, and `print.color-grade` picks
between them (standard by default).

```sh
press config set print.color-grade premium-color   # optional; standard otherwise
```

When you order a golden copy of a colour edition (see
[print ordering](https://github.com/clintecker/press/blob/main/docs/PRINT-ORDERING.md)),
the inspection's **colour** checklist point is where you confirm the ink
reproduces on the physical copy as it does on screen. The
[Hearthstone Table](https://github.com/clintecker/press/tree/main/examples/hearthstone-cookbook)
example is a colour cookbook built this way.

## Binding sets the cover's shape

The binding decides the cover topology, independent of the vendor:

- **`perfect-bound`** — a paperback: back · spine · front, flat.
- **`saddle-stitch` / `coil`** — no spine (a flat back · front wrap).
- **`casewrap`** — a hardcover printed directly on the board, with a wrap
  that folds around it (a board turn-in and hinge).
- **`dust-jacket`** — a hardcover jacket with flaps.

A hardcover binding needs the provider's wrap geometry, so it is only
available at a provider that offers it (see below).

## Material chooses the treatment

- **`paperback`** / **`casewrap`** — a printed cover.
- **`linen`** — a cloth case where the **printed field is suppressed**: the
  linen is the finish, and only the dust jacket is printed. (Press never bakes
  a simulated cloth texture into a real linen cover.)

## The provider supplies the numbers

The spine caliper, bleed, safety margin, and hardcover wrap geometry are
**vendor-specific** — the same 6×9 paperback has a different spine width at
each printer, because they run different paper and round differently. Select
the vendor so the numbers are theirs:

```sh
press config set print.provider lulu   # or kdp, ingramspark
```

What each vendor offers (from their sourced specs):

| Vendor | Bindings | Notable |
| --- | --- | --- |
| `lulu` | perfect-bound, saddle-stitch, coil, casewrap, dust-jacket (linen) | hardcover spine from a lookup table; the fullest set |
| `kdp` | perfect-bound, casewrap | **no** dust jacket, cloth, saddle, or coil |
| `ingramspark` | perfect-bound, casewrap, dust-jacket | its white 50# is genuinely thinner (512 PPI) |
| `house` | perfect-bound, saddle-stitch, coil | the default; reproduces the v1 spine exactly |

The full trim × binding × ink matrix and page-count bounds live in each
provider's spec; `press check` refuses a trim, binding, or ink the vendor does
not offer before any render, and `press coverwrap` enforces it again at the
cover geometry.

Which providers exist and what each can actually do is one reviewed ledger,
`quality/providers.yaml`; the copy shipped in the wheel is generated from it,
never hand-copied. To add a provider or correct a citation, follow the
[provider-data update workflow](https://github.com/clintecker/press/blob/main/docs/PROVIDER-DATA.md).

## Verify and inspect

`press verify-print` builds and verifies the interior and cover wrap at the
selected geometry. The wrap is checked against the *same* geometry the
generator used, so a size regression cannot ship. As always, a physical
golden-copy inspection (see
[print ordering](https://github.com/clintecker/press/blob/main/docs/PRINT-ORDERING.md))
is what actually qualifies an edition for sale.

## A note on versions

Configurable trim, binding, and material change a book's typography and
physical form, so they are a **v2** capability — a book opts in by pinning
`@v2`. A `@v1` book is 6×9 paperback, unchanged. The design rationale and the
sourced vendor numbers are recorded in the
[print-profiles plan](https://github.com/clintecker/press/blob/main/docs/PRINT-PROFILES-PLAN.md).
