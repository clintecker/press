# Celebrimbor: a reusable quality-harness extracted from press

## The question and the short answer

Can press's quality machinery become a reusable, app-agnostic, **import-and-go**
harness? Yes. There is a real framework hiding inside press: a
**declarative-ledger + pure-validator + self-proving-gate engine** whose spine
runs through six of eight areas. The owner has already decided the terminal
state — a published `pip install celebrimbor` package, not a perpetually-internal
sub-package — so the question is not *whether* to publish but *in what order*.

The answer is a sequence, not a hedge. **Build the importable package inside the
press repo now (`src/celebrimbor/`, zero `press.` imports, its own tests and its
own negative fixtures); harden its conventions by dogfooding press as the first
consumer until press's gates stay green byte-for-byte through the refactor; then
publish.** Publishing is gated on *the seam holding press green*, not on a
hypothetical second consumer appearing — an internal-only package with no
published surface can never acquire the second consumer that would "justify" it,
so that trigger would never fire. The repo split itself (a second release
cadence, duplicated CI) is the one genuinely deferrable cost; everything that
makes Celebrimbor a framework — the runner inversion, the seam-cleaning, the
commodity-orchestration layer press never built — is worth doing now on its own
merits.

Two honest corrections to the earlier draft frame everything below:

- **The commodity 80% of `celebrimbor gate` — bundled ruff/mypy/format/pre-commit
  with opinionated defaults, plus the orchestrator that runs them — does not
  exist in press to extract.** press delegates all of lint/type/format to
  `pre-commit run --all-files` against its own `.pre-commit-config.yaml` and
  `pyproject.toml`. That layer is **new BUILD work**, and it is the wedge a new
  adopter takes first.
- **Role *inference* from naming does not exist in press.** `surfaces.scaffold()`
  writes every new module as the literal string `unclassified`; there is zero
  naming heuristic anywhere. Inference is new work, it is trust-sensitive, and it
  is sized separately below — not "parameterize three constants."

## North star: convention over configuration, import-and-go

The product goal is **omakase for code quality**: `pip install celebrimbor`, run
`celebrimbor init`, and a working quality harness stands up with near-zero
wiring — Rails/Django philosophy applied to validation, verification, and
testing. You do not assemble a thousand pieces; configuration is for the
exceptions, never the setup.

Convention-over-configuration lives or dies on **strong, correct opinions**, and
several of those opinions are net-new. To keep the promise honest, the harness
ships in two tiers, and the north star is explicit about which is which:

- **Tier 0 — green in under ten minutes, near-zero wiring.** `init` writes
  opinionated defaults (ruff, mypy, formatter, pytest/coverage, a
  `.pre-commit-config.yaml` whose hook is `celebrimbor gate --fast`) and a
  `tests/known-bad/` convention. `gate --fast` runs lint + types + format +
  known-bad against those defaults and **passes on a fresh repo**. The
  coverage ratchet auto-baselines (see below). This is the layer that kills the
  wiring problem, and an adopter takes it *without believing any theory of
  testing*.
- **Tier 1 — opt-in, deliberate authoring.** Surface-role completeness, the
  no-blind-verifier producer ledger, the invariant ledger, the impact gate, and
  mutation are **off until the app opts in**, so surface-completeness does not
  redden the gate on day one. Celebrimbor makes this layer *mechanical and
  un-rottable*, not *free*: it is real authoring, and it is the differentiator
  layered on top, not the entry fee.

What convention-over-configuration means per pillar:

- **Surface roles are *proposed* by inference, then ratified — never silently
  accepted.** When the app opts into surface completeness, `init` runs a naming
  heuristic (`verify_*`/`*_verifier` → verifier, `parse_*` → parser,
  `gen_*`/`build_*` → producer) and pre-fills each row it is confident about,
  marked `# inferred`. The gate stays **red on any `# inferred` or `unclassified`
  row** until a human ratifies it; re-running `init` never overwrites a ratified
  row. Crucially, **inference only ever proposes higher-obligation roles and
  abstains to `unclassified` otherwise** — it never proposes the low-obligation
  escape roles (`pure`, `presenter`), because a wrong guess there silently voids
  the very gates that key on role. Inference shrinks the human's job from
  "author 109 rows from scratch" to "ratify N proposals and correct the handful
  it misclassifies"; it does not manufacture green.
  *(Conflict resolved: reviewers split between "green where inference is
  confident" and "red until a human confirms." Decision: red-until-ratified, but
  inference pre-fills the row so ratification is a one-line confirm, not an
  authoring task. Safety beats day-one greenness on the one input every
  obligation gate trusts.)*
