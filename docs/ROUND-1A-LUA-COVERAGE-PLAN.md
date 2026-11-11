# Round 1A: v3.0.1 and Lua coverage (M3) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship v3.0.1 with the one wrong sentence `press migrate` tells every v3 author corrected, then make the Lua filters' test coverage measured, floored, and actually run in CI, so the edition-parity rewrite of those filters (Round 1B, v4) has a safety net under it.

**Architecture:** Two independent pieces, both within-major. (1) `migrate.plan` picks its design note from a table keyed by the target major instead of one hard-coded sentence. (2) A line-hook coverage harness for pandoc's embedded Lua: when a coverage directory is set in the environment, every filter test loads a generated shim that installs `debug.sethook` line tracing, `dofile`s the real filter, and dumps per-file line hits when the document finishes; a Python ratchet merges the hits, computes per-file coverage against an eligible-line count, and refuses any drop below a committed floor. No luacov, no luarocks: pandoc's own interpreter is the only Lua the project needs. CI's quality job gains pandoc *before* pytest, with a flag that turns the Lua tests' silent skip into a failure, because today no Lua filter test runs anywhere in CI.

**Tech Stack:** Python 3.10+, pytest, pandoc's Lua 5.4 (`pandoc lua`, `--lua-filter`), celebrimbor gate (unchanged), GitHub Actions.

**Spec:** `docs/LUA-QUALITY-PLAN.md` §5 (coverage + ratchet), §6 (close the gaps), §7 (no silent skip); issue #262; `CLAUDE.md` § The contract; memory `press-release-gates`.

## Findings this plan rests on (verified 2026-11-10)

