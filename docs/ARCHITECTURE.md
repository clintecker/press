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

The traceable table is generated from the ledger into
[docs/INVARIANTS.md](https://github.com/clintecker/press/blob/main/docs/INVARIANTS.md);
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

Books pin `@v1` (floating) or a three-part tag (immutable, enforced:
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
  their pin.
- Three-part tags (`vN.x.y`) are immutable, and the immutability is
  enforced rather than promised: the release-contract workflow
  proves that each three-part tag's build.yml pins the press action
  to that exact tag and the toolchain image to an existing immutable
  `sha-` tag, so a pinned book resolves the same pipeline, action,
  and toolchain bytes forever.
- `vN` floats: it moves to the latest compatible `vN.x.y`, following
  the GitHub Actions convention. A book that pins `@v1` accepts
  fixes within the design contract; a book that pins `@v1.x.y`
  accepts nothing at all.

## Where a book ends and the press begins

A book holds its manuscript, config, and accepted art — nothing else.
If a book needs machinery, the machinery belongs here. If the press
needs a book-specific fact, it must arrive through config. The
integration gate enforces the second rule mechanically: no original-
book identity may appear in a clean scaffold's public artifacts.
