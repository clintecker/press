# The press, explained to someone who will change it

## The four laws

Everything here follows four laws, and a change that violates one is
wrong even when it works:

1. **Facts are stated once.** A book's identity lives in its config;
   the house design lives in press data; the artifact graph lives in
   the registry. If you find the same fact in two places, one of them
   is a bug already filed or a bug you should file.
2. **Generators over checkers over conventions.** Prefer machinery
   that produces the right thing to machinery that detects the wrong
   thing, and either to a sentence in a document asking people to
   behave.
3. **Artifacts are verified as objects.** A green build means the
   actual PDF was rendered and inspected, the actual EPUB was
   validated by the tool retail channels run, the actual site was
   crawled. Verifying without rebuilding is forbidden by construction.
4. **Scars become law.** Every production failure earns a mechanical
   guard and an entry in CLAUDE.md's scars list. Do not relearn them.

## The shape of the machine

- `booklib` / `bookmodel` — the one typed, normalized reading of a
  book's config, with locatable refusals. Nothing else parses
  metadata.
- `registry` — every artifact's outputs, prerequisites, and
  publication role, stated once; build order, download lists, and the
  CLI's format list derive from it.
- `build` — pandoc/LuaLaTeX orchestration through defaults templates
  (`@press/` and `@book/` path prefixes, `?optional` degradation).
- `gen_*` — the generators: front matter from config, the subject
  index, the authorities companion, the cover wrap with computed
  spine and EAN-13.
- `check_*`, `style_audit`, `jargon_lint` — the editorial law, which
  proves its own checkers against known-bad fixtures that each
  declare the rule they exist to trip.
- `verify_*` — the artifact inspectors: rendered-page PDF checks
  (with print-profile margin and ink laws), format witnesses, archive
  contracts, and the public-site crawl.
- `aesthetic` — the book's visual identity, merged over the house
  default; consumed by builders (palette, type, inks) and by the art
  workflows (prompt material).
- `instruments`, `operator`, `art`, `art_commission` — the packaged
  skills and agent workflows, their headless drivers, and the art
  department's commission/accept cycle.
- `config_cli` / `config_store` / `config_schema` — `press config`, the
  validated read/write surface over every book-configuration field: a
  comment-preserving round-trip write, checked by the real typed model
  before a byte is touched.
- `desk/` — the optional operator desk (the `tui` extra), a terminal
  interface and setup wizard over the same targets and config boundary;
  the CLI and desk are built from the one `catalog`, so they cannot drift.
- `yamlio` — the single YAML door (ruamel at YAML 1.2); no module reads or
  writes YAML any other way.
- `selftest`, `doctor` — the press checking itself and the machine
  it runs on.

## The artifact contract

`registry.ARTIFACTS` is the authoritative table. Every published
artifact is built by `press all`, named in the Pages downloads,
attached to releases by the reusable workflow, and covered by a
verifier; `press pages` builds its full prerequisite graph from a
clean repository. Adding an artifact obliges you to: declare it in
the registry (outputs, prerequisites, role), give it a verifier or
state why none applies, and let `press selftest` prove the graph
still holds and the docs still name every target. The selftest fails
otherwise; that failure is the extension checklist.

## The invariant matrix

Every invariant the press enforces has one machine-checkable home:
`quality/invariants.yaml`. Each entry names the guarantee, where it is
enforced, the negative proof that the enforcement can actually fail (a
selftest check or a known-bad fixture), and, honestly, what it does
not cover. The ledger's validator proves on every selftest that every
enforcer and proof it names still resolves to a real function or
fixture, so the matrix cannot cite something deleted or renamed, and a
critical invariant left undefended fails the build.

