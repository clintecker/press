# Celebrimbor: a reusable quality-harness extracted from press

## The question and the short answer

Can press's quality machinery be extracted into a reusable, app-agnostic harness? Yes — there is a genuine framework hiding inside press: a **declarative-ledger + pure-validator + self-proving-gate engine** whose spine runs through six of eight areas. But the decisive fact is that today the reuse population is exactly one: press is the only consumer, and Celebrimbor's future consumers would be *other Python tools*, not books (books consume press, not this harness). The honest verdict is therefore split by cost: harden the seams inside press now as an internal `celebrimbor` sub-package with its own tests and zero `press.` imports — that captures ~90% of the value at ~30% of the cost — and defer minting a separate published repo until a real second consumer exists, because the repo split is the expensive, perpetual-tax step and the internal boundary keeps it cheaply reversible.

## Prior art and where Celebrimbor sits

The commodity 80% of a quality harness is thoroughly owned by mature, slick
tools; the distinctive layer is not. No single framework bundles all of this
into one adopt-and-go product, but several own adjacent cells — knowing which
is what keeps Celebrimbor from reinventing them. **Mark every pillar
build-vs-adopt against this map.**

- **Slick quality-standard products, but service/metric-coarse, not
  per-callable.** Backstage Tech Insights / Soundcheck, Cortex, OpsLevel
  (service scorecards: "does this *service* have tests/an owner/a runbook");
  SonarQube/SonarCloud (coverage + new-code quality gates + static analysis, as
  metric thresholds). Closest *product-shaped* relatives; none classify a
  *callable's* test obligation. **Adopt** their pattern; do not rebuild.
- **Slick declarative check-engines with a registry + generated docs — but for
  data or patterns.** dbt and Great Expectations / Soda (the closest *shape* to
  the feel Celebrimbor wants — declarative expectations + run engine + docs +
  lineage — but for data pipelines); Semgrep (declarative *code* patterns +
  shared registry + autofix); OPA/Conftest, Checkov (policy-as-code). **Adopt**
  the declarative-ledger + pure-comparator shape (press already has it).
- **Day-one quality wiring — scaffolds, not a living engine.** PyScaffold, the
  hypermodern-python cookiecutter, Nx generators, Rails convention: they wire
  pre-commit/mypy/coverage/tox on init, then walk away. **Adopt** for the
  bootstrap step; they provide no ongoing obligation gate.
- **Single-pillar best-of-breed to ORCHESTRATE, never rebuild.** Stryker/mutmut
  (mutation), ArchUnit/import-linter/Tach (structural fitness functions),
  diff-cover/Codecov (coverage ratchets), semantic-release/changesets (release),
  in-toto/SLSA (pipeline-step attestation — the nearest cousin to
  no-blind-verifier). Celebrimbor should shell out to / wrap these.

**The genuinely unoccupied cell** — and therefore the only defensible thing to
*build* — is a coherent framework that makes *application code* prove *each
public unit earns its trust*: the role-classified **test-obligation** taxonomy,
the AST **completeness gate**, the **no-blind-verifier** producer ledger, and
the **impact-refuses-an-unclassified-change** gate, at *callable* granularity.
The nearest philosophy is the "fitness functions" movement (Neal Ford et al.;
ArchUnit/import-linter are its libraries) — but that is scoped to *structure and
dependencies*, and is a movement, not a slick product. Celebrimbor is
best positioned as **"fitness functions for test-obligation completeness."**

**What this means for scope.** The value is not the bundle — the bundle already
exists as an assembly of excellent tools. The value is the thin novel
methodology layer (surface-role/obligation engine + producer-rejection ledger +
impact gate) wrapped in *opinionated orchestration* over the commodity tools,
not a reimplementation of SonarQube-plus-everything. This sharpens the report's
recommendation: the internal `celebrimbor` sub-package should own the novel
layer and shell out to adopted tools for the commodity pillars.

## What press proved is reusable

