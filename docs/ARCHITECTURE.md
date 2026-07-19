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

## Where a book ends and the press begins

A book holds its manuscript, config, and accepted art — nothing else.
If a book needs machinery, the machinery belongs here. If the press
needs a book-specific fact, it must arrive through config. The
integration gate enforces the second rule mechanically: no original-
book identity may appear in a clean scaffold's public artifacts.