The traceable table is generated from the ledger into the
[invariant ledger](https://github.com/clintecker/press/blob/main/docs/INVARIANTS.md);
read it there rather than in a second copy here. An honest limitation
column is the point: a guarantee whose edges are unstated is a
guarantee waiting to be overtrusted. Universal fixtures live in
`src/press/data/known-bad/`; a book adds its own under
`tests/known-bad/`.

## Provenance and verification

Two different kinds of trust operate in a build, and it pays to keep
them distinct.

Generated-from-config facts are provenance: the press produced them
from declared inputs, so they are right by construction as long as
the generator is right. The front matter pages come from
`config/front-matter.yaml` and `config/metadata.yaml`; the cover
wrap's spine width, trim geometry, and EAN-13 come from the rendered
interior's page count and the declared paper stock; the subject index
comes from `config/index-terms.yaml` against the manuscript; the
authorities companion comes from `config/authorities.yaml`. None of
these can drift from their inputs, because they are regenerated on
every build (the generated appendices are cleaned first so stale
copies cannot survive).

Verified-now facts are the other kind: claims about the artifact
object itself, proven against the bytes this build produced. Every
verifier runs against the artifact it names, in the same run that
built it: the PDF's pages are rendered and inspected, the EPUB goes
through epubcheck, the archives are opened and their members
compared to policy, the public site is crawled. Nothing is trusted
from a previous run; the CLI's dependency edges force a rebuild
before any verification, so a stale artifact cannot be blessed.

The rule of thumb: generation makes a fact true, verification proves
it stayed true all the way into the object a reader receives. A fact
that is only generated is trusted exactly as far as its generator;
a fact that is verified is trusted as far as this build's evidence.

## The release contract

Books pin `@vN` (floating: `@v1` or `@v2`) or a three-part tag
(immutable, enforced:
the release-contract workflow proves each tag pins its own action ref
and an existing immutable toolchain sha). Design is part of the
contract: within a major, fixes may correct broken output but must
not change a valid book's typography; design changes wait for a new
major. Releases are gated on the integration workflow, which builds
the wheel, raises a stranger's book inside the real container, runs
the whole gauntlet, and tampers with an artifact to prove the
verifiers still refuse. Tag builds run with `PRESS_RELEASE=1`, which
refuses vacuous witnesses.

The release itself is proven by a trust-receipt chain: the
release-contract workflow first waits for every trust-layer check to go
green on the tagged commit (the full test suite, the container gauntlet,
the operator surface), then builds a receipt for each layer, each
extending the one before, terminated by a release receipt that names the
built wheel's digest and the pinned toolchain. Verification requires the
chain to be *complete* — every layer present, contiguous, and linked to
its predecessor — so a partial chain standing in for the missing layers
cannot pass. A release cannot be cut on a proof with a hole in it.

## Design versioning

Typography and layout are part of the pinned contract, not an
implementation detail behind it. The policy, restated plainly:

- Within a major version, a fix may correct broken output (a page
  that failed to render, a link that pointed nowhere, an artifact a
  verifier refused) but must not change the typography or layout of
  a book that was already valid. A book that rebuilt cleanly
  yesterday must produce the same design today.
- Design and template changes, however small they look, require a
  new major version. A different margin, face, or front-matter
  arrangement is a new contract, and books opt into it by moving
  their pin. v2 makes this concrete: trim and interior geometry are
  chosen from versioned **print profiles**, so a book selecting a
  non-house profile is asking for a different design under a v2 pin,
  while a `@v1` book stays the sealed 6×9 (see
  [trim & binding](https://github.com/clintecker/press/blob/main/docs/PRINT-FORMATS.md)).
- Three-part tags (`vN.x.y`) are immutable, and the immutability is
  enforced rather than promised: the release-contract workflow
  proves that each three-part tag's build.yml pins the press action
  to that exact tag and the toolchain image to an existing immutable
  `sha-` tag, so a pinned book resolves the same pipeline, action,
  and toolchain bytes forever.
- `vN` floats: it moves to the latest compatible `vN.x.y`, following
  the GitHub Actions convention. A book that pins `@vN` accepts
  fixes within the design contract; a book that pins `@vN.x.y`
  accepts nothing at all.

Moving between majors is opt-in, per-book, and reversible. `press migrate`
rewrites the press major in the two places a book pins it — its
`requirements.txt` and its CI workflow — and nothing else: the manuscript,
config, and art come out byte-for-byte identical, a dry run reports every
change before any mutation, and rollback restores the exact prior pin from a
backup written first. Because the house profile reproduces the sealed v1
geometry, a v1 book that repins to v2 and keeps the house profile renders
unchanged; the design moves only when the author selects a non-house
profile. A v2 release consumes the migration proof (`check_migration`'s
round-trip) with the consumer backtest, so a major cannot ship claiming a
path it has not demonstrated. The full contract is the
[migration guide](https://github.com/clintecker/press/blob/main/docs/MIGRATION.md).

## Extending the press

Everything extensible — a design profile, a provider spec, an artifact, a
skill, a workflow — is a named data file selected by id, never an imported
plugin, and that absence is the contract. Behavior cannot come from the
accident of which package imported first. A `@v2` addition carries an
**extension manifest** that declares the names it claims, the contract major
it targets, the invariants it takes on and how they are proven, and the
capabilities it asserts; a conformance gate refuses a manifest that collides
with a core name, targets an unsupported contract, or claims a sealed
capability — before anything is built. The mandatory verification, path
containment, artifact graph, config validation, and release gate stay
sealed: an extension may depend on them but never replace one. The full
decision record is the
[extension contract](https://github.com/clintecker/press/blob/main/docs/EXTENSION-CONTRACT.md).

## Where a book ends and the press begins

A book holds its manuscript, config, and accepted art — nothing else.
If a book needs machinery, the machinery belongs here. If the press
needs a book-specific fact, it must arrive through config. The
integration gate enforces the second rule mechanically: no original-
book identity may appear in a clean scaffold's public artifacts.