The load-bearing idea across every surviving area is one sentence: **make the quality bar a committed declarative artifact that a pure comparator gates, let it move only through an explicit reason-carrying `--update`, and prove every gate bites with a named negative fixture.** That idea is app-agnostic; most of the code implementing it for press is not, and that is the correct division of labor. The specific disciplines press proved out, each with its origin file:

- **Mechanical, un-rottable inventory.** `surfaces.public_callables()` (`src/press/surfaces.py`) walks `src/press/*.py` with `ast.parse` — it classifies source without importing it, so the completeness guarantee can never silently fall behind the code.
- **Role-with-proof-obligation taxonomy.** The eight roles (`pure`/`parser`/`normalizer`/`verifier`/`producer`/`orchestrator`/`adapter`/`presenter`) and what each *owes* live as data in `quality/surfaces.yaml`, not hardcoded — a general theory of how any callable earns trust.
- **No-blind-verifier.** `check_producers_are_verified()` (`src/press/selftest.py`) forces every `producer`-classified module to name an on-the-record negative fixture that turns its verifier red, or sit in a shrinking visible-gap allowlist — you cannot inherit a verifier that inspects nothing.
- **Monotonic ratchets.** `scripts/coverage_ratchet.py` (per-module branch floor, shadow-PATH determinism, low-floor-needs-a-written-reason) and `scripts/mutation_ratchet.py` (AST mutation in a shadow symlink tree, survivor-*identity*-not-count as the invariant) — quality strength that can only rise.
- **Referential-integrity invariant ledger.** `src/press/invariants.py` validates `quality/invariants.yaml` so every enforcer resolves to a real module and every critical promise keeps a real negative proof, then renders `docs/INVARIANTS.md` and fails on drift.
- **Completeness meta-gates.** The ordered `CHECKS` list plus `test_every_check_is_orchestrated` (`tests/test_selftest_checks.py`) prove nothing escapes the runner; `check_ledger_completeness` (`selftest.py`) proves every critical invariant keeps a fast-tier proof.
- **Change-impact mapping.** `src/press/impact.py` maps a git diff → surface role → owning invariant → gap, reddening when a policy-role module changes with no invariant naming it.
- **Marker-grammar test discipline.** `tests/pytest_invariants.py` enforces that a marked test cites a real invariant with `layer`/`proof`, that every `xfail` cites a declared limitation, every environment `skip` names a declared capability, and an assertionless marked test is rejected.
- **Declarative fixtures & scenarios.** `quality/fixtures.yaml` + `src/press/fixture_provenance.py` (known-bad-must-be-rejected, with the *right* checker and expected diagnostic); `quality/scenarios.yaml` + `src/press/scenarios.py` (deterministic pairwise covering set with both-ways + high-risk gates).
- **Self-proving baseline differs.** `tests/visual_harness.py` / `tests/structure_harness.py` extract toolchain-stable geometry and diff it under a pure tolerance-scoped comparator whose `--update` demands a recorded reason and whose bite is proven by in-memory mutation.
- **No-drift, no-skip gate composition.** `scripts/verify.sh` (cheap-failure-first ladder), the one-body-two-callers pattern (`scripts/gauntlet-steps.sh` run by CI directly and via `docker run`), and the no-silent-skip guard keyed on the trusted-image promise (`src/press/verify_formats.py`).
- **Resumable release/contract machine.** `scripts/release.sh` (preflight-before-mutation, idempotent remote-checked steps, poll-gate-before-irreversible-float) and `.github/workflows/release-contract.yml` (a tag must pin its own internal refs and prove every trust layer green).

## Extraction map

