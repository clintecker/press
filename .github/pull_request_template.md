<!-- Keep changes scoped: one concern per PR. Do not include a private
     manuscript, credentials, or copyrighted book content. -->

## What and why

<!-- The change and the outcome it produces. -->

Closes #

## Proof

<!-- How you know it works. The press proves changes; name the evidence. -->

- [ ] A test fails before this change and passes after it.
- [ ] `press selftest` and the pytest suite pass locally.
- [ ] Generated projections are regenerated and not hand-edited
      (`docs/REFERENCE.md`, `docs/INVARIANTS.md`, `docs/PROVIDER-QUALIFICATION.md`,
      `ROADMAP.md`, the docs site).
- [ ] Docs updated in the same change as the surface they describe.

## Contract impact

<!-- Delete the lines that do not apply. -->

- Compatibility: backward-compatible / corrects broken output / breaking (new major).
- Invariants added or changed:
- Consumer proof (if the pipeline or CI contract changed):
