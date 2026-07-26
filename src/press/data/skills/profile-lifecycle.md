---
name: profile-lifecycle
version: 1.0.0
description: Add a print profile to the press the one repeatable way - scaffold a new trim or ink from proven geometry, prove it with a golden-copy inspection, then seal it under the design contract so its appearance can never drift without a deliberate re-seal.
compatibility: any-agent
---

# Print-profile lifecycle

## Purpose

A trim (6×9, 5×8, 5.5×8.5) or an ink (single black, colour) is a **print
profile**: versioned interior geometry the press ships as data
(`src/press/data/profiles/<id>.yaml`), selected by a book with
`print.profile`. Adding one is adding a profile, never editing the pipeline.

This skill is the one path from an idea for a new physical form to a
**stamped, proven artifact**: scaffold → prove → seal. It runs in the press
repository (a maintainer/agent activity), not in a book. The prose reference
is `docs/PROFILE-LIFECYCLE.md`; the machinery is `press.profile_lifecycle`.

## Before you start

- Read `src/press/profiles.py` (what a profile carries and how its digest is
  computed) and `docs/PRINT-PROFILES-PLAN.md` (why design, binding, material,
  and provider are four orthogonal layers — a profile is the **interior look
  only**: trim, margins, figure cap, typography; never spine or bleed).
- A profile change to an *existing* profile is a design-major decision. This
  skill adds a *new* profile; changing a sealed one means bumping its
  design-major and re-sealing, deliberately.

## The three steps

### 1. Scaffold

Derive a new profile from an existing one so it starts from proven geometry:

```sh
python3 -m press.profile_lifecycle scaffold trade-5-5x8-5 --trim 5.5x8.5
python3 -m press.profile_lifecycle scaffold photo-8x10 --trim 8x10 --ink color
```

The scaffold copies the base's margins, figure cap, and typography (tune them
for the new trim — a narrower page wants a smaller measure and its own
leading, as `novella-5x8` does). It never invents spine or bleed numbers:
those are provider specs, not design. The figure cap must never approach
`\textheight` (the LuaLaTeX empty-page scar).

### 2. Prove (golden-copy inspection)

The profile's own declared numbers are the oracle. The golden-copy geometry
test renders **every shipped profile** through the real toolchain and asserts
the interior comes out at the declared trim:

```sh
python3 -m pytest tests/test_visual_regression.py::test_profile_renders_at_its_declared_trim -q
```

Your new profile is covered the moment its YAML exists — no separate baseline
to hand-mint. Also render it and look at the page:

```sh
press config set print.profile trade-5-5x8-5 && press print
```

### 3. Seal

Sealing records the profile's design-affecting digest and its design-major in
the ledger (`src/press/data/profile-seals.yaml`). The digest is read from the
profile — you cannot seal a geometry the profile does not have:

```sh
python3 -m press.profile_lifecycle seal trade-5-5x8-5 --note "5.5x8.5 US trade paperback"
```

From now on the selftest gate (`check_profile_seals`) turns **red** if the
profile's geometry ever drifts from its sealed digest. That is the design
contract made mechanical: appearance cannot change without a deliberate
re-seal, which is a design-major decision.

## Verify the whole thing holds

```sh
python3 -m press.profile_lifecycle validate   # every shipped profile is sealed and current
python3 -m press selftest                      # the gate, among all the others
```

Commit the new profile YAML and the updated seal ledger **together** — an
unsealed shipped profile fails the selftest, and so does a seal for a profile
that is not shipped.