| # / Area | Mechanism | Reusable core | Press-specific | Verdict |
|---|---|---|---|---|
| 1 · Surface role system | AST inventory + module-default/override/exemption classify + audit gate (`surfaces.py`, `surfaces.yaml`) | `public_callables`/`classify`/`audit`/`scaffold`; the role taxonomy as config; stale-ref + reason/review-date validation | The module→role rows; `doctor.main`/`selftest.main` exemptions; `SRC`/`CONFIG`/`UNCLASSIFIED_MODULES` constants; `yamlio` shim | **Core** |
| 2 · No-blind-verifier | Producer set from `surfaces.yaml` partitioned against proven/pending registries (`selftest.py`) | `check_producers_are_verified` structure + its four failure modes; the proven-set/pending-allowlist pattern | `PRODUCER_REJECTION_PROOFS` / `PRODUCERS_PENDING_REJECTION_PROOF` contents (naming press verifiers) | **Core (mechanism) + Adapter (data)** |
| 3 · Ratchets | Committed JSON baseline + pure `compare()` + reason-gated `--update` (`coverage_ratchet.py`, `mutation_ratchet.py`) | Per-module floor with shadow-PATH determinism + low-floor-reason meta-ratchet; AST mutation with shadow-tree + survivor-identity invariant | `HIDDEN_TOOLS`/`DESELECT`/`TARGETS` values; the four mutation-target modules; the baseline contents | **Core** |
| 4 · Selftest runner + invariant ledger | Ordered `CHECKS` run by CLI + pytest; ledger validator + renderer (`selftest.py`, `invariants.py`) | The registry + dual runner + "no check escapes" meta-test; schema/dup/enforcer-resolves/critical-needs-negative validator; completeness gate; pytest marker plugin | ~30 press `check_*` bodies; `TITLES`; the `press.` prefix, `check_`/`fixture:` proof grammar, `KNOWN_BAD` dir, branded `render()` prose; `_CAPABILITIES`/`_LAYERS` vocab | **Core (both engines) — runner needs inversion; ledger needs a proof-resolver seam** |
| 5 · Impact / surface-gap gate | git-diff → role → invariant → gap (`impact.py`) | `changed_modules`/`analyze`; the `POLICY_ROLES` "policy roles owe a proof" rule (framework-level) | Hardcoded `"src/press/"` prefix + `__init__`/`__main__` exclusions; `adapters.process_runner` shim | **Core** (parameterize path prefix, inject the two ledgers) |
| 6 · Declarative fixtures/scenarios/harnesses | Provenance auditor; pairwise generator; extract→pure-diff→reason-gated-update differ (`fixture_provenance.py`, `scenarios.py`, `visual_harness.py`, `structure_harness.py`) | The auditor (orphans both ways + inline-`expect` anti-drift); the deterministic pairwise + both-ways + high-risk gates; the baseline-differ skeleton with self-proving negative fixtures | The fixtures/`fixtures.yaml` entries (editorial rules); the scenario dimensions; the feature extractors (`extract_pdf`/`extract_editions`); `design_major: v1` scoping | **Core (auditor + generator + skeleton) / Adapter (extractors)** |
| 7 · Composed gate + no-silent-skip | Layered `verify.sh` ladder; one-body-two-callers; env-promise strictness (`verify.sh`, `gauntlet-steps.sh`, `verify_formats.py`) | The no-silent-skip guard helper (~10 lines: promise-set-and-tool-absent ⇒ hard-fail, else warn); the composition *pattern* | The `verify.sh` step list; the entire gauntlet body (`press new`/`press all`/tamper); `PRESS_TOOLCHAIN` literal; epubcheck as gated tool | **Leave (template) + one small Core helper (`skip_guard`)** |
| 8 · Release / contract state machine | Resumable, remote-checked release; immutable-tag contract (`release.sh`, `release-contract.yml`, `lock-deps.sh`) | The documentable *structure*: preflight-before-mutation, idempotent steps, poll-gate-before-float, strict-SemVer `--check-tag`; `pip-compile --generate-hashes` shape | `clintecker/press@vN` action-ref rewriting; floated-major convention; `consumer`/`contract` check names; toolchain image identity + digest; CHANGELOG/pyproject/build.yml rewrites | **Leave (template)** — code welded to press's GitHub-Actions distribution topology |

