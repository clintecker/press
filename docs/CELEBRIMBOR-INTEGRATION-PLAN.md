# Celebrimbor integration: retire press's parallel quality machinery

The finishing plan for leaning *entirely* on celebrimbor. Executed in staged,
gate-verified steps; **nothing destructive happens until celebrimbor is the
wired, enforced gate and parity is proven.** Every step before the deletion is
additive and reversible.

## Where we are (the honest baseline)

`celebrimbor gate` runs **green on press** (every surface/structure/producer/
invariant/marker/lint/format/type gate) — but as an **external shadow tool**
(`cb-venv4 --root press`), not press's enforced gate:

- Not in `.pre-commit-config.yaml`; press's commits are gated by press's own
  ruff/mypy/**selftest**/pytest.
- Not a press dependency.
- press's 6 infra modules (`surfaces.py`, `impact.py`, `invariants.py`,
  `fixture_provenance.py`, `scripts/coverage_ratchet.py`,
  `scripts/mutation_ratchet.py`) are present and enforced.
- press's ~30 **domain** checks still live in `selftest.py`'s `CHECKS` list.

So press runs **both systems in parallel**. The job is to make celebrimbor the
sole gate, then delete the redundant half.

## The architectural decision: how press's domain checks reach celebrimbor

The `celebrimbor` CLI loads only its own builtin checks (`load_builtin_checks()`);
there is no config to load an app's `@check` registrations. Two options:

- **A. Programmatic (works today):** a thin `press gate` entry that
  `import`s the module holding press's `@celebrimbor.check` registrations
  (registering them by import side-effect), then calls `celebrimbor.gate(...)`
  and exits on its verdict. press's pre-commit/CI run `press gate`.
- **B. `check_modules` config (needs a celebrimbor update):** celebrimbor grows
  `[tool.celebrimbor] check_modules = ["press.quality_checks"]`, and the CLI
  imports them before running, so `celebrimbor gate` alone runs everything.