- **Known-bad is a directory, not config.** A file dropped in `tests/known-bad/`
  must be rejected by some checker with the expected diagnostic, enforced
  automatically.
- **Ratchets auto-baseline — but never below the floor, and never on a dev box.**
  The first `gate` run in the pinned/CI environment records the coverage and
  mutation floor behind a recorded reason; thereafter it only rises. A fresh app
  baselined *below* the low-floor threshold is **red until a human writes the
  reason** (press's `LOW_FLOOR_ALLOWED` meta-ratchet, carried in as a first-class
  feature), so auto-baseline cannot freeze weak coverage as false green. The
  baseline is taken **in CI or the pinned container, not on first local run** —
  a dev-box baseline inflates above CI's numbers and hands the adopter a red CI
  on day two (this is press's own "never `--update` locally" scar).
- **The gate is one command with three tiers.** `celebrimbor gate`,
  `gate --fast`, `gate --full` — a real Python entrypoint with opinionated
  defaults that shells out to the commodity tools and composes the extracted
  engines, needing **no author-written shell script**. Same command, different
  tier flag:
  - `gate --fast` — pre-commit tier: lint, types, format, known-bad, surface
    audit (when opted in). Seconds. Target **< ~10s**.
  - `gate` (default) — PR tier: `--fast` + coverage ratchet + invariant ledger +
    impact gate. Target **< ~2min**.
  - `gate --full` — merge/release tier: default + mutation + container/integration
    steps. As slow as the container gauntlet needs to be.
  *(Conflict resolved: earlier draft used two flags `--fast|--full`; three tiers
  are required to express "run ratchets but not the ten-minute container." Decision:
  three tiers, matching press's own `--quick`/default/`--full`.)*

The import-and-go surface stays tiny: `celebrimbor init`, `celebrimbor gate`,
`celebrimbor.gate()` (programmatic), and a `@celebrimbor.check` decorator so an
app plugs its own domain checks into the same runner. The decorator is the one
idiom for the check seam (it registers into the same ordered registry the runner
proves complete); we do not also expose a raw registry object in the docs.

## Prior art and where Celebrimbor sits

The one-line category claim: **Celebrimbor is fitness functions for
test-obligation completeness** — the only tool that makes *application code*
prove each *callable* earns its trust, *and* ships the commodity ladder as
omakase. The buy-vs-build rebuttal a prospective adopter can repeat: SonarQube is
a service that gates *metrics*; cookiecutters wire-and-walk-away; ArchUnit scopes
to *structure*; none classifies a callable's obligation or refuses a blind
verifier. Celebrimbor is the intersection.

The commodity 80% is owned by mature tools; **mark every pillar build-vs-adopt
against this map:**

- **Service-scorecard products — coarse, not per-callable.** Backstage Tech
  Insights, Cortex, OpsLevel; SonarQube/SonarCloud (metric-threshold gates).
  Closest product-shaped relatives; none classify a callable's obligation.
  **Adopt** the pattern; do not rebuild.
- **Declarative check-engines with a registry + generated docs — but for data or
  patterns.** dbt, Great Expectations/Soda (closest *shape*: declarative
  expectations + run engine + docs, but for data); Semgrep (declarative code
  patterns); OPA/Conftest, Checkov (policy-as-code). **Adopt** the
  declarative-ledger + pure-comparator shape — press already has it.
- **Day-one wiring — scaffolds, not a living engine.** PyScaffold,
  hypermodern-python cookiecutter, Nx generators, Rails convention. **Adopt** for
  bootstrap; they provide no ongoing obligation gate and then walk away.
- **Single-pillar best-of-breed to ORCHESTRATE — with two honest exceptions.**
  ArchUnit/import-linter/Tach (structural fitness), semantic-release/changesets
  (release), in-toto/SLSA (step attestation — nearest cousin to
  no-blind-verifier): wrap, don't rebuild. **The exceptions:** press's coverage
  and mutation ratchets are *bespoke and do not map onto* diff-cover or
  mutmut, and Celebrimbor keeps them bespoke on purpose (see the extraction map).
  Coverage: a **per-module branch floor**, which diff-cover's PR-line-diff model
  cannot express — Celebrimbor wraps `coverage.py` measurement, not diff-cover.
  Mutation: an AST mutator that only yields a usable gate on a **hand-picked set
  of pure, toolchain-free modules** (press mutates four; `verify_formats` scores
  7/92 and is excluded for cause) — it does not generalize to "all apps," so it
  is opt-in, app-nominates-targets, and out of the day-one ladder.

**The genuinely unoccupied cell** — the only defensible thing to *build* — is a
framework that makes application code prove each public unit earns its trust: the
role-classified obligation taxonomy, the AST completeness gate, the
no-blind-verifier producer ledger, and the impact-refuses-an-unclassified-change
gate. One caveat kept in full view: press today enforces **classification
coverage** (every callable has a role) plus two role-specific gates (the producer
ledger and the invariant ledger). It does **not yet** enforce "each role
discharges its declared obligation" — `quality/surfaces.yaml` says so in a
comment, and that per-role enforcement is deferred press issue #80. So the
extractable differentiator is *classification coverage + producer gate + ledger +
impact*; full per-role obligation enforcement is future BUILD, not something
sitting in the code waiting to be lifted. We do not oversell it.

## What press proved is reusable

The load-bearing idea across every surviving area is one sentence: **make the
quality bar a committed declarative artifact that a pure comparator gates, let it
move only through an explicit reason-carrying `--update`, and prove every gate
bites with a named negative fixture.** That idea is app-agnostic; most of the
code implementing it for press is not, and that is the correct division of labor.
The disciplines press proved, each with its origin file:

- **Mechanical, un-rottable inventory.** `surfaces.public_callables()`
  (`src/press/surfaces.py`) walks `src/press/*.py` with `ast.parse` — classifies
  source without importing it, so completeness can never silently fall behind the
  code. (Note: it *inventories*; it does not *infer* — inference is new.)
- **Role-with-proof-obligation taxonomy.** The eight roles
  (`pure`/`parser`/`normalizer`/`verifier`/`producer`/`orchestrator`/`adapter`/
  `presenter`) and what each owes live as data in `quality/surfaces.yaml`, not
  hardcoded.
- **No-blind-verifier.** `check_producers_are_verified()`
  (`src/press/selftest.py`) forces every `producer` to name an on-the-record
  negative fixture that turns its verifier red, or sit in a shrinking allowlist.
- **Monotonic ratchets.** `scripts/coverage_ratchet.py` (per-module branch floor,
  shadow-PATH determinism, `LOW_FLOOR_ALLOWED` low-floor-needs-a-reason
  meta-ratchet) and `scripts/mutation_ratchet.py` (AST mutation in a shadow
  symlink tree, survivor-*identity*-not-count as the invariant, four hand-picked
  `TARGETS`).
- **Referential-integrity invariant ledger.** `src/press/invariants.py` validates
  `quality/invariants.yaml`, renders `docs/INVARIANTS.md`, fails on drift; its
  default proof-resolver **fails closed** on an unrecognized reference.
- **Completeness meta-gates.** The ordered `CHECKS` list plus
  `test_every_check_is_orchestrated` (`tests/test_selftest_checks.py`) prove
  nothing escapes the runner by scanning the module for `check_*` and diffing
  against the registered set; `check_ledger_completeness` proves every critical
  invariant keeps a fast-tier proof.
- **Change-impact mapping.** `src/press/impact.py` maps git diff → surface role →
  owning invariant → gap.
- **Marker-grammar test discipline.** `tests/pytest_invariants.py` enforces that a
  marked test cites a real invariant with `layer`/`proof`, every `xfail` cites a
  limitation, every environment `skip` names a capability, and an assertionless
  marked test is rejected.
- **Declarative fixtures & scenarios.** `quality/fixtures.yaml` +
  `src/press/fixture_provenance.py` (known-bad-must-be-rejected, by the *right*
  checker with the expected diagnostic); `quality/scenarios.yaml` +
  `src/press/scenarios.py` (deterministic pairwise covering set).
- **Self-proving baseline differs.** `tests/visual_harness.py` /
  `tests/structure_harness.py` extract toolchain-stable geometry and diff it
  under a pure tolerance-scoped comparator whose `--update` demands a reason and
  whose bite is proven by in-memory mutation.
- **No-drift, no-skip gate composition.** `scripts/verify.sh` (cheap-failure-first
  ladder), the one-body-two-callers pattern (`scripts/gauntlet-steps.sh`), and
  the no-silent-skip guard keyed on the trusted-image promise
  (`src/press/verify_formats.py`).
- **Resumable release/contract machine.** `scripts/release.sh` and
  `.github/workflows/release-contract.yml`.

## Extraction map

Verdicts: **Core** = extract the mechanism. **Adapter** = the data/extractors an
app supplies. **Leave** = template + docs, not library code. **BUILD** = new work,
not present in press to extract.

| # / Area | Mechanism | Reusable core | Press-specific / new | Verdict |
|---|---|---|---|---|
| 0 · `init` + `gate` CLI + commodity bundle | opinionated ruff/mypy/format/pre-commit defaults; the tier orchestrator that shells to them and composes the engines | — (press owns none of this; it delegates to `pre-commit run --all-files`) | the entire bundle and orchestrator | **BUILD (new)** — the wedge; MVP |
| 0b · Role inference | naming heuristic → proposed roles, safe-direction only | — (press writes `unclassified`) | the heuristic table, confidence/abstention, ratify-don't-overwrite | **BUILD (new)** — MVP-adjacent |
| 1 · Surface role system | AST inventory + module-default/override classify + audit gate (`surfaces.py`, `surfaces.yaml`) | `public_callables`/`classify`/`audit`/`scaffold`; taxonomy as config; stale-ref + reason/review-date validation | module→role rows; `doctor`/`selftest` exemptions; `SRC`/`CONFIG` constants; `yamlio` shim | **Core** |
| 2 · No-blind-verifier | producer set from `surfaces.yaml` partitioned against proven/pending registries (`selftest.py`) | `check_producers_are_verified` + its four failure modes; proven-set/pending-allowlist pattern | `PRODUCER_REJECTION_PROOFS` contents | **Core (mechanism) + Adapter (data)** — **fix the override hole** (see below) |
| 3 · Ratchets | committed JSON baseline + pure `compare()` + reason-gated `--update` | per-module floor + shadow-PATH determinism + low-floor-reason meta-ratchet; AST mutation + shadow-tree + survivor-identity | `HIDDEN_TOOLS`/`DESELECT`/`TARGETS` values; baseline contents | **Core** (wraps `coverage.py`, not diff-cover; mutation opt-in) |
| 4 · Runner + invariant ledger | ordered `CHECKS` run by CLI + pytest; ledger validator + renderer | registry + dual runner + "no check escapes" meta-test; schema/dup/enforcer-resolves/critical-needs-negative validator; pytest marker plugin | ~30 press `check_*` bodies; `press.` prefix; `check_`/`fixture:` grammar; `KNOWN_BAD` dir; branded prose | **Core — runner needs inversion; ledger needs a proof-resolver seam** |
| 5 · Impact / surface-gap gate | git-diff → role → invariant → gap (`impact.py`) | `changed_modules`/`analyze`; `POLICY_ROLES` rule | hardcoded `"src/press/"` prefix; `adapters.process_runner` shim | **Core** (parameterize prefix, inject ledgers; iterate overrides) |
| 6 · Declarative fixtures/scenarios/harnesses | provenance auditor; pairwise generator; extract→pure-diff→reason-gated-update differ | auditor (orphans both ways + inline-`expect`); deterministic pairwise + both-ways + high-risk gates; baseline-differ skeleton with self-proving negatives | fixtures entries; scenario dimensions; feature extractors; `design_major` scoping | **Core (auditor + generator + skeleton) / Adapter (extractors)** |
| 7 · Composed gate + no-silent-skip | layered ladder; one-body-two-callers; env-promise strictness | the no-silent-skip guard helper (~10 lines) **and the cheap-fail-first tier ordering** promoted into the `gate` runner's defaults | the `verify.sh` step list; gauntlet body; `PRESS_TOOLCHAIN` literal | **Core helper + ordering** (rest is template) |
| 8 · Release / contract state machine | resumable, remote-checked release; immutable-tag contract | the documentable *structure*: preflight-before-mutation, idempotent steps, poll-gate-before-float | `clintecker/press@vN` rewriting; floated-major convention; toolchain digest | **Leave (template)** — welded to press's GitHub-Actions topology |

**Two extraction corrections carried in:**

- **Fix the override soundness hole.** press's producer gate collects only modules
  whose *default* role is `producer`, and `impact.analyze` keys off the module
  default via `_role_of` — so a producer introduced by a per-callable *override*
  (e.g. `aesthetic.write_tex_overrides`, `edition.build`, `yamlio.dump`) escapes
  the no-blind-verifier gate entirely. Celebrimbor's extraction **iterates
  overrides, not just defaults**, raising the gate to true callable granularity;
  press inherits the fix. (If instead we ever ship module-default granularity, the
  docs must say so plainly — but the intended fix is to close the hole.)
- **Keep both the naming scan and the registry.** A `@celebrimbor.check` decorator
  makes escaping the registry nearly impossible by construction but *loses* the
  ability to catch a `check_*` someone wrote and forgot to decorate.
  `runner.py` keeps the AST/naming scan *and* the registry, and the meta-test
  asserts `scan-set == registry-set`.

## Celebrimbor package shape

Centered on the four conventions an adopter actually touches — **init, gate,
inference, and the check registry** — with the extracted engines behind them.
`[MVP]` marks the bounded first increment; `[Tier 1]` marks opt-in
obligation-engine modules.

```text
celebrimbor/
  cli.py             # `init` and `gate` entry points                      [MVP]
  init.py            # writes opinionated defaults: ruff, mypy, formatter,  [MVP]
                     #   pytest/coverage, .pre-commit-config.yaml (hook =
                     #   `gate --fast`), quality/*.yaml skeletons, known-bad/.
                     #   An app's own [tool.ruff] etc. always wins the merge.
  gate.py            # the tier orchestrator (fast/default/full). Shells to  [MVP]
                     #   ruff/mypy/format/coverage-ratchet/mutation-ratchet,
                     #   composes the engines, cheap-fail-first ordering,
                     #   exit-code contract, tool-availability policy. NEW work.
  infer.py           # naming heuristic → proposed roles; safe-direction     [MVP]
                     #   (never proposes pure/presenter); abstains to
                     #   unclassified; ratify-don't-overwrite. NEW work.
  surfaces.py        # public_callables/classify/audit/scaffold — Area 1    [Tier 1]
                     #   params: src_dir, config_path, unclassified_modules, yaml_loader
  runner.py          # the INVERTED check-runner — Area 4                   [MVP core]
                     #   @check decorator + CheckRegistry + run_all + pytest_params
                     #   + naming-scan == registry-set meta-test helper
  producers.py       # check_producers_are_verified — Area 2 (iterates overrides) [Tier 1]
  ledger.py          # invariants.py validator + renderer — Area 4         [Tier 1]
                     #   params: package_name, proof_resolver (protocol), fixture_dir
  impact.py          # git-diff → role → invariant → gap — Area 5          [Tier 1]
                     #   params: path_prefix, policy_roles, process_runner
  ratchet/
    coverage.py      # per-module floor + low-floor-needs-reason — Area 3   [MVP]
    mutation.py      # AST mutation, shadow tree, survivor-identity — Area 3 [Tier 1, opt-in]
    baseline.py      # extract → pure-diff → reason-gated-update skeleton — Area 6 [Tier 1]
  fixtures.py        # provenance auditor — Area 6                          [MVP]
  scenarios.py       # deterministic pairwise + both-ways + high-risk — Area 6 [Tier 1]
  pytest_plugin.py   # marker grammar + index emission — Area 4            [Tier 1]
  skip_guard.py      # no-silent-skip helper — Area 7                       [MVP]
  templates/         # OPTIONAL CI escape hatch only: release.sh skeleton,
                     #   release-contract.yml, and app-specific build/exercise
                     #   steps. NOT required for `gate` to run — Areas 7 & 8.
```

The shell templates are an **optional escape hatch for app-specific build steps**,
not the gate. The default `gate` needs no author-written `verify.sh`.

**The declarative config an app writes** (same filenames as press):

- `quality/surfaces.yaml` — the `roles:` block plus a `modules:` map. When surface
  completeness is opted into, `init` pre-fills rows via inference, marked
  `# inferred`; the gate forces ratification.
- `quality/invariants.yaml` — the app's promises, same schema.
- `quality/fixtures.yaml` — provenance ledger for known-bad files (inline `expect`).
- `quality/scenarios.yaml` — optional-feature dimensions and high-risk interactions.
- `quality/coverage-baseline.json`, `quality/mutation-baseline.json` — produced by
  `--update` in the pinned/CI environment, behind a recorded reason.

**The plugin points (the seams where an app injects its facts):**

1. **`@celebrimbor.check`** — the app's checks enter the one ordered registry. The
   naming-scan == registry-set meta-test runs against the app's module.
2. **`proof_resolver` — a protocol, not a bare callable.** Not `str → str|None`
   but `resolve(ref) -> ProofKind` **and** `exists(ref) -> bool` (or one
   `validate(ref) -> Problem|None`), because press's ledger doesn't just *label* a
   proof reference — it *validates the referent exists* (an enforcer resolves to a
   real `module.function`; a `negative` names a real check or fixture file). A
   consumer resolver **must fail closed**: an unknown reference is invalid, so an
   app cannot accidentally write a resolver that blesses every reference and guts
   the ledger.
3. **`surfaces.yaml roles:` — reserved vs. extensible.** The taxonomy is data, but
   certain names are load-bearing framework keywords: `producer` (the ledger and
   no-blind-verifier gate filter on it) and whichever roles `POLICY_ROLES` binds
   for the impact gate. An app **may add roles and mark which are policy-bearing;
   it may not rename the reserved ones** without losing the gate that keys on them.
4. **`FeatureExtractor` protocol** — `extract(artifact) -> dict` +
   `compare(a, b, tolerances) -> drift`. The skeleton, reason-gated update guard,
   and negative-proof discipline are inherited; only *which features are stable*
   is app knowledge.
5. **Ratchet config object** — `HIDDEN_TOOLS`, `DESELECT`, `TARGETS`, `src_dir` as
   config, not module constants. `TARGETS` is never inferred — adding a module is
   a human promise that its tests pin it tightly.
6. **pytest vocab** — `capabilities`, `layers`, `polarities` sets passed to the
   plugin.

## API and schema contract

Because apps *commit* `quality/*.yaml` and *import* `gate`, `check`, and the
protocols, Celebrimbor needs the same stability law press lives by. The public
surface — `celebrimbor.init`, `celebrimbor.gate`/`gate()`, `@celebrimbor.check`,
the `proof_resolver` and `FeatureExtractor` protocols, and the CLI exit-code
contract — follows SemVer. **The YAML schemas and the reserved role names are
part of the major-version contract:** a schema field rename or a change to a
policy-bearing role name is a breaking change, exactly analogous to press's own
"schema/design changes require a new major." Celebrimbor's own CI runs
`celebrimbor gate` on Celebrimbor and releases via the templated `release.sh`
pattern — the quality framework gates itself.

## Adoption path

Target: **a newcomer is green in under ten minutes.**

**First run (Tier 0 — a five-module toy app):**

```console
$ pip install celebrimbor
$ celebrimbor init
  wrote  pyproject.toml        (+[tool.ruff] [tool.mypy] [tool.pytest.ini_options])
  wrote  .pre-commit-config.toml  (hook: celebrimbor gate --fast; ruff, shellcheck,
                                    yamllint, pymarkdown when their binaries exist)
  wrote  quality/coverage-baseline.json   (empty)
  made   tests/known-bad/
$ celebrimbor gate --fast
  ruff ......... ok      mypy ......... ok
  format ....... ok      known-bad .... ok (no fixtures yet)
  PASS  (3.1s)
```

Green on a fresh repo, in seconds. That is the wedge.

**Opting into the obligation engine (Tier 1), one seam at a time:**

```console
$ celebrimbor init --surfaces        # inference pre-fills proposals
  proposed 18 roles (# inferred), abstained on 4 (unclassified)
$ celebrimbor gate
  surface-audit ... RED  (4 unclassified, 18 awaiting ratification)
```

Correcting a misclassification is **one line** in `surfaces.yaml`:

```yaml
modules:
  loader: {default: pure, overrides: {load: parser}}   # was inferred pure; ratified
```

Then the remaining wiring, borne once, each step un-rottable thereafter:

1. Ratify/correct the inferred roles; classify the abstentions. (`init --surfaces`
   scaffolds the module list mechanically.)
2. Write `invariants.yaml` promises plus a `proof_resolver`, or adopt the default
   grammar and write `@check` functions.
3. `--update` the ratchet baselines **in CI/container** behind a recorded reason.
4. Write known-bad fixtures with inline `expect` comments; wire a `FeatureExtractor`
   per artifact type for the baseline harness.
5. Nominate mutation `TARGETS` (opt-in, pure modules only); wire `skip_guard` to
   the app's trusted-environment promise.

**Tool availability.** Every tier declares its required tools. In an untrusted
environment a missing tool **warns and skips**; in a trusted environment — the
app's promise, named by the `CELEBRIMBOR_TRUSTED_ENV` convention (press's
`PRESS_TOOLCHAIN` generalized) — a missing tool **hard-fails**. That is the
operable heart of "no silent skip," and it covers Docker-absent (so `--full`
can't run), a mutmut-less/target-less project, and a missing linter binary alike.

**How press dogfoods it back.** press keeps all its domain content and imports the
engine: `selftest.py` collapses from ~1781 lines to ~30 `@check` bodies plus a
registry; `surfaces.py`/`impact.py`/`invariants.py`/`fixture_provenance.py`/
`scenarios.py`/`pytest_invariants.py` shrink to thin config + injection;
`quality/*.yaml` are untouched. If the extraction is clean, press's gates keep
passing byte-for-byte, and that green run *is* the proof the seam is right —
matching press's own law that "a green pip install is not a working pipeline;
prove against a real consumer."

**But dogfood-green proves preservation, not methodology.** press's rigor comes
from its hand-forged negative fixtures, not the engine alone. So Celebrimbor
**ships its own per-gate negative fixtures**, proving each gate bites
independently of press: a deliberately-misclassified surface the audit must
catch; a producer with a blind verifier the ledger must redden; a coverage
regression the ratchet must catch; a survivor-identity change the mutation gate
must catch; a below-floor baseline the low-floor meta-ratchet must redden. This
is press's central law — "a guard you never test is a guard you can't trust" —
applied to the framework itself.

## Effort, risk, and recommendation

**The wedge and the ICP.** The ideal second consumer is a solo/small-team Python
CLI or library maintainer who already values ratchets and reproducible CI but
hates wiring them. The feature they adopt *without believing the philosophy* is
Tier 0 — `init` + commodity `gate` + auto-baselined coverage ratchet + known-bad.
The obligation engine is sequenced *behind* that wedge, never in front of it.

**MVP cut.** The bounded first increment is `init` + `gate` (three tiers) +
auto-baselined coverage ratchet (with the low-floor gate) + known-bad convention +
the inverted `runner` + `infer` + `skip_guard`. The no-blind-verifier ledger, the
invariant ledger, the impact gate, mutation, scenarios, and the baseline harness
are Tier 1, layered on after.

**Sizing (internal seam-hardening, no second repo yet):**

| Piece | Effort | Note |
|---|---|---|
| **`gate` CLI + tier orchestrator + tool-availability policy** | ~3–5 days | **NEW; the wedge.** press owns none of this |
| **`init` scaffolder + opinionated defaults bundle** | ~2–3 days | **NEW.** ruff/mypy/pre-commit/coverage defaults + override story |
| **role inference (`infer.py`)** | ~2–3 days | **NEW.** heuristic table, safe-direction abstention, ratify-don't-overwrite |
| **runner inversion** | ~3–5 days | **the hard one:** module-level `CHECKS` → registry, keeping dual CLI/pytest + naming-scan meta-test working. Critical-path spike — gates everything; give it a fallback if inversion proves leaky |
| coverage ratchet + low-floor gate | ~1–2 days | config-object the knobs; carry `LOW_FLOOR_ALLOWED` |
| surfaces | ~1–2 days | parameterize constants; wire inference output |
| impact | ~1–2 days | parameterize prefix, inject ledgers, iterate overrides |
| ledger validator + proof-resolver protocol | ~2–3 days | inject package name, resolver, doc template; fail-closed |
| producer gate (override-granular) | ~1–2 days | close the override hole |
| fixture provenance | ~2 days | parameterize schema vocab + expect regex |
| pytest plugin | ~2 days | parameterize vocab sets |
| mutation ratchet + baseline-differ skeleton | ~2 days | opt-in; pattern + pure helpers |
| Celebrimbor's own per-gate negative fixtures | ~2 days | proves each gate bites |
| **Total internal** | **~3–5 weeks** | band, not point — inference and the two CLIs are new, and the runner inversion destabilizes press's own proof spine |
| Second-repo split (CI, packaging, release, docs) | ~1 week + perpetual cadence tax | the one genuinely deferrable cost |

**Coupling risks that make it hard:**

- **The selftest monolith** (~1781 lines mixing the generic runner with 30+ press
  bodies) is the single inversion-of-control blocker. Everything else is
  parameterization; this one needs real inversion, and it refactors the spine of
  press's own proof — a destabilization risk for a reuse payoff that is deferred.
- **The import cluster** `impact → invariants → surfaces → selftest` is tight —
  good cohesion (it is genuinely one engine) but it extracts all-or-nothing.
- **House shims** `yamlio` and `adapters.process_runner` must be vendored or
  replaced with stdlib. Minor but pervasive.
- **Design-contract leakage.** `design_major` scoping and "a fix must not change
  layout" semantics are press-domain and must not follow the differ into
  Celebrimbor.

**Recommendation (dogfood-then-publish):**

1. **Do now:** build `src/celebrimbor/` inside the press repo — the MVP first
   (`gate`, `init`, `runner` inversion, `infer`, coverage ratchet, `skip_guard`,
   known-bad), then the Tier 1 engines (areas 1, 2, 5, the ledger, 6) — with
   **zero `press.` imports**, its **own test suite**, and its **own per-gate
   negative fixtures**. A strict improvement even if no second app ever appears:
   it retires the monolith and gives press a legible internal architecture.
2. **Harden by dogfood:** press imports the engine and keeps its domain data; the
   proof it is done is press's gates staying green byte-for-byte.
3. **Publish** once the seam holds press green — *this is the trigger, not a second
   consumer appearing.* The internal boundary means the split is then a
   `git filter-repo` + a `pyproject`, not a rewrite.
4. **Template, don't extract:** ship areas 7 and 8 as `celebrimbor/templates/`
   plus one docs page on the patterns. Their code is welded to GitHub Actions and
   press's floated-tag topology; a library abstraction over "how you release"
   would be leaky.

*(Conflict resolved: the earlier draft gated publishing on "a real second consumer
exists." Decision: publishing is gated on the seam holding press green, per the
owner's stated goal — an unpublished internal package can never acquire the
second consumer that would justify it. Only the repo-split *mechanics* are
deferred, not the decision to publish.)*

## Open questions and risks

The sharpest unresolved concerns the leads raised, kept visible rather than
papered over:

- **Heuristic inference vs. rigor — the deepest tension.** Every obligation gate
  trusts the role map, which is the exact input inference auto-populates, in the
  *lower-obligation* direction if it guesses wrong. Our mitigations —
  never propose `pure`/`presenter`, abstain to `unclassified`, red-until-ratified
  — are opinions, not proofs. Open: is there a naming corpus that makes inference
  accurate enough to feel omakase without ever softening a gate? If not, the honest
  fallback is "inference pre-fills, human ratifies everything," which is less
  magical but sound. We chose sound.
- **Gate speed vs. adoption.** The budgets (`--fast` < ~10s, PR < ~2min) are
  targets, not measurements — we have not yet clocked press's own ladder per tier.
  If `--fast` cannot stay under ~10s with mypy in the loop, pre-commit ergonomics
  erode and adopters disable the hook. Open: measure before promising.
- **Override ergonomics.** "Correct a misclassification in one line" is the
  strongest DX claim, and it is real in the YAML `overrides:` idiom — but it is a
  YAML edit, not a code-site annotation. Open: is a `@celebrimbor.role("verifier")`
  decorator at the callsite worth the second surface, or does one canonical place
  (the YAML) beat two? Current answer: one place, the YAML.
- **The differentiator is partly greenfield.** press enforces classification
  coverage, not full per-role obligation discharge (#80). "Fitness functions for
  test-obligation completeness" is the *destination*; the shipped engine proves
  classification + producer + ledger + impact. Open: how much of #80 lands in the
  MVP vs. later.
- **Mutation does not generalize.** The bespoke mutator is a usable gate only on
  hand-picked pure, toolchain-free modules. For most apps it will either mutate
  untestable code (noise) or require the wiring omakase promises away. It stays
  opt-in and out of the day-one ladder; whether it earns its place in a generic
  tool at all is open.
- **Runner-inversion leakage.** Inverting the 1778-line monolith while preserving
  dual CLI/pytest execution *and* the naming-scan == registry meta-test *and*
  press's green run is the critical path. If inversion proves leaky, the fallback
  is a thinner registry that wraps rather than replaces the CHECKS list — worse
  architecture, but it ships.

## Non-goals

Celebrimbor is deliberately *not*:

- **Not a test-runner replacement.** It composes pytest, coverage, and pre-commit;
  it gates the *strength and completeness* of a suite and never executes tests in
  place of the runner.
- **Not app logic, and not a book pipeline.** No ISBN/EAN arithmetic, no coverwrap
  detectors, no PDF/EPUB/DOCX extractors, no editorial checkers. Every domain
  checker, verifier, and feature extractor stays in the consuming app. Books
  consume press; press (and other tools) consume Celebrimbor.
- **Not the release/distribution mechanism.** `release.sh` and
  `release-contract.yml` port as templates and a documented pattern, not library
  code. Celebrimbor does not know how any app ships, does not own tag conventions,
  and does not name trust-layer checks.
- **Not a coverage/quality *number*.** It never asserts a repo-wide percentage or a
  fixed kill count. It gates *regression and completeness*: floors only rise (and
  never below the reason-gated low floor), survivor identity is the invariant,
  every critical promise keeps a real negative proof.
- **Not a passing-gate generator.** The obligation engine (Tier 1) is honestly red
  until wired; it refuses to manufacture false green. Auto-baseline never freezes
  weak coverage as green — a below-floor baseline is red until a human writes the
  reason.
- **Not a config auto-populator.** Inference *proposes*; it never *confirms*. Every
  role ratification, invariant, proof, fixture, and baseline reason is a human
  decision the gate forces — mechanical maintenance, human judgment.
- **Not a philosophy tax on day one.** Tier 0 must deliver value before an adopter
  buys into the obligation engine. If the commodity gate did not stand alone, the
  framework would read as "believe our theory of testing or get nothing" — which
  is adoption death. The wedge earns the right to sell the differentiator.
