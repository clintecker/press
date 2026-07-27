# Celebrimbor: clean-room build brief

This is the specification a clean-room team builds `celebrimbor` against. Its
companion is `CELEBRIMBOR-PLAN.md` (the analysis and the decision); this document
is the **build contract**. Read the plan for *why*; build against *this* for
*what*.

## How to use this spec (read first)

- **Build fresh against this spec. Do not read press's implementation.** The
  spec deliberately gives you the *what* (API, conventions, contracts) and the
  hard-won *constraints* (the "scars" below), but not press's *how*. Building
  clean-room keeps the result genuinely app-agnostic — a design that never saw
  `press.` cannot couple to it — which is the framework's first architectural
  requirement.
- **But you are not in a vacuum.** The scars are non-negotiable requirements, not
  suggestions; press already paid for each one in production. Build them in from
  the start rather than re-deriving them. (This is the project's own thesis
  applied to its own construction: an agent building without a falsifier in
  reach will produce something plausible and wrong.)
- **Definition of done is the acceptance test at the end**, not "it looks right."

## Thesis (the one-paragraph pitch, and the design compass)

Celebrimbor is **invariant-driven design as a framework**: it removes the
epistemic vacuum where plausible-but-wrong code lives. A claim a system cannot
contradict is a claim it will eventually get wrong — and AI-generated code, which
optimizes for plausibility, lives in exactly that vacuum. Celebrimbor's job is to
make every unit of an application **carry its own falsifier** and to make the gate
**fail closed** — refuse when it cannot prove, never estimate. Every design
decision below serves that compass: *self-falsifying claims, fail closed,
invariants over checks.*

## Product shape

Omakase quality harness for Python apps. `pip install celebrimbor` →
`celebrimbor init` → `celebrimbor gate`, near-zero wiring. Two tiers:

- **Tier 0 (green in <10 min, no theory of testing required):** commodity ladder
  — lint, types, format, known-bad — wired with opinionated defaults. This is the
  adoption wedge; it must pass on a fresh repo.
- **Tier 1 (opt-in, authored not free):** the obligation engine — surface-role
  completeness, no-blind-verifier ledger, invariant ledger, impact gate,
  mutation. Off until the app opts in, so it never reddens day one.

## Public API — the whole surface

- `celebrimbor init [--surfaces]` — scaffold: write opinionated tool defaults
  (ruff, mypy, a formatter, pytest/coverage), a `.pre-commit-config.yaml` whose
  one hook is `celebrimbor gate --fast`, and a `tests/known-bad/` directory.
  `--surfaces` additionally runs role inference and writes the pre-filled,
  ratify-me surface map (Tier 1 opt-in).
- `celebrimbor gate [--fast|--full]` — the one command, three tiers:
  - `gate --fast` — pre-commit tier: lint, types, format, known-bad, surface
    audit (when opted in). **Target < ~10s.**
  - `gate` (default) — PR tier: `--fast` + coverage ratchet + invariant ledger +
    impact gate. **Target < ~2min.**
  - `gate --full` — merge/release tier: default + mutation + any
    container/integration steps. As slow as it must be.
- `celebrimbor.gate(tier=...)` — the same, programmatic.
- `@celebrimbor.check(...)` — decorator registering an app's own check into the
  ordered registry the runner proves complete. This is the ONLY documented seam
  for app-specific checks; do not also expose a raw registry object.
- Config: `celebrimbor.toml` (or `[tool.celebrimbor]` in `pyproject.toml`) — for
  the **exceptions only**. Convention supplies the rest.

## Conventions (this is where "convention over configuration" lives)

- **Surface roles are inferred, then ratified — never silently accepted.**
  Inference is a naming heuristic (`verify_*`/`*_verifier` → verifier, `parse_*`
  → parser, `gen_*`/`build_*` → producer, side-effect-free signature → pure). It
  pre-fills each row it is confident about, marked `# inferred`. The surface gate
  stays **RED on any `# inferred` or unclassified row** until a human ratifies it;
  re-running `init` never overwrites a ratified row. Ratifying is a one-line
  confirm, not an authoring task.
- **Known-bad is a directory, not config.** Any file in `tests/known-bad/` must
  be rejected by some checker with the expected diagnostic, enforced
  automatically.
- **Ratchets auto-baseline** on first run in the pinned/CI environment; thereafter
  they only rise.

## The role taxonomy and its proof obligations

Eight roles; each names the kind of proof a callable of that role owes. This is
the heart of the obligation engine — a general theory of how a callable earns
trust.

| Role | Owes |
|---|---|
| `pure` | a property or unit test over its contract |
| `parser` | a unit test with malformed input that must be refused |
| `normalizer` | a property test (idempotence and folding) |
| `verifier` | a negative fixture that must turn it red |
| `producer` | proof through the verifier that inspects its artifact |
| `orchestrator` | an interaction test over its dependency edges |
| `adapter` | a contract test against fake and real backends |
| `presenter` | an integration or end-to-end run |

Roles are assigned by module default with per-callable overrides, never one row
per function. A callable that genuinely owes no direct proof is exempted by name
with a reason and a review date — never silently.

## The engines to build

1. **Surface inventory + audit.** Walk the app's source with `ast` and classify
   **without importing it** (so the completeness guarantee can never fall behind
   code that fails to import). The gate fails when a public callable exists that
   the surface map does not account for.
2. **Role inference.** The naming heuristic above, with the safe-direction and
   ratify-don't-overwrite rules (see scars).