**Net:** Core = 1, 3, 5, the mechanisms of 2/4/6, the scenario generator. Adapter = the data/extractors of 2, 4, 6. Leave = 7 (bar the skip-guard helper) and 8.

## Celebrimbor package shape

```text
celebrimbor/
  surfaces.py        # public_callables/classify/audit/scaffold — Area 1, near-verbatim
                     #   params: src_dir, config_path, unclassified_modules, yaml_loader
  ledger.py          # invariants.py validator + renderer — Area 4
                     #   params: package_name, proof_resolver, fixture_dir,
                     #           doc_header template, title_required
  runner.py          # the INVERTED check-runner — Area 4
                     #   CheckRegistry.register / run_all / pytest_params
                     #   + "no check_* escapes the registry" meta-test helper
                     #   + the repo-root wheel-skip idiom as a decorator
  producers.py       # check_producers_are_verified mechanism — Area 2
                     #   params: surfaces config, proven_registry, pending_registry
  impact.py          # git-diff → role → invariant → gap — Area 5
                     #   params: path_prefix, policy_roles, process_runner
  ratchet/
    coverage.py      # per-module floor + low-floor-needs-reason — Area 3
    mutation.py      # AST mutation, shadow tree, survivor-identity — Area 3
    baseline.py      # extract → pure-diff → reason-gated-update skeleton — Area 6
  fixtures.py        # provenance auditor — Area 6 (params: schema, expect_regex, dirs)
  scenarios.py       # deterministic pairwise + both-ways + high-risk gate — Area 6
  pytest_plugin.py   # marker grammar + index emission — Area 4
                     #   params: capabilities, layers, polarities sets
  skip_guard.py      # no-silent-skip helper — Area 7 (the one bit worth code)
  templates/         # cookiecutter: verify.sh, gate-steps.sh, .pre-commit-config.yaml,
                     #   release.sh skeleton, release-contract.yml — Areas 7 & 8 (docs, not imports)
```

**The declarative config an app writes** (same filenames as press, different contents):

- `quality/surfaces.yaml` — the `roles:` block (adopt the eight or prune) plus a `modules:` map. `--write` scaffolds module rows as `unclassified`; the gate forces a real role on each.
- `quality/invariants.yaml` — the app's promises, same schema.
- `quality/fixtures.yaml` — provenance ledger for its known-bad files (each carrying an inline `expect` comment).
- `quality/scenarios.yaml` — its optional-feature dimensions and high-risk interactions.
- `quality/coverage-baseline.json`, `quality/mutation-baseline.json` — produced by `--update` behind a recorded reason.

**The plugin points (the real API design — the seams where an app injects its facts):**

1. **`CheckRegistry.register`** — the app's `check_*` callables enter the one ordered list, replacing press's module-level `CHECKS`. The "no `check_*` escapes the registry" meta-test runs against the app's module.
2. **`proof_resolver: Callable[[str], str|None]`** — the single most important seam. Press's grammar (`check_`/`fixture:`/`integration`/`none`) becomes the *default* resolver; an app that proves invariants differently supplies its own. This unbinds `ledger.py` from press's selftest + fixture layout.
3. **`surfaces.yaml roles:`** — the taxonomy is data; `POLICY_ROLES` for the impact gate derives from which roles the app marks policy-bearing.
4. **`FeatureExtractor` protocol** — `extract(artifact) -> dict` plus `compare(a, b, tolerances) -> drift`. The skeleton, reason-gated update guard, and negative-proof discipline are inherited; only *which features are stable* is app knowledge.
5. **Ratchet config object** — `HIDDEN_TOOLS`, `DESELECT`, `TARGETS`, `src_dir` as config, not module constants.
6. **pytest vocab** — `capabilities`, `layers`, `polarities` sets passed to the plugin instead of inline constants.

## Adoption path

`pip install celebrimbor && celebrimbor init` drops the `quality/*.yaml` skeletons and the templates.

**Day one you get scaffolding and an honest refusal to lie — not passing gates:**

