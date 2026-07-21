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
vendor that offers none, a page count out of range — is **refused before
rendering**, naming what went wrong.

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

The full trim × binding matrix and page-count bounds live in each provider's
spec; `press coverwrap` refuses a combination the vendor does not offer.

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