3. **No-blind-verifier producer ledger.** Every `producer`-classified module must
   name an on-the-record negative fixture that turns its verifier red, or sit in a
   visible, shrinking pending allowlist. You cannot inherit a verifier that
   inspects nothing.
4. **Check registry + dual runner.** An ordered registry of checks, runnable from
   the CLI and under pytest, with a meta-test proving **no check escapes the
   runner**.
5. **Invariant ledger.** A declarative ledger (e.g. `invariants.yaml`) validated
   for referential integrity — every named enforcer resolves to a real callable,
   every critical promise keeps a real negative proof — that renders human docs
   and **fails on drift** between the ledger and the code.
6. **Change-impact gate.** Map a git diff → the surface role of each changed
   module → the invariant that owns it → a gap. Redden when a policy-role module
   changes with no invariant naming it. (Parameterize the source path prefix;
   inject the two ledgers.)
7. **Ratchets.** A coverage ratchet (per-module floor) and a mutation ratchet
   (survivor *identity*, see scars), each a committed baseline + a pure
   comparator + a reason-gated `--update`.
8. **Declarative fixtures + scenarios + baseline differ.** A known-bad provenance
   auditor (orphans caught both ways; the *right* checker with the *expected*
   diagnostic), a deterministic pairwise scenario generator, and a
   toolchain-stable baseline differ whose `--update` demands a recorded reason and
   whose own bite is proven by in-memory mutation.
9. **Commodity orchestration.** `gate` shells out to ruff / mypy / a formatter /
   pre-commit / coverage / a mutation tool with opinionated defaults and the
   no-silent-skip guard — no author-written shell script. **This layer is new
   build work; it is the adopter's first wedge, and it does not exist to copy.**

## Scars — hard-won constraints (build in as REQUIREMENTS; do not re-derive)

- **Fail closed, everywhere.** When the harness cannot prove something, it
  **refuses (red)**; it never estimates, defaults, or passes. This is the core
  invariant; every engine inherits it.
- **Every gate is itself proven by a negative fixture** that turns it red. Ship
  Celebrimbor's own per-gate negative fixtures — a gate that has never been
  observed to fail is a blind gate.
- **Classify without importing.** The surface inventory is AST-only, so a module
  that fails to import cannot silently drop out of the completeness count.
- **Inference is safe-direction and ratified, never trusted.** Inference only ever
  proposes **higher-obligation** roles and abstains to `unclassified` otherwise —
  it must **never** propose the low-obligation escape roles (`pure`, `presenter`),
  because a wrong guess there silently voids the very gates that key on role.
  Inferred rows are red-until-ratified; re-running never overwrites a ratified
  row. Inference shrinks the human's job; it never manufactures green.
- **Ratchets never baseline on a dev box.** Take the baseline only in the
  pinned/CI environment. A dev-box baseline inflates above CI's numbers and hands
  the adopter a red CI on day two. Provide no local `--update` path that can lower
  a floor without a written reason.
- **Low-floor meta-ratchet.** A floor recorded *below* a configured threshold is
  red until a human writes the reason — auto-baseline must not freeze weak
  coverage as false green.
- **Mutation invariant is survivor IDENTITY, not count.** The ratchet asserts
  *which* mutants survive, not how many — a changed set with the same count is a
  regression the count would miss.
- **No silent skip.** When a tool is expected (a trusted-environment promise is
  set) and absent, hard-fail; only warn-and-skip when no such promise is made.
- **Marker grammar is enforced.** A marked test with no assertion is rejected; an
  `xfail` must cite a declared limitation; an environment `skip` must name a
  declared capability. (Celebrimbor's own test suite obeys this.)
- **Producer override granularity.** The no-blind-verifier gate must catch a
  `producer` introduced by a per-callable *override* on a non-producer module, not
  only a module whose default is `producer`.

## Anti-goals for the builder (do NOT bring these across)

- Any book / edition / pandoc / LaTeX / ISBN / cover / plate concept.
- press's `design_major` scoping or "a fix must not change layout" semantics —
  those are a press-domain differ policy and must not follow the baseline differ
  into Celebrimbor.
- press house shims (its YAML I/O wrapper, its process-runner adapter) — use the
  standard library or a thin, documented port.

## Acceptance test — the definition of done

1. **Dogfood on press (the real gate).** press imports `celebrimbor`, keeps its
   own domain data (its surface map, its invariants, its fixtures), and its full
   quality gate stays green **byte-for-byte** through the swap. `celebrimbor` has
   **zero `press.` imports**, its **own test suite**, and its **own per-gate
   negative fixtures**.
2. **Cold-start a toy app (the adoption promise).** On a fresh five-module app:
   `celebrimbor init` + `celebrimbor gate --fast` passes in **under ten minutes**
   with no hand-wiring (Tier 0). `celebrimbor init --surfaces` then yields a
   red-until-ratified surface map with inference pre-filling the confident rows
   and abstaining (not guessing `pure`) on the rest.

## Open questions to resolve during the build

- **Heuristic inference vs. rigor** — the deepest tension: every obligation gate
  trusts the role map, the exact input inference populates. The safe-direction +
  ratify rules are the mitigation; validate they hold under a real app's messy
  naming.
- **Gate speed budget** — the `< ~10s` fast tier is load-bearing for adoption;
  measure it on a real repo, and decide what moves to the default tier if it
  slips.
- **Override ergonomics** — correcting a misclassified role must be one obvious
  line, or the convention promise breaks. Prototype the correction flow early.