- `migrate.py:182-186` builds the plan's first note as a fixed sentence claiming byte-for-byte parity for any `from_major → to_major`. True for 1→2, false for 2→3. Seen on Make Ready's real migration (#262).
- Every Lua filter test (`test_figure_numbering_filter.py`, `test_figure_placement.py`, `test_set_pieces.py`, `test_scene_break.py`, `test_dropcaps_filter.py`, `test_typographic_spacing.py`, `test_print_safe_images_filter.py`, `test_press_util_lua.py`, `test_lua_compiles.py`) is `skipif(no pandoc and not PRESS_TOOLCHAIN)`. The CI quality job installs pandoc only *after* pytest and the gate (`selftest.yml:57-61`), the matrix jobs never install it, and the container gauntlet runs no pytest. So the Lua suite has only ever run on developer machines.
- Each filter test owns a private `_render()` that passes `f"--lua-filter={FILTER}"` to a `subprocess.run(["pandoc", ...])`; there is no shared helper. All seven filters use pandoc's global-function style (`function Pandoc(doc)`, `function Image(el)`, `function Div(el)`, `function Inlines(x)`); only `press-util.lua` returns a module table.
- The Python coverage floors live in `.celebrimbor/baselines/coverage.yaml` (`version: 1`, `environment: ci`, `floors: {module: pct}`) and are measured in CI; the release-gates memory forbids re-baselining from macOS because numbers differ. The Lua ratchet follows the same shape and the same law.
- `scripts/verify.sh` runs pytest with `--cov` then `celebrimbor gate`, then the site build; `--full` adds the gauntlet. The Lua ratchet slots in beside the gate.

## Global Constraints

- Within-major: no rendered output of any book changes. The harness is test-only; the filters themselves are not edited except where §6 backfill adds a test, never code.
- Release law: v3.0.1 is cut with `scripts/release.sh v3.0.1` after the four local gates and a green main; the changelog carries a `## [3.0.1]` section first.
- Docs law: every surface change and its documentation land in the same commit (`docs/LUA-QUALITY-PLAN.md`, `CONTRIBUTING.md`, `docs/MIGRATION.md` where touched).
- Never re-baseline a ratchet from a macOS measurement; floors are CI's numbers. The Lua baseline is first committed from a CI run's reported values.
- Pre-commit (ruff with complexity gate, mypy, PyMarkdown, yamllint, stylua, selene, Lua syntax gate) passes; no `--no-verify`.
- A pytest skip must cite a declared capability (`tests/pytest_invariants.py` enforces it); the new harness introduces no new skip reason.
- Commit trailers: `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01SPXDHxTzC8B5pWcw7UqBEr`.

## Review Focus

1. **A pandoc run that errors before `Pandoc` fires** (bad markdown, a filter raising) would never dump its hits; the harness must not turn such a test's failure into a silent coverage hole or a crash of the ratchet. Pinned in Task 3's test that a shim run whose filter raises leaves no partial hits file and the ratchet still reads the others.
2. **Two pandoc runs writing the same hits file.** Tests run under xdist. Pinned in Task 3 by unique per-run filenames and a merge test over several files.
3. **Eligible-line counting that counts comments or `end` as misses**, making the floor unreachable or noisy. Pinned in Task 4's eligible-line unit tests.
4. **The ratchet going green because no hits were collected at all** (the env var unset, the shim not used). Pinned in Task 4: zero hits for a filter that has tests is a failure, not 0%.
5. **The no-silent-skip flag making developer machines without pandoc fail.** Pinned in Task 5: the flag is set only in CI; locally the skip stays a skip and the ratchet step is skipped with a message.

---

### Task 1: Register the plan

**Files:**
- Create: `docs/ROUND-1A-LUA-COVERAGE-PLAN.md` (this file)
- Modify: `scripts/build_site.py` (`NOT_PUBLISHED`)

- [x] **Step 1:** add `"docs/ROUND-1A-LUA-COVERAGE-PLAN.md": "internal round plan for v3.0.1 and the Lua coverage ratchet; lives in the repo and issues, not the docs site"` to `NOT_PUBLISHED`. (Done at planning time, uncommitted.)
- [ ] **Step 2:** `python3 scripts/build_site.py` exits 0.
- [ ] **Step 3:** commit: `Record the round-1A plan: v3.0.1 and the Lua coverage ratchet`.

---

### Task 2: #262 — the migration note names what the target major changes, then release v3.0.1

**Files:**
- Modify: `src/press/migrate.py:182-186`
- Modify: `tests/test_migrate.py`
- Modify: `CHANGELOG.md`, `docs/MIGRATION.md` (one sentence under "The four moves" that the plan's first note is specific to the target major)

**Interfaces:**
- Produces: `migrate.DESIGN_NOTES: dict[int, str]` keyed by target major, and `migrate.design_note(from_major: int, to_major: int) -> str`. Known majors: `2` → the existing byte-for-byte sentence (with `v{to}`/`v{from}` interpolated); `3` → `"design changes: v3 is a design major (a fine-press typography pass and numbered figures move glyph positions and line breaks in every book), so after apply, rebuild and look at the pages; docs/MIGRATION.md 'What v2 → v3 actually changes' lists what moved."`. Unknown major → `"design: see docs/MIGRATION.md for what v{to} changes relative to v{from}; nothing here is rewritten but the pin."`.

- [ ] **Step 1: Write the failing tests** in `tests/test_migrate.py`:

```python
REQ_V2 = "press @ git+https://github.com/clintecker/press@v2\n"
WF_V2 = "    uses: clintecker/press/.github/workflows/build.yml@v2\n"

@pytest.mark.layer("unit")
def test_v2_to_v3_plan_does_not_claim_byte_for_byte_parity(tmp_path):
    plan = migrate.plan(_book(tmp_path, REQ_V2, WF_V2), 3)
    joined = " ".join(plan.notes)
    assert "byte-for-byte" not in joined
    assert "design major" in joined and "MIGRATION.md" in joined

@pytest.mark.layer("unit")
def test_v1_to_v2_plan_still_states_geometry_parity(tmp_path):
    plan = migrate.plan(_book(tmp_path, REQ_V1, WF_V1), 2)
    assert any("byte-for-byte" in n for n in plan.notes)

@pytest.mark.layer("unit")
def test_unknown_major_gets_the_neutral_note():
    note = migrate.design_note(3, 9)
    assert "byte-for-byte" not in note and "MIGRATION.md" in note and "v9" in note
```

- [ ] **Step 2:** run `python3 -m pytest tests/test_migrate.py -p no:cacheprovider`; expected: the first and third FAIL (`AttributeError: design_note` / byte-for-byte present).
- [ ] **Step 3:** implement `DESIGN_NOTES` and `design_note()`; `plan()` uses `design_note(from_major, to_major)` as its first note. No other behaviour changes.
- [ ] **Step 4:** tests pass; also `python3 -m pytest tests/test_scaffold_pin.py tests/test_selftest_checks.py -k migration -p no:cacheprovider` passes (the scaffolded-book migration proof).
- [ ] **Step 5:** CHANGELOG: new `## [3.0.1] - <date>` section above `[3.0.0]` (keep an empty `## [Unreleased]` on top) with one `### Fixed` bullet; `docs/MIGRATION.md` sentence.
- [ ] **Step 6:** commit: `press migrate states what the target major changes instead of promising byte-for-byte parity for every major (#262)`; push main; wait for `Press selftest` and `Press integration gate` green.
- [ ] **Step 7:** local gates: `scripts/verify.sh`, the installed-wheel desk run (install `pytest-xdist` into that venv too, the suite's addopts need it), `git status --porcelain` empty (park untracked files outside the tree if needed, restore after).
- [ ] **Step 8:** `scripts/release.sh v3.0.1`; confirm `gh release view v3.0.1` and that `refs/tags/v3` moved to it. Close #262 with the release link.

---

### Task 3: The Lua line-hook coverage harness

**Files:**
- Create: `tests/lua_coverage.py` (shim generation + hits merge; importable from tests)
- Create: `tests/lua/coverage-hook.lua` (the hook, read by the shim generator and inlined)
- Modify: the seven filter tests' `_render()` to call the helper for the filter argument
- Create: `tests/test_lua_coverage_harness.py`

**Interfaces:**
- Produces: `lua_coverage.filter_arg(filter_path: Path) -> str`: returns `f"--lua-filter={filter_path}"` when `PRESS_LUA_COV_DIR` is unset; otherwise writes (once per process) `<dir>/shim-<filter-stem>.lua` and returns `--lua-filter=<shim>`.
- Produces: `lua_coverage.merge(cov_dir: Path) -> dict[str, set[int]]`: merges every `hits-*.tsv` in the directory into `{filter filename: {line numbers hit}}`.
- The shim's contract: it sets a line hook that records `(short_src, line)` only for sources under the filters directory; `dofile`s the real filter; wraps or defines the global `Pandoc` so that, after the real `Pandoc` (if any) returns, hits are appended to `<dir>/hits-<os.tmpname basename>-<os.time>.tsv` as `file\tline` rows; the hook is cleared before the write. If the real filter raises, no file is written (pandoc exits non-zero and the test fails as before).
- Hits-file writes use a fresh unique name per pandoc run so concurrent xdist workers never share one.

- [ ] **Step 1: Write the failing harness tests**

```python
# tests/test_lua_coverage_harness.py  (all tests marked layer("unit") and _needs_pandoc as in test_lua_compiles.py)
def test_filter_arg_is_passthrough_without_env(monkeypatch, tmp_path):
    monkeypatch.delenv("PRESS_LUA_COV_DIR", raising=False)
    assert lua_coverage.filter_arg(Path("/x/f.lua")) == "--lua-filter=/x/f.lua"

def test_shim_records_hits_for_a_real_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESS_LUA_COV_DIR", str(tmp_path))
    arg = lua_coverage.filter_arg(LUA_DIR / "scene-break.lua")
    subprocess.run(["pandoc", "-f", "markdown", "-t", "html", arg], input="a\n\n* * *\n\nb\n", check=True, capture_output=True, text=True)
    hits = lua_coverage.merge(tmp_path)
    assert "scene-break.lua" in hits and len(hits["scene-break.lua"]) > 5

def test_two_runs_write_two_files_and_merge(tmp_path, monkeypatch):
    ...  # run the same pandoc twice; assert 2 hits files; merged lines are the union

def test_a_raising_filter_leaves_no_hits_file(tmp_path, monkeypatch):
    bad = tmp_path / "bad.lua"; bad.write_text("function Pandoc(doc) error('boom') end\n")
    ...  # shim for `bad`; pandoc exits non-zero; no hits-*.tsv exists

def test_hits_only_name_filters_under_the_lua_dir(tmp_path, monkeypatch):
    ...  # merged keys are bare filenames of files in LUA_DIR, nothing from the shim itself
```

- [ ] **Step 2:** run; expected: ImportError / FAIL.
- [ ] **Step 3:** implement `tests/lua/coverage-hook.lua` and `tests/lua_coverage.py`. Hook body (the one algorithm the signatures do not determine):

```lua
-- coverage-hook.lua: generated shim prepends the three config lines
-- local PRESS_LUA_DIR, PRESS_REAL_FILTER, PRESS_COV_DIR = ...
local hits = {}
debug.sethook(function(_, line)
  local src = debug.getinfo(2, "S").short_src
  if src:sub(1, #PRESS_LUA_DIR) == PRESS_LUA_DIR then
    local f = hits[src]; if not f then f = {}; hits[src] = f end
    f[line] = true
  end
end, "l")
dofile(PRESS_REAL_FILTER)
local real_pandoc = Pandoc
function Pandoc(doc)
  local out = doc
  if real_pandoc then out = real_pandoc(doc) or doc end
  debug.sethook()
  local name = PRESS_COV_DIR .. "/hits-" .. os.tmpname():match("[^/]+$") .. "-" .. os.time() .. ".tsv"
  local fh = assert(io.open(name, "w"))
  for src, lines in pairs(hits) do
    local base = src:match("[^/]+$")
    for ln in pairs(lines) do fh:write(base, "\t", ln, "\n") end
  end
  fh:close()
  return out
end
```

  `short_src` truncates long paths with `...`; the shim passes an absolute `PRESS_LUA_DIR` and the Python side writes it verbatim, so compare with `debug.getinfo(2, "S").source` (`@/abs/path`) instead when `short_src` starts with `...`. Pin this with a test whose tmp dir path is long.

- [ ] **Step 4:** switch the seven filter tests' `_render()` from `f"--lua-filter={FILTER}"` to `lua_coverage.filter_arg(FILTER)`; nothing else in them changes. Run the full Lua suite twice: once without the env (byte-identical outputs, all pass) and once with `PRESS_LUA_COV_DIR=<tmp>` (all pass, hits files appear for all seven filters).
- [ ] **Step 5:** commit: `A line-hook coverage harness for the Lua filters, switched on by PRESS_LUA_COV_DIR`.

---

### Task 4: The ratchet and its baseline

**Files:**
- Create: `scripts/lua_coverage_ratchet.py`
- Create: `.celebrimbor/baselines/lua-coverage.yaml`
- Create: `tests/test_lua_coverage_ratchet.py`
- Modify: `scripts/verify.sh`, `CONTRIBUTING.md`, `docs/LUA-QUALITY-PLAN.md` (§5: the mechanism is a line hook, not luacov; M3 status)

**Interfaces:**
- Produces: `lua_coverage_ratchet.eligible_lines(source: str) -> set[int]`: 1-based lines that are not blank, not comment-only (`--`), and not a lone closer (`end`, `else`, `}`, `)`, `end)`, `end,`), after stripping.
- `lua_coverage_ratchet.report(cov_dir: Path, lua_dir: Path) -> dict[str, tuple[int, int]]`: per filter filename `(hit_eligible, eligible)`; a filter with zero hits and at least one eligible line is reported as `(0, n)`.
- CLI: `python3 scripts/lua_coverage_ratchet.py check --cov-dir DIR` (exit 1 on any file below its floor, or on any filter present in the baseline with zero hits, printing `file: got X% floor Y%`), `report --cov-dir DIR` (prints the table and the uncovered line numbers per file, for §6 backfill), `update --cov-dir DIR --reason "..."` (rewrites floors to the measured values, never lower, records the reason). Baseline shape mirrors `coverage.yaml`: `version: 1`, `environment: ci`, `tool: lua-line-hook`, `floors: {filename: pct}`, `reasons: [...]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_eligible_lines_skips_blank_comment_and_closers():
    src = "-- c\nlocal x = 1\n\nif x then\n  y()\nend\n"
    assert lua_coverage_ratchet.eligible_lines(src) == {2, 4, 5}

def test_report_counts_only_eligible_hits(tmp_path):
    (tmp_path / "f.lua").write_text("local a = 1\n-- c\nlocal b = 2\n")
    (tmp_path / "hits-1.tsv").write_text("f.lua\t1\nf.lua\t2\n")   # line 2 is a comment: not eligible
    assert lua_coverage_ratchet.report(tmp_path, tmp_path) == {"f.lua": (1, 2)}

def test_check_fails_below_floor_and_on_zero_hits(tmp_path, capsys):
    ...  # baseline {f.lua: 60.0, g.lua: 10.0}; hits give f 50%, g none -> exit 1, both named

def test_update_never_lowers_a_floor(tmp_path):
    ...  # measured 40 vs floor 60 -> floor stays 60; reason appended

def test_check_passes_at_or_above_floor(tmp_path): ...
```

- [ ] **Step 2:** run; FAIL (module missing).
- [ ] **Step 3:** implement the script (pure functions + argparse; read/write YAML with `press.yamlio`).
- [ ] **Step 4:** tests pass. Measure locally once: `PRESS_LUA_COV_DIR=$(mktemp -d) python3 -m pytest tests/test_*filter*.py tests/test_set_pieces.py tests/test_scene_break.py tests/test_typographic_spacing.py tests/test_figure_placement.py -p no:cacheprovider && python3 scripts/lua_coverage_ratchet.py report --cov-dir <dir>`; paste the table in the task report. Commit the baseline with **provisional floors 5 points below the local numbers** and `reasons: ["initial floors, provisional: set 5 points under a macOS measurement; replaced by CI's numbers in Task 5"]`.
- [ ] **Step 5:** `scripts/verify.sh`: after the gate, if `pandoc` is on PATH, run the Lua suite with `PRESS_LUA_COV_DIR` set to a temp dir and then `lua_coverage_ratchet.py check`; if pandoc is absent print `lua coverage: pandoc absent, skipped (CI enforces it)`. `CONTRIBUTING.md`: one paragraph beside the coverage-ratchet warning (never `update` from a macOS measurement). `docs/LUA-QUALITY-PLAN.md` §5: replace the luacov mechanism with the line-hook description and mark M3 shipped.
- [ ] **Step 6:** commit: `A Lua coverage ratchet: per-filter line floors that only rise, measured through the hook harness`.

---

### Task 5: Run the Lua suite in CI, loudly, and take the baseline from CI

**Files:**
- Modify: `.github/workflows/selftest.yml` (quality job)
- Modify: `tests/test_lua_compiles.py`, `tests/test_press_util_lua.py`, and the seven filter tests' `_needs_pandoc` markers (one shared marker in `tests/lua_coverage.py` replaces the copies)
- Modify: `.celebrimbor/baselines/lua-coverage.yaml` (CI numbers)

**Interfaces:**
- Produces: `lua_coverage.needs_pandoc`: `pytest.mark.skipif(shutil.which("pandoc") is None and not (PRESS_TOOLCHAIN or PRESS_REQUIRE_LUA), reason="requires capability: pandoc")`. With `PRESS_REQUIRE_LUA=1` and no pandoc, the tests run and fail on the missing binary instead of skipping.

- [ ] **Step 1:** replace the nine per-file markers with the shared one; a test in `tests/test_lua_coverage_harness.py` asserts that with `PRESS_REQUIRE_LUA=1` the marker's condition is `False` even when `shutil.which` returns `None` (monkeypatch both).
- [ ] **Step 2:** in the quality job, move the `apt-get install pandoc` lines to **before** the "Quality gate" step, set `PRESS_REQUIRE_LUA: "1"` and `PRESS_LUA_COV_DIR: ${{ runner.temp }}/lua-cov` on the gate step's `env`, and add a step after the gate: `python3 scripts/lua_coverage_ratchet.py report --cov-dir "$PRESS_LUA_COV_DIR" && python3 scripts/lua_coverage_ratchet.py check --cov-dir "$PRESS_LUA_COV_DIR"`. Leave the matrix jobs alone (they prove interpreters, not filters).
- [ ] **Step 3:** push; read the `report` table from the CI log; run `update --reason "floors set from CI run <id>"` locally **by pasting CI's numbers** (the script accepts `--from-report <file>` for exactly this; add that flag if not already present, with a test), commit, push, confirm `check` green in CI.
- [ ] **Step 4:** CHANGELOG `### Changed` bullet under `[Unreleased]`: the Lua filter tests now run in CI's quality job with pandoc present and a flag that forbids the silent skip; a per-filter coverage floor is enforced.
- [ ] **Step 5:** commit: `Run the Lua filter suite in CI with pandoc present and refuse the silent skip; floor Lua coverage from CI's numbers`.

---

### Task 6: §6 backfill against the report

**Files:**
- Modify: the filter tests (new cases only); never the filters
- Modify: `.celebrimbor/baselines/lua-coverage.yaml` (raise floors after backfill, from CI)

- [ ] **Step 1:** from the CI `report`, list every filter under 80% and its uncovered lines. For `figure-numbering.lua`, map uncovered lines to the placement × width × format matrix cells (`tests/test_figure_placement.py` already covers part of it); for `set-pieces.lua`, to the format branches; for `chapter-dropcap.lua`, to the `ornate`/`raised-cap`/hung-quote arms.
- [ ] **Step 2:** add parametrized cases until each filter is at or above 80% or every remaining uncovered line is a defensive branch, which the task report names line by line.
- [ ] **Step 3:** push; take CI's new numbers into the baseline with `update --from-report --reason "§6 backfill"`.
- [ ] **Step 4:** commit: `Backfill the Lua filter tests against the coverage report; raise the floors`.

---

## What comes after

Round 1B is the edition-parity design major (`docs/EDITION-PARITY-PLAN.md` M1–M3) as v4.0.0, planned once this round's floors are in place; the filter rewrite it requires is exactly what Tasks 3–6 protect.
