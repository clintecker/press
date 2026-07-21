# Migrating between press majors

A book pins the press to a major — `@v1`, and now `@v2` — and that pin is a
contract: it resolves the same pipeline, action, and toolchain bytes for as
long as you leave it. Moving to a new major is opting into a new contract,
and this page is how you do it safely, prove what changed, and reverse it if
you change your mind.

The whole operation is one command, `press migrate`, and its first promise
is that it touches **only the pin**. Your manuscript, your config, and your
accepted art — the three things a book owns — are never rewritten by a
migration. A migration changes which pipeline builds your book, never what
your book says.

## What v1 → v2 actually changes

Almost nothing, unless you ask for more. v2 makes trim, binding, cover
material, and print vendor configurable, but a book that repins from `@v1`
to `@v2` and keeps the **house design profile** renders byte-for-byte as it
did under v1: the house 6×9 profile reproduces the sealed v1 geometry
exactly. The design changes only when you *select* a non-house
`print.profile` — a separate, explicit choice you make after migrating, not
a side effect of the pin.

So the migration itself is small: it rewrites the press major in the two
places a book pins it, and leaves everything else alone.

| Site | Before | After |
| --- | --- | --- |
| `requirements.txt` | `clintecker/press@v1` | `clintecker/press@v2` |
| `.github/workflows/<ci>.yml` | `…/build.yml@v1` | `…/build.yml@v2` |

An immutable pin (`@v1.20.0`) is floated to the new major (`@v2`); pin a
three-part v2 tag afterward if you want to freeze the exact release.

## The four moves

```bash
press migrate            # or: press migrate plan — dry run, writes nothing
press migrate apply      # repin, after writing an exact backup
press migrate status     # what you're pinned to, and any recorded migration
press migrate rollback   # restore the exact prior pin
```

### `press migrate` (plan) — see everything first

The dry run reports every change it would make and every consequence to
weigh, and **writes nothing**. This is the `INV-migration-preview`
guarantee: you learn exactly what moving majors does before a byte changes.

```text
migrate v1 -> v2

changes:
  requirements.txt: clintecker/press@v1  ->  clintecker/press@v2
  .github/workflows/book.yml: …/build.yml@v1  ->  …/build.yml@v2

before you apply:
  - design is unchanged: with the house profile, v2 reproduces the v1
    geometry byte-for-byte. Selecting a non-house print.profile is a
    separate, explicit choice.
  - the manuscript, config, and accepted art are not touched.
  - custom override tex/title-page.tex is preserved as-is: overrides the
    generated front matter entirely; verify it against your trim before
    shipping.

nothing is written until you run `press migrate apply`.
```

If you supply files the design profile does not govern — a
`tex/title-page.tex`, a custom `assets/web/reader.css` or `extra.css`, a
`config/aesthetic.yaml` — the plan **names each one** so you re-check it
against the major you are moving to. They are preserved untouched, never
silently carried or overwritten.

### `press migrate apply` — repin, reversibly

Apply writes an exact backup of every file it will change *before* it
changes anything, then rewrites the pin. It records a receipt at
`.press/migration-receipt.json`. This is the `INV-migration-safe`
guarantee: only the pin moves, and there is always a way back.

Commit the repinned `requirements.txt` and workflow. On the next push, CI
resolves the new major's pipeline and toolchain.

### `press migrate rollback` — exact reversal

Rollback restores the exact pre-migration bytes of every file the last
migration touched, from the backup, and clears the migration state. It is a
byte-for-byte reversal, not a best-effort undo.

## What migration will not do

- It will not touch `book/`, `config/`, `tex/` (except a pin, which never
  lives there), or `assets/`. A press pin found *outside* `requirements.txt`
  or a CI workflow is refused, not rewritten — migration cannot edit prose.
- It will not migrate a book pinned to two different majors at once; it
  reports the split and asks you to reconcile it first.
- It will not change your design. Moving to a non-house profile is a
  deliberate act you take after migrating, under v2's
  [trim & binding](https://github.com/clintecker/press/blob/main/docs/PRINT-FORMATS.md)
  configuration.

## Old pins keep working

Migration is opt-in and per-book. A book that never repins stays on its
major forever: `@v1` keeps resolving the v1 pipeline, and every immutable
`v1.x.y` tag resolves its exact proven bytes. There is no forced upgrade and
no deadline. The v1 milestones continue to receive fixes within the v1
design contract; v2 is a door you walk through when you want what is behind
it.

## How the press proves this

The two guarantees are invariants, proven on every selftest by
`check_migration`, which scaffolds a real book, runs the full
`plan → apply → rollback` round-trip, and asserts that the plan changes
nothing on disk, that apply moves only the pin while the manuscript, config,
and art come out byte-for-byte identical, that a receipt is written, and
that rollback restores the exact prior pin. A v2 release consumes that proof
along with the consumer backtest — a real book built from the installed v2 —
so a major cannot ship claiming a migration path it has not demonstrated.

- `INV-migration-safe` — migration moves only the pin; rollback restores
  exact bytes.
- `INV-migration-preview` — a dry run reports every change before any
  mutation.