- The AST surface auditor scaffolds `surfaces.yaml` with every module `unclassified`; the gate is **red** until a human assigns roles. That is the feature — mechanical maintenance, human decision.
- The ratchet engines run against empty baselines (everything reads as a new module).
- The pytest plugin enforces the marker grammar the moment a marked test appears.
- The ledger validator demands an `invariants.yaml` and refuses a critical invariant with no negative proof.

**The wiring steps (the real cost, borne once):**

1. Classify every module's role — the only large hand-authored input; `--write` scaffolds the module list mechanically.
2. Write `invariants.yaml` promises plus a `proof_resolver`, or adopt the default grammar and write `check_*` functions.
3. Register the checks; `--update` the ratchet baselines behind a recorded reason.
4. Write known-bad fixtures with inline `expect` comments; wire a feature extractor per artifact type for the baseline harness.
5. Template `verify.sh` / `gate-steps.sh` / `.pre-commit-config.yaml` from `celebrimbor/templates/` and fill in the app's build/exercise commands; wire the `skip_guard` to the app's trusted-environment promise.

Then the app inherits the whole discipline: no-blind-verifier, monotonic floors, impact-gap detection, completeness (critical ⇒ fast-tier proof), and no-silent-skip.

**How press dogfoods it back.** Press keeps all its domain content and imports all the engine:

- `selftest.py` collapses from ~1781 lines to ~30 `check_*` bodies plus a `registry.register(...)` block; `main()` and the pytest parametrization come from `celebrimbor.runner`.
- `surfaces.py`, `impact.py`, `invariants.py`, `fixture_provenance.py`, `scenarios.py`, `pytest_invariants.py` shrink to thin config + injection (press passes `package_name="press"`, its proof-resolver, its `POLICY_ROLES`, its `HIDDEN_TOOLS`/`TARGETS`).
- `quality/*.yaml` are untouched — they were always press's data. `PRODUCER_REJECTION_PROOFS`, the 34 checks, the ISBN/EAN/coverwrap/authorities verifiers, the PDF/EPUB/DOCX extractors, and `_CAPABILITIES` all stay press-side. The release machine stays in press; Celebrimbor only offers it as a template.

This is a genuine dogfood: if the extraction is clean, press's own gates keep passing byte-for-byte, and that green run *is* the proof the seam is right — matching press's own law that "a green pip install is not a working pipeline; prove against a real consumer."

## Effort, risk, and recommendation

**Sizing (internal seam-hardening, no second repo yet):**

| Piece | Effort | Note |
|---|---|---|
| surfaces | ~1 day | already clean; parameterize 3 constants |
| ratchets | ~1–2 days | config-object the four knobs each |
| impact | ~1 day | parameterize path prefix, inject ledgers |
| ledger validator | ~2–3 days | inject package name, proof-resolver, doc template |
| **runner inversion** | ~3–5 days | **the hard one:** module-level `CHECKS` → registry API, keeping dual CLI/pytest execution and the meta-test working |
| fixture provenance | ~2 days | parameterize schema vocab + expect regex |
| pytest plugin | ~2 days | parameterize the vocab sets |
| baseline-differ skeleton | ~1 day | mostly pattern + two pure helpers |
| **Total internal** | **~2–3 weeks** | focused |
| Second-repo (CI, packaging, release, docs, dogfood loop) | ~1 week setup + perpetual tax | only if N ≥ 2 |

**Coupling risks that make it hard:**

- **The selftest monolith** (~1781 lines mixing the generic runner with 30+ press bodies) is the single blocker. Everything else is parameterization; this one needs inversion of control.
- **The import cluster** `impact → invariants → surfaces → selftest` is tight. That cohesion is *good* — it is genuinely one engine — but it means the engine extracts all-or-nothing: you cannot cheaply take surfaces and leave the rest, because the producer gate and impact both reach into `surfaces.yaml`.
- **House shims** `yamlio` and `adapters.process_runner` must be vendored or replaced with stdlib (`json`/`subprocess` + any YAML loader). Minor but pervasive.
- **Design-contract leakage.** `design_major` scoping and "a fix must not change layout" semantics bleed into the baseline harnesses; that is press-domain and must not follow the differ into Celebrimbor.