**Decision: build A now** (no external dependency, fully in press's control),
and **file B as a celebrimbor nicety** so the CLI hook is available later. A also
keeps press's own three-tier mapping to pre-commit/PR/CI explicit.

## The check inventory (from selftest.py `CHECKS`)

- **INFRA — DELETE** (celebrimbor replaces 1:1): `check_producers_are_verified`,
  `check_invariant_ledger`, `check_ledger_completeness`, `check_registry`,
  `check_the_checkers`, `check_fixture_provenance`, `check_imports`,
  `check_import_side_effects` (→ celebrimbor's `producers`, `invariants`,
  completeness/`registry`, `falsifiers`, `known_bad`, `imports`).
- **DOMAIN — REGISTER via `@check`** (~30, the actual product verification):
  `check_aesthetic_schema`, `check_arithmetic`, `check_authorities_ledger`,
  `check_book_model`, `check_command_catalog`, `check_commerce_config`,
  `check_commerce_release_gate`, `check_contract_mirror`,
  `check_coverwrap_detectors`, `check_docs`, `check_edition_manifest`,
  `check_editions_agree`, `check_editorial_checkers`,
  `check_extension_conformance`, `check_format_witnesses`, `check_front_panel`,
  `check_honest_refusals`, `check_jargon_default_watchlist_agrees`,
  `check_jargon_parity`, `check_migration`, `check_pages_verifier`,
  `check_profile_seals`, `check_provider_contract`,
  `check_provider_qualification`, `check_receipt_chain`, `check_release_grammar`,
  `check_scaffold_neutrality`, `check_site_identity`, `check_slug_invariant`,
  `check_source_policy`.

## Phase 1 — register the domain checks via `@check` (ADDITIVE)

Add `src/press/quality_checks.py`: for each domain `check_*`, a thin adapter

```python
@celebrimbor.check(id="press.editorial.jargon", title="…",
                   falsified_by="tests/known-bad/jargon.md",   # the fixture that reddens it
                   stage="fast|default|full")                   # match its current tier
def _jargon(ctx):
    try:
        selftest.check_editorial_jargon()          # press's existing body, unchanged
        return CheckResult.passed(...)
    except SystemExit as exc:
        return CheckResult.failed(..., [Finding(str(exc))])
```

- Each `falsified_by` names the known-bad fixture or negative test that already
  reddens that check (press has these; map them). Where none exists yet, use
  `Unproven(review_by=…)` and burn it down.
- The check *bodies* stay in their current modules (`verify_pdf`, `jargon_lint`,
  `style_audit`, `gen_authorities`, `verify_coverwrap`, …); only the
  *registration* is new. Nothing is deleted here.
- Prove it: `press gate` (Phase 2) runs the builtin + these 30 and is green.

## Phase 2 — wire celebrimbor as the enforced gate (ADDITIVE, both run)

1. Add celebrimbor to press's dev dependencies (pinned wheel/lock).
2. Add a `press gate [--fast|--full]` command (option A): import `quality_checks`,
   call `celebrimbor.gate()`, exit on the verdict.
3. Move the ledgers from `.celebrimbor/` to `quality/` (the committed home;
   update `celebrimbor.toml` paths) so they sit beside press's data — after
   press's own `quality/surfaces.yaml` etc. are retired in Phase 4 there is no
   collision, but during Phases 2–3 keep celebrimbor's in `.celebrimbor/`.
4. Add `press gate --fast` as a **second** pre-commit hook (press's own gate
   still runs too). CI runs `press gate` at the PR stage and `--full` at merge,
   **alongside** the existing gauntlet.
5. Enable `import_check = true` and generate the known-bad `expected.yaml`
   (unblocked once the domain checkers are registered).

## Phase 3 — prove parity (the go/no-go gate for deletion)

For every press infra + domain check, prove celebrimbor's equivalent catches the
same failure: run each known-bad fixture and each negative test and confirm the
celebrimbor gate reddens where press's did. A short `tests/test_parity.py` that
asserts, per check, "press caught it ⇒ celebrimbor catches it." **Deletion does
not start until this is green.**

## Phase 4 — delete the redundant infrastructure (DESTRUCTIVE, staged)

One module per commit, each with the full gate proving still-green after:

1. `scripts/coverage_ratchet.py`, `scripts/mutation_ratchet.py` → celebrimbor
   `ratchets`.
2. `impact.py` → celebrimbor `impact`. `invariants.py` (validator/renderer) →
   celebrimbor `invariants`. `fixture_provenance.py` → celebrimbor `known_bad`.
3. `surfaces.py` + `quality/surfaces.yaml` (press's own) → celebrimbor
   `surface.*`; move celebrimbor's ledgers into `quality/`.
4. `selftest.py`: delete the RUNNER (the `CHECKS` list, `render_reference`, the
   dual CLI/pytest orchestration) and the 6 infra check bodies; keep nothing —
   the domain checks now live behind `@check` in their own modules.
5. Delete the corresponding tests that only tested the deleted infra
   (`test_selftest_checks.py` runner parts, `test_surface_inventory.py`,
   `test_invariant_ledger.py`, `fixture_provenance` tests) — celebrimbor's own
   suite covers the engine.

## Phase 5 — repoint CI, remove the parallel gate (DESTRUCTIVE)

1. `.pre-commit-config.yaml`: drop press's ruff/mypy/selftest/pytest hooks in
   favor of `press gate --fast` (celebrimbor runs lint/types/format/etc.).
2. CI (`.github/workflows/*`, `scripts/gauntlet*.sh`, `scripts/verify.sh`):
   replace the quality steps with `press gate` / `--full`. Keep the
   book-render/toolchain steps (those run the domain checks' heavy paths).
3. The release contract + `release.sh` stay (deploy automation, out of scope).

## Non-negotiables

- **No deletion before Phase 3 parity is green.** Deleting a check whose
  celebrimbor equivalent is unproven silently drops product verification.
- Each Phase-4/5 removal is its own commit with the gate green after it, so any
  regression is one `git revert` away.
- The domain-check *bodies* are product code and are never deleted — only their
  press-runner registration moves to `@check`.

## Open dependency

Option B (`check_modules` CLI loading) is filed as a celebrimbor issue; if it
lands, Phase 2's `press gate` can collapse to a plain `celebrimbor gate` hook.
Not a blocker — A ships without it.
