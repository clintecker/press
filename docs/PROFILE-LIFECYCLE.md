# Print-profile lifecycle: scaffold, prove, seal

A new trim or ink is a new **print profile** — versioned interior geometry
the press ships as data (`src/press/data/profiles/<id>.yaml`) and a book
selects with `print.profile`. This is the one documented path from an idea
for a physical form to a stamped, proven artifact, so every profile is
qualified the same way rather than added ad hoc (#221).

This is a contributor workflow in the press repository, not a book-author
task: books *select* among shipped profiles; adding one happens here. The
skill `profile-lifecycle` (`press skills`) carries the same steps for an
agent; the machinery is `press.profile_lifecycle`.

## What a profile is (and is not)

A design profile carries the interior **look only**: trim, margins, figure
cap, typography. It does **not** carry manufacturing numbers — spine caliper,
bleed, cover-wrap geometry — which are provider-specific and live in a
provider spec, so the same design prints at Lulu, KDP, or IngramSpark. See
[the print-profiles plan](PRINT-PROFILES-PLAN.md) for the four orthogonal
layers (design, binding, material, provider).

## 1. Scaffold

Derive a new profile from an existing one, so it starts from proven geometry
instead of a blank file:

```sh
python3 -m press.profile_lifecycle scaffold trade-5-5x8-5 --trim 5.5x8.5
python3 -m press.profile_lifecycle scaffold photo-8x10 --trim 8x10 --ink color
```

The scaffold inherits the base profile's margins, figure cap, and typography
(default base: `house-6x9`; choose another with `--from`). Tune them for the
new trim — a narrower page wants a tighter measure and its own leading, the
way `novella-5x8` differs from a resized house. Keep the figure cap well below
`\textheight`: a figure taller than the text block makes LuaLaTeX ship empty
pages forever.

## 2. Prove with a golden-copy inspection

The profile's own declared numbers are the oracle, so a profile needs no
hand-minted image baseline. The golden-copy geometry proof renders **every
shipped profile** through the real toolchain and asserts the interior comes
out at the declared trim — a new profile is covered the moment its YAML
exists:

```sh
python3 -m pytest tests/test_visual_regression.py::test_profile_renders_at_its_declared_trim -q
```

Render it and read the page, too:

```sh
press config set print.profile trade-5-5x8-5 && press print
```

## 3. Seal it under the design contract

Sealing records the profile's design-affecting digest
([`profiles.digest`](https://github.com/clintecker/press/blob/main/src/press/profiles.py))
and its design-major in the ledger
(`src/press/data/profile-seals.yaml`). The digest is read from the profile —
you can never seal a geometry the profile does not actually have:

```sh
python3 -m press.profile_lifecycle seal trade-5-5x8-5 --note "5.5x8.5 US trade paperback"
```

From then on the selftest gate `check_profile_seals` turns **red** if the
profile's geometry ever drifts from its sealed digest. That is the design
contract made mechanical: within a major, appearance cannot change; changing
a sealed profile means bumping its design-major and re-sealing, a deliberate
act on the record.

## Verify the whole ledger holds

```sh
python3 -m press.profile_lifecycle validate   # every shipped profile sealed and current
python3 -m press selftest                      # the gate among all the others
```

Commit the new profile YAML and the updated seal ledger **together**: an
unsealed shipped profile fails the selftest, and so does a seal that names a
profile the press does not ship.