**The second-repo cost is the real reason to wait.** Version skew between celebrimbor and press; a second release cadence; a mandatory dogfood loop (every celebrimbor change proven against press before press upgrades — press's own law); duplicated CI and docs. For N = 1 this is pure overhead with no offsetting reuse. It also risks *diluting* the discipline: the gates are sharp today precisely because they were forged against one demanding consumer, and genericizing prematurely tends to soften the exact hardcoded assumptions (the `PRESS_TOOLCHAIN` keying, the `check_` grammar) that make them bite.

**Recommendation: extract a subset now as an internal boundary; defer the second repo.**

1. **Do now (worth it regardless):** create `src/celebrimbor/` inside the press repo containing areas 1, 3, 5, the mechanisms of 2/4/6, and the scenario generator — with **zero `press.` imports** and its **own test suite**. ~2–3 weeks. It is a strict improvement even if no second app ever appears: it forces the runner inversion (retiring the monolith), makes the seams explicit, and gives press a legible internal architecture. The proof it is done right is press's gates staying green through the refactor.
2. **Do now (cheap, high-value):** extract the `skip_guard` no-silent-skip helper — ~10 lines, used in several places, easy to get subtly wrong.
3. **Template, don't extract:** ship areas 7 and 8 as `celebrimbor/templates/` cookiecutter files plus one docs page on the patterns (one-script-two-callers, preflight-before-mutation, poll-gate-before-float). Their code is welded to GitHub Actions and press's floated-tag distribution; a library abstraction over "how you release" would be leaky and low-payoff.
4. **Do not do yet:** mint `celebrimbor` as a separate published package/repo. Wait for a real second consumer. When one appears, the internal boundary means the split is a `git filter-repo` + a `pyproject`, not a rewrite — you will have already paid the hard cost (decoupling) and deferred only the cheap-but-perpetual cost (a second repo's maintenance) until it is justified.

**Why not "extract now" fully:** the honest reuse population is one; splitting repos at N = 1 optimizes for a future that may not arrive and taxes the present with certainty. **Why not "wait entirely":** the runner inversion and seam-cleaning are worth doing inside press today on their own merits.

## Non-goals

Celebrimbor is deliberately *not*:

- **Not a test-runner replacement.** It composes pytest, coverage, and pre-commit; it does not reimplement them. The pytest plugin adds a marker grammar and an index; the ratchets read pytest/coverage output. Celebrimbor gates the *strength and completeness* of a test suite — it never executes tests in place of the runner.
- **Not app logic, and not a book pipeline.** It ships no ISBN/EAN arithmetic, no coverwrap detectors, no PDF/EPUB/DOCX extractors, no editorial checkers. Every domain checker, verifier, and feature extractor stays in the consuming app. Books consume press; press (and other tools) consume Celebrimbor — Celebrimbor never grows book-domain knowledge.
- **Not the release/distribution mechanism.** `release.sh` and `release-contract.yml` port as templates and a documented pattern, not as library code. Celebrimbor does not know how any given app ships (composite action vs. plain wheel vs. container), does not own tag conventions, and does not name trust-layer checks — the app supplies its own distribution topology.
- **Not a coverage/quality *number*.** It never asserts a repo-wide percentage or a fixed kill count. It gates *regression and completeness*: floors only rise, survivor identity is the invariant, every critical promise keeps a real negative proof. The bar is a committed artifact that moves only through an explicit reason-carrying `--update`.
- **Not a passing-gate generator.** Day one it is honestly red (every module `unclassified`, empty baselines). It refuses to manufacture false green; making the gates pass is the app's wiring work, by design.
- **Not a config auto-populator.** The AST scaffold maintains the *module list* mechanically, but every role assignment, invariant, proof, fixture, and baseline reason is a human decision the gate forces — mechanical maintenance, human judgment.
