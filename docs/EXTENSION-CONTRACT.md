# The extension contract

Status: accepted. Governs: the v2 line (`@v2`) and every major after it.
Issue: [#171](https://github.com/clintecker/press/issues/171). Enforced by
`src/press/extensions.py`, the `INV-extension-conformance` and
`INV-extension-seal` invariants, and the `check_extension_conformance`
selftest.

This is the decision record for what a book — or a third party — may add to
the press, and what stays sealed. It exists so that the composable v2 press
gains new profiles, providers, and artifacts *without* any of them being
able to bypass the artifact, invariant, packaging, or design contracts the
press already keeps. Read it before opening an implementation issue that
adds a new extensible surface; the surface must fit this contract or the
contract must change first.

## The decision: press extends by declaration, not by code

The press has **no plugin loader, no entry-point group, and no import-time
discovery**, and that absence is the contract, not a missing feature. A
system that discovers behavior by importing whatever package registered
itself first makes its own behavior a function of installation order, and no
verification claim survives that. So the press does the opposite: everything
extensible is a **named data file, selected by id, validated at a typed
boundary**.

You already see the model in v2's design profiles and provider specs. A
design profile is `src/press/data/profiles/<id>.yaml` carrying a
`design-major:` and its geometry; you select it with
`press config set print.profile <id>`. A provider spec is
`src/press/data/provider-specs/<id>.yaml`; you select it with
`print.provider`. Adding one is dropping a file and selecting it. There is
nothing to import, nothing to register, no order to get wrong.

An **extension** is one more entry in one of these declarative registries,
carrying a manifest that states its obligations. It earns a place in a
registry that the same typed, path-contained, deterministic laws already
govern. It earns no privilege to run arbitrary code, because the contract
admits none.

## What may be extended

Five surfaces, each already a named, id-selected, data-declared registry:

| Surface | Registry | Selected by |
| --- | --- | --- |
| `design-profile` | `data/profiles/<id>.yaml` | `print.profile` |
| `provider-spec` | `data/provider-specs/<id>.yaml` | `print.provider` |
| `artifact` | `registry.ARTIFACTS` | build target / download policy |
| `skill` | `data/skills/<id>/` | `press skills`, workflows |
| `workflow` | `data/workflows/<id>.js` | `press workflows`, the Workflow tool |

Each new entry declares itself with an **extension manifest** (below). The
manifest is what makes the addition auditable before it runs.

## What stays sealed

These are the press's to guarantee. An extension may *depend on* them
running; it may never declare that it provides or replaces one, and the
conformance gate refuses any manifest that claims a sealed capability:

- **`core-verification`** — the mandatory checks every artifact passes
  (`press check`, the format witnesses, the blank-page and ink detectors,
  archive policy). A book cannot ship an editon these did not bless.
- **`path-containment`** — every write lands under the book root; nothing
  an extension names escapes `dist/` or `build/`.
- **`artifact-graph`** — the acyclic dependency graph in `registry.py`
  that forbids verifying a stale artifact or assembling pages before their
  archives exist.
- **`config-validation`** — the typed boundary that checks every config
  write before a byte is touched (`config_schema.validate_file`).
- **`release-gate`** — the release-contract and commerce gates that decide
  whether an edition may be tagged or sold.

Design itself is sealed *within a major*: a profile's appearance cannot
change without a new profile identity or a `design-major` bump. That rule
is [#172](https://github.com/clintecker/press/issues/172)'s to enforce; this
contract only guarantees an extension cannot route around it.

## The extension manifest

A manifest is a small YAML mapping. The reference example lives at
`src/press/data/extensions/reference.yaml`:

```yaml
name: acme-quarto           # the extension's own id (must not collide)
kind: design-profile        # which sealed-list surface it registers into
contract-major: 2           # the extension contract it was written against
provides:                   # the exact names it claims in that registry
  - acme-quarto
requires:                   # names it depends on: core or self-provided
  - pdf
invariants:                 # the guarantees it takes on
  - INV-acme-quarto-geometry
proofs:                     # how each is proven (may not be empty if any)
  - fixture:acme-quarto.md
capabilities:               # what it asserts — never a sealed capability
  - interior-geometry
publication: internal       # published | internal, for artifacts it adds
```

Every field is an **obligation on the record**. `provides` is what the
extension will occupy in the registry; `requires` is what must already
exist; `invariants` plus `proofs` are the guarantees it accepts and how it
keeps them; `capabilities` is what it claims to do; `publication` decides
whether an artifact it adds reaches readers. Nothing here is inferred, and
nothing is optional-by-omission in a way that hides a decision.

## Version negotiation

An extension pins `contract-major` to the extension contract it was written
against. The press declares the majors it implements in
`extensions.SUPPORTED_CONTRACT_MAJORS` (today: `(2,)`). A manifest targeting
any other major is **refused before execution** — never loaded and hoped
for. The extension contract major moves with the design major, because a
press only grows surfaces to extend across a breaking design change; a `@v2`
book speaks contract major 2.

## Lifecycle

Deterministic and explicit, with no ambient step:

1. **Discover.** Registries are read from disk in sorted order
   (`glob("*.yaml")` sorted, registry declaration order). Discovery is a
   function of what files exist, never of import or entry-point order.
2. **Parse.** `load_manifest` turns the mapping into a `Manifest`, refusing
   anything structurally malformed (a missing or mistyped required key) at
   the parser boundary.
3. **Check conformance.** `conformance(manifest)` returns the reasons the
   manifest is refused, most important first, or an empty list. This runs
   *before* any build.
4. **Register.** A conforming manifest's `provides` names take their place
   in the registry alongside the core entries, under the same laws.
5. **Build & verify.** The extension's artifacts pass exactly the checks a
   core artifact does. There is no lighter path for extension output.

## Error model

Every refusal is a **located reason**, never a bare "invalid extension":

- **Collision** — `provides` a name the core already owns (an artifact,
  command, alias, profile, or provider id) or claims the same name twice.
  Refused with the colliding name.
- **Unsupported contract** — `contract-major` the press does not implement.
- **Unknown dependency** — `requires` a name that is neither core nor
  self-provided, so behavior would depend on discovery order.
- **Sealed claim** — `capabilities` names a sealed capability.
- **Unproven obligation** — declares `invariants` but names no `proofs`.
- **Malformed** — refused at the parser boundary, before policy runs.

Collisions and version mismatches fail up front, at manifest time, not deep
in a render. That is the whole point: a book learns an extension is
incompatible before it has built anything against it.

## Extension obligations, in the ledgers

The contract is modeled in the same ledgers that govern the core, so the
obligations are proven, not promised:

- `INV-extension-conformance` (critical) — a colliding, mis-versioned,
  malformed, or unknown-dependency manifest is refused before execution.
- `INV-extension-seal` (critical) — a manifest cannot claim a sealed
  capability or carry an unproven invariant.
- `quality/surfaces.yaml` classifies `extensions.conformance` as a
  `verifier` and `load_manifest` as a `parser`, so the module is proven the
  way its role demands.
- `check_extension_conformance` runs the reference and hostile fixtures on
  every selftest, in the CLI and the pytest suite alike.

## Conformance fixtures

The contract ships its own adversaries as package data under
`src/press/data/extensions/`:

- `reference.yaml` — a well-formed third-party extension that **must**
  conform.
- `hostile/collision.yaml` — claims the core `pdf` artifact.
- `hostile/version.yaml` — targets contract major 99.
- `hostile/sealed.yaml` — declares it provides `core-verification`.
- `hostile/unproven.yaml` — an invariant with no proof.
- `hostile/malformed.yaml` — structurally invalid; refused by the parser.

The selftest asserts the reference conforms and every hostile manifest is
refused. A future runtime that *loads* extensions will reuse exactly this
gate; the gate exists and is proven before any loader does, so the loader
cannot become the accidental place the rules actually live.

## The v1 compatibility path

A `@v1` book has no extensions and needs none: it selects the sealed house
6×9 profile and the house provider, and renders byte-for-byte as it always
has. The extension contract is a v2 surface. A v1 book that pins `@v2`
migrates by the path in
[the migration contract](https://github.com/clintecker/press/blob/main/docs/MIGRATION.md);
until it selects a non-house profile or provider, no manifest is consulted
and nothing about its build changes. Old immutable v1 tags keep resolving
their exact pipeline forever, extensions or not.

## Deprecation policy

The extensible *surfaces* (the five kinds) and the manifest schema are part
of the design contract: within a major they may gain fields but not change
the meaning of an existing one, and a field is removed only across a major
with a deprecation recorded in the CHANGELOG and a migration note. A new
`contract-major` is added to `SUPPORTED_CONTRACT_MAJORS` when the press
learns to speak it and dropped only across a major. An extension pinned to a
still-supported contract keeps conforming; one pinned to a dropped contract
is refused with the supported set named, never run against a contract the
press no longer honors.

## What this contract deliberately does not do

It does not admit a code extension — no hook, no callback, no imported
plugin — because that is the accidental plugin API
[#171](https://github.com/clintecker/press/issues/171) was opened to
prevent. Everything an extension contributes is a declaration validated
before it runs. If a future need genuinely cannot be met by a declarative
registry entry, that is a new decision record and a new major, not a hook
slipped in under this one.
