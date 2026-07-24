# Provider data: update and review workflow

The print-provider qualification ledger has **one canonical source**:
[`quality/providers.yaml`](https://github.com/clintecker/press/blob/main/quality/providers.yaml).
It is the reviewed record of which providers exist, what each can actually
do, and what is still unknown — with a citation, a retrieval date, and an
explicit capability value for every claim.

The copy an installed wheel loads,
[`src/press/data/providers.yaml`](https://github.com/clintecker/press/blob/main/src/press/data/providers.yaml),
is **not** a second maintained file. It is a deterministic projection of the
canonical ledger: a fixed generated banner followed by the canonical bytes
verbatim, written by `press.qualification.render_packaged()`. Never edit it
by hand — an edit there is overwritten on the next regeneration and is
refused by the selftest in the meantime.

## Changing the ledger

1. Edit **only** `quality/providers.yaml` — add a provider, correct a
   citation, adjust a capability or an `unknowns` entry. Keep every
   provider's `disposition`, `evidence` (each a `claim` and a `url`),
   explicit `capabilities`, `unknowns`, and the physical-verification
   `physical_checklist` intact; the validator refuses an implicit
   capability or an evidence entry missing a claim or url.
2. Regenerate the packaged projection and the rendered docs in one step:

   ```sh
   python3 -m press selftest --write-docs
   ```

   This rewrites `src/press/data/providers.yaml` from the canonical bytes
   and regenerates
   [`docs/PROVIDER-QUALIFICATION.md`](https://github.com/clintecker/press/blob/main/docs/PROVIDER-QUALIFICATION.md).
3. Commit the canonical file and its generated projection **together**. A
   review sees the human-meaningful diff in `quality/providers.yaml`; the
   packaged copy's diff is mechanical.

## What keeps the two in step

- `press.qualification.validate` compares the committed packaged file
  **byte-for-byte** against `render_packaged()`. A stale packaged copy — even
  one that differs only in a comment or in whitespace, which a semantic
  compare would miss — turns the selftest red with a regenerate instruction.
- The distribution tests build the wheel and assert its
  `press/data/providers.yaml` is exactly that projection, so no release ships
  a hand-copied or divergent record.

If the selftest reports the packaged record is stale, you edited the
generated copy or forgot to regenerate: run
`python3 -m press selftest --write-docs` and commit the result.

## Provenance and physical verification

Marketing and a published API are **evidence**, never qualification. A
provider in this ledger is *researched*; an edition becomes *qualified* for a
provider only when a physically ordered copy passes every point of the
`physical_checklist`, scoped to that edition's identity. The checklist and the
per-provider cards render into
[provider qualification](https://github.com/clintecker/press/blob/main/docs/PROVIDER-QUALIFICATION.md);
the gate lives in `press.qualification` and `press.edition`.
