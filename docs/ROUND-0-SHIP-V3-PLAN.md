# Round 0: unblock the gate and ship v3.0.0 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the quality gate green again, roll three months of finished work into an immutable v3.0.0 tag, and move the flagship book onto it, so the public site and the pinned pipeline describe the same press.

**Architecture:** Nothing new is designed here. The work is (1) retiring the 23 expired entries in the celebrimbor producer ledger by wiring real verifiers, reclassifying mis-cast callables, or re-dating with a reason; (2) landing the within-major EPUB corrections the edition-parity plan calls M0; (3) adding a scheduled early-warning job so a review date never ambushes the gate again; (4) running the release state machine for a new major and repinning Make Ready. Every task leaves main green and releasable on its own.

**Tech Stack:** Python 3.10–3.14, celebrimbor 0.12.0 (quality gate), pytest, GitHub Actions, `scripts/release.sh`, the pinned toolchain image.

**Spec:** this document plus the direction it implements (the executive survey of 2026-11-10, recorded in the maintainer's memory as `press-state-2026-11`), `docs/EDITION-PARITY-PLAN.md` § "M0 — Corrections", `docs/CELEBRIMBOR-SPEC.md` § "No-blind-verifier producer ledger", `CLAUDE.md` § "The contract".

## Why this round, and why first

- Last tag: v2.3.1 (2026-07-25). Main is 134 commits / 332 files ahead and the CHANGELOG's `[Unreleased]` section names two changes as a new major (the figure-placement treatment and the fine-press typography pass). The next tag is therefore **v3.0.0**.
- `.celebrimbor/producers.yaml` holds 23 `pending` producers with `review_by: 2026-10-01`. The `celebrimbor.producers` check fails every PR since 2026-10-14 (seen on Dependabot PRs #253, #254). Main was last green on 2026-08-06 only because nothing has been pushed since. **The next push to main goes red**, so this is the first task.
- The docs site deploys from main and already documents features no tag carries. Make Ready pins `@v2` and has none of them.

## Global Constraints

- The three-part tag is immutable and its release contract must prove; `scripts/release.sh vN.x.y` is the only release path (CLAUDE.md § The contract).
- Design law: within a major, a fix may correct broken output but must not change the typography or layout of a valid book. Every change in this round that touches a stylesheet must be a correction of broken output (overflow, overlap, dead rule), never a restyle. Unlisted design work from the edition-parity plan is **out of scope** here (it is v4).
- Docs law: a surface change and its documentation land in the same commit; `press selftest` enforces it.
- Never run a coverage or mutation ratchet `--update` on macOS; committed floors must match CI's Linux numbers (memory `press-release-gates`).
- Never pipe a check into `grep` before `&&` in a commit chain.
- Every new `.md` under `docs/` must be listed in `PAGES`/`FOOTER_PAGES` or `NOT_PUBLISHED` in `scripts/build_site.py`, or the site build (run by the selftest workflow) fails.
- The producer ledger schema is celebrimbor's: a proved producer names `verifier: module:callable` (the callable must be classified `verifier` in `.celebrimbor/surfaces.yaml`) and `negative_fixture: tests/file.py::test_node` (must exist). A `pending` entry needs `reason` and `review_by`.
- Pre-commit runs ruff, mypy, stylua, selene, and the Lua syntax gate; all must pass before each commit.

## Review Focus

1. **A ledger entry that "proves" a producer through a verifier that never reads its artifact.** Expected: the negative fixture feeds that exact verifier a broken artifact of that producer and asserts it goes red. Pinned in Task 2 by requiring each wired fixture to construct the bad artifact through the producer's own output path.
2. **A reclassified callable that actually writes a file.** Expected: only callables that return a value and touch no filesystem are reclassified from `producer`. Pinned in Task 2 by the reclassification test that greps each reclassified callable's body for `write_text`, `write_bytes`, `open(`, `yamlio.write`.
3. **An EPUB with a numbered figure whose caption number is lost on the EPUB branch.** Expected: `verify-formats` fails naming the missing label. Pinned in Task 3's negative test.
4. **The review-date watcher opening a duplicate issue every Monday.** Expected: one open issue per expiring ledger, updated not duplicated. Pinned in Task 4 by the dedupe test.
5. **Make Ready repinned to v3 while its working tree carries uncommitted changes** (`tex/title-page-print.tex` modified, `config/qualification.yaml` untracked as of 2026-11-10). Expected: the operator inspects and resolves those before `press migrate apply`, so the v3 render is attributable to v3 and not to a local edit. Pinned in Task 7 as an explicit preflight step.

---

### Task 1: Register this plan and prove the gate is red for the reason we think

**Files:**
- Create: `docs/ROUND-0-SHIP-V3-PLAN.md` (this file)
- Modify: `scripts/build_site.py:129-170` (`NOT_PUBLISHED`)

**Interfaces:**
- Produces: a committed plan and a reproduced local failure every later task is measured against.

- [x] **Step 1: Add the plan to `NOT_PUBLISHED`** in `scripts/build_site.py` with the reason `"internal round plan for unblocking the gate and cutting v3.0.0; lives in the repo and issues, not the docs site"`. (Done when the plan was written, so the site build stays green; uncommitted.)

- [ ] **Step 2: Reproduce the red gate locally**

Run: `python3 -m pytest -q -p no:cacheprovider --cov=press --cov-report= && celebrimbor gate --diff-base origin/main`
Expected: `celebrimbor.producers` FAILS with `23 no-blind-verifier defect(s)`, each line reading `pending producer '<subject>' passed its review date (2026-10-01)`. Record the 23 subjects in the task log; they must match the list in Task 2.

- [ ] **Step 3: Build the site to prove the plan file is accounted for**

Run: `python3 scripts/build_site.py`
Expected: exits 0; no "unaccounted" message.

- [ ] **Step 4: Commit**

```bash
git add docs/ROUND-0-SHIP-V3-PLAN.md scripts/build_site.py
git commit -m "Record the round-0 plan: unblock the producers gate and ship v3.0.0"
```

---

### Task 2: Retire the 23 expired pending producers

**Files:**
- Modify: `.celebrimbor/producers.yaml`
- Modify: `.celebrimbor/surfaces.yaml` (role overrides, ratified)
- Create: `tests/test_producer_ledger_round0.py`
- Modify (negative fixtures, one per wired producer): the test files named in the table below

**Interfaces:**
- Consumes: celebrimbor's ledger shape (Global Constraints).
- Produces: a `producers.yaml` whose `pending` block holds only `reader_meta` (review 2027-01-01) and any Class C entries with a new date, and whose `producers` block proves every other former-pending subject.

**The decision rule, applied per subject.** Classify each of the 23 into exactly one class:

- **Class A — wire a verifier.** A verifier that inspects this producer's artifact already exists. Add a `producers:` record naming it and a negative fixture that builds a *broken* artifact through the producer's own path and asserts that verifier rejects it. If the verifier's module is not yet classified `verifier` in `surfaces.yaml`, add a ratified per-callable override (`<callable>: verifier`) for just that callable; do not reclassify a whole module.
- **Class B — reclassify.** The callable returns a value and writes nothing (no `write_text`, `write_bytes`, `open(`, `yamlio.write`, no subprocess). It was cast `producer` by the `render_*`/`dump` naming heuristic. Change its override in `surfaces.yaml` to `pure` (or remove the override if the module default already fits), keep `status: ratified`, and drop it from `pending`.
- **Class C — re-date with a specific reason.** The artifact is real, no verifier inspects it yet, and writing one is bigger than this round. Replace the generic reason with one sentence naming *which* verifier is owed, and set `review_by: '2027-02-01'`. Open a GitHub issue per Class C subject titled `Producer <subject>: write <verifier> and its negative fixture`, and put the issue number in the reason.

**Starting assignments** (verified against the code on 2026-11-10; the implementer confirms each by reading the callable before acting):

| Subject | Class | Verifier / action | Negative fixture home |
|---|---|---|---|
| `edition:build` | A | `edition:verify` (`verify(manifest, root) -> list[str]`) | `tests/test_edition.py` |
| `print_safe` | A | `verify_coverwrap:check_print_safe` (already a verifier) | `tests/test_print_safe.py` |
| `profiles:write_geometry_tex` | A | `profile_lifecycle:validate` (already proves `profile_lifecycle`) | `tests/test_profiles.py` |
| `qualification:render`, `qualification:render_packaged` | A | `qualification:validate` (`validate(record) -> list[str]`) | `tests/test_qualification.py` |
| `receipts:emit`, `receipts:build_full_chain`, `receipts:build_release_receipt`, `receipts:assemble_release` | A | `receipts:verify_chain` / `receipts:verify_release` / `receipts:verify_complete` as fits each | `tests/test_receipts.py` |
| `migrate:apply`, `migrate:rollback` | A | `migrate:diagnose` (a mixed-major or missing pin is a red diagnosis) | `tests/test_migrate.py` |
| `catalog:render_usage`, `catalog:render_global_help`, `catalog:render_command_help` | B | return `str`, write nothing → `pure` | — (reclassification test below) |
| `yamlio:dump` | B | returns `str` → `pure` | — |
| `yamlio:write` | C | it is the one true YAML writer; owed verifier: a `yamlio:verify_roundtrip` that reloads and compares | issue |
| `invariants:render`, `selftest:render_reference` | B if they return text; A via `selftest_release` checks if they write `docs/INVARIANTS.md` | decide by reading | per decision |
| `scenarios` | B | module computes covering sets, returns data | — |
| `desk_model` | C | owed: a verifier over the desk's typed status model | issue |
| `aesthetic:write_tex_overrides` | C | owed: a TeX-overrides verifier (compiles or structurally checks the emitted file) | issue |
| `art_commission:commission`, `art_enhance:enhance` | C | owed: intake geometry verifier reused from `press art accept` | issue |

- [ ] **Step 1: Write the ledger-shape test**

```python
# tests/test_producer_ledger_round0.py
import datetime as dt, re
from pathlib import Path
from press import yamlio

ROOT = Path(__file__).resolve().parents[1]
LEDGER = yamlio.load(ROOT / ".celebrimbor" / "producers.yaml")
SURFACES = yamlio.load(ROOT / ".celebrimbor" / "surfaces.yaml")
WRITE_MARKERS = ("write_text", "write_bytes", "open(", "yamlio.write", "subprocess")

def test_no_pending_producer_has_an_expired_review_date():
    today = dt.date.today()
    expired = {s: e["review_by"] for s, e in LEDGER["pending"].items()
               if dt.date.fromisoformat(str(e["review_by"])) < today}
    assert expired == {}

def test_every_pending_reason_names_the_owed_verifier_or_an_issue():
    for subject, entry in LEDGER["pending"].items():
        assert re.search(r"#\d+|verify|verifier", entry["reason"]), subject

def _source_of(subject: str) -> str:
    module, _, name = subject.partition(":")
    text = (ROOT / "src" / "press" / f"{module}.py").read_text()
    if not name:
        return text
    m = re.search(rf"^def {name}\(.*?(?=^def |\Z)", text, re.S | re.M)
    assert m, subject
    return m.group(0)

RECLASSIFIED = ["catalog:render_usage", "catalog:render_global_help",
                "catalog:render_command_help", "yamlio:dump"]  # extend per Class B decisions

def test_reclassified_callables_write_nothing():
    for subject in RECLASSIFIED:
        body = _source_of(subject)
        assert not any(m in body for m in WRITE_MARKERS), subject
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/test_producer_ledger_round0.py -v`
Expected: `test_no_pending_producer_has_an_expired_review_date` FAILS listing 23 subjects; the other two pass or fail depending on current reasons.

- [ ] **Step 3: For each Class A subject, write the negative fixture first**

Each fixture follows this shape (one real example; the rest mirror it):

```python
# tests/test_edition.py
def test_verify_rejects_a_manifest_whose_interior_bytes_changed(tmp_path, built_edition):
    manifest, root = built_edition(tmp_path)          # produced through edition.build
    (root / "dist" / f"{manifest.slug}-interior.pdf").write_bytes(b"%PDF-1.4 tampered")
    problems = edition.verify(manifest, root)
    assert any("digest" in p or "bytes" in p for p in problems)
```

Run each new test alone and confirm it passes against the existing verifier (the verifier already exists; the fixture proves it bites). If a verifier does *not* go red on the broken artifact, that subject is **not** Class A: move it to Class C and open the issue.

- [ ] **Step 4: Edit `.celebrimbor/producers.yaml`**

Move each Class A subject from `pending` to `producers` with its `verifier` and `negative_fixture`. Delete each Class B subject from `pending`. Rewrite each Class C entry's `reason` and `review_by: '2027-02-01'`.

- [ ] **Step 5: Edit `.celebrimbor/surfaces.yaml`**

For Class B: change the override value to `pure` (e.g. under `catalog:` set `render_usage: pure`). For Class A verifiers not yet classified `verifier` (e.g. `edition:verify`, `qualification:validate`, `migrate:diagnose`, `receipts:verify_chain`): add a per-callable override `<name>: verifier`. Leave `status: ratified`. Do not touch `pin:` values by hand; if the gate reports a pin mismatch, run the surface re-pin the gate's hint names and review the diff.

- [ ] **Step 6: Run the gate**

Run: `python3 -m pytest -q -p no:cacheprovider --cov=press --cov-report= && celebrimbor gate --diff-base origin/main`
Expected: `celebrimbor.producers` ✓ with `N producer(s) proved through a verifier, M on a dated pending list` where `M` equals the Class C count plus one (`reader_meta`). The whole gate reports GREEN. If `celebrimbor.surface.pin` complains, follow its hint and re-run.

- [ ] **Step 7: Run the ledger test**

Run: `python3 -m pytest tests/test_producer_ledger_round0.py -v`
Expected: 3 passed.

- [ ] **Step 8: Add a CHANGELOG line under `[Unreleased]` → `### Changed`**

One bullet: the producer ledger's pending list is retired to N dated entries, each naming its owed verifier; the K former-pending producers are now proved through real verifiers with negative fixtures.

- [ ] **Step 9: Commit**

```bash
git add .celebrimbor/producers.yaml .celebrimbor/surfaces.yaml tests/ CHANGELOG.md
git commit -m "Retire the expired producer pending list: wire verifiers, reclassify renderers, re-date the rest with owed verifiers named"
```

---

### Task 3: Edition-parity M0 corrections (within-major) with their verifier

**Files:**
- Modify: `src/press/data/tex/epub.css`
- Modify: `src/press/data/web/reader.css:297`, `src/press/data/tex/book.css:114` (delete the dead `.verse .verse-line` rule only)
- Modify: `src/press/verify_formats.py:349-360` (`verify_epub`)
- Create: `tests/test_verify_epub_figures.py`
- Modify: `docs/ILLUSTRATIONS.md` (one paragraph: what the EPUB verifier now proves)

**Interfaces:**
- Consumes: `press.figures.parse(markdown) -> list[Figure]` (a `Figure` with a `kind` attribute; numbered kinds are `figure`, `chart`, `map`, `photo`, `diagram`), `booklib.root()`.
- Produces: `verify_formats.numbered_figure_count(root: Path) -> int` and `verify_formats.require_figure_labels(text: str, expected: int, label: str) -> None` (raises `SystemExit` when fewer than `expected` occurrences of the pattern `Figure \d+\.\d+\.` appear in `text`).

- [ ] **Step 1: Write the failing verifier tests**

```python
# tests/test_verify_epub_figures.py
import pytest
from press import verify_formats as vf

def test_labels_present_passes():
    vf.require_figure_labels("Figure 1.1. A map. Figure 1.2. A chart.", 2, "EPUB")

def test_missing_label_is_named():
    with pytest.raises(SystemExit) as e:
        vf.require_figure_labels("Figure 1.1. A map.", 2, "EPUB")
    assert "EPUB" in str(e.value) and "2" in str(e.value) and "1" in str(e.value)

def test_zero_numbered_figures_is_a_no_op():
    vf.require_figure_labels("no figures here", 0, "EPUB")

def test_numbered_figure_count_counts_only_informative_kinds(tmp_path, monkeypatch):
    ch = tmp_path / "book" / "chapters"; ch.mkdir(parents=True)
    (ch / "01.md").write_text(
        "![A plate](a.png)\n\n![A map](b.png){.map #m1}\n\n![A chart](c.png){.chart}\n")
    monkeypatch.setattr(vf.booklib, "root", lambda: tmp_path)
    assert vf.numbered_figure_count(tmp_path) == 2
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_verify_epub_figures.py -v`
Expected: FAIL with `AttributeError: ... has no attribute 'require_figure_labels'`.

- [ ] **Step 3: Implement in `verify_formats.py`**

`numbered_figure_count(root: Path) -> int`: walk `root/"book"/"chapters"/*.md` and `root/"book"/"appendices"/*.md` (the same directories `scripts/build_site.py:770-774` reads), call `figures.parse` on each, count figures whose `kind` is in `{"figure","chart","map","photo","diagram"}`.
`require_figure_labels(text, expected, label)`: count `re.findall(r"Figure \d+\.\d+\.", text)`; if fewer than `expected`, `raise SystemExit(f"{label} carries {found} numbered-figure labels; the source declares {expected}")`.
Call `require_figure_labels(text, numbered_figure_count(booklib.root()), "EPUB")` at the end of `verify_epub`, and the same with `"HTML"` at the end of `verify_html`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_verify_epub_figures.py tests/test_verify_editions.py -v`
Expected: all pass.

- [ ] **Step 5: Apply the three stylesheet corrections**

In `epub.css`, append:

```css
/* Corrections (edition-parity M0): a figure wider than the screen overflowed,
   a half-measure figure sat flush-left, and a short opener could overlap the
   floated initial. No colour, border, or shadow: the reader owns the theme. */
figure { margin: 1.5em 0; text-align: center; page-break-inside: avoid; }
figure img { max-width: 100%; height: auto; }
.chapter-opening::after { content: ""; display: block; clear: both; }
```

(Execution ruling: this block originally carried a `figcaption { font-size: 0.9em; line-height: 1.4; font-style: italic; }` line. The final whole-branch review found it is a restyle of every valid EPUB's caption, not a correction, so it was removed in the final fix wave; caption typography belongs to the v4 parity major.)

Delete the line `.verse .verse-line { margin: 0; }` from `epub.css`, `reader.css`, and `book.css` (it matches no emitted element; `set-pieces.lua` emits verse as one block with `<br>`). Confirm with `grep -rn "verse-line" src/press/data/lua` that no filter emits that class.

- [ ] **Step 6: Prove the PDF and the plain-book web output are unchanged**

Run: `scripts/dev-render.sh --preview` (Alice example) and `python3 -m pytest tests/test_visual_regression.py tests/test_structural_baseline.py -v`.
Expected: visual and structure baselines unchanged (the PDF path is untouched; `epub.css` is EPUB-only; the deleted rule was dead). If a structure baseline differs, stop: that means the rule was not dead.

- [ ] **Step 7: Build the gallery EPUBs through the new verifier**

Run: `python3 scripts/build_examples.py` (or the per-book form it documents) for `alice-in-wonderland` and one book with no figures (`small-hours-chapbook`).
Expected: both pass `verify-formats`; Alice reports its numbered figures found in HTML and EPUB.

- [ ] **Step 8: Document and record**

Add to `docs/ILLUSTRATIONS.md` one paragraph under the verification section: every edition is checked for as many `Figure C.N.` labels as the source declares numbered figures. Add a `### Fixed` bullet to `[Unreleased]`: EPUB figures no longer overflow or sit flush-left; a short dialogue opener no longer overlaps the drop cap in EPUB; the dead verse rule is gone; numbered-figure label parity is verified in HTML and EPUB.

- [ ] **Step 9: Commit**

```bash
git add src/press/data/tex/epub.css src/press/data/web/reader.css src/press/data/tex/book.css src/press/verify_formats.py tests/test_verify_epub_figures.py docs/ILLUSTRATIONS.md CHANGELOG.md
git commit -m "EPUB corrections (parity M0): figure overflow, drop-cap clearfix, dead verse rule; verify figure-label parity"
```

---

### Task 3b: Fold smart dashes in the site witness normaliser (added during execution)

Found while proving Task 3 in the toolchain: `press all` on the Alice example fails at the reader-site witness check with `reader site is missing 02-the-pool-of-tears.md: its witness line "myself about you: you must manage the best way you..." appears on no page`. Diagnosis (ledgered): pandoc's smart extension renders the source's `--` as U+2013 on the page; `verify_formats.normalized()` (`:36`) straightens quotes but not dashes, and `_verify_site_chapter_identity` (`:492`) matches the whole witness line as a substring, so a correct build goes red. The HTML/EPUB checks pass because they match 8-word fragments or a dash-free line. A verifier false negative, pre-existing since the site check was written (c7ccb1a), on no CI gate (the docs site builds example PDFs only), affecting any book whose chapter witness line carries `--`, `---`, or `...`.

**Files:**
- Modify: `src/press/verify_formats.py:33-37` (`STRAIGHTEN`, `normalized`)
- Test: `tests/test_verify_site_witness.py` (new)

**Interfaces:**
- Produces: `normalized()` additionally folds U+2014 → `---`, U+2013 → `--`, U+2026 → `...` on both sides, so a witness taken from source and a page rendered by pandoc's smart extension compare equal. `sentinel_present` is unchanged (sentinels are exact-case and already documented as quote-only).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_verify_site_witness.py
from press import verify_formats as vf

def test_normalized_folds_smart_dashes_and_ellipsis():
    assert vf.normalized("x -- y") == vf.normalized("x – y")
    assert vf.normalized("x --- y") == vf.normalized("x — y")
    assert vf.normalized("wait...") == vf.normalized("wait…")

def test_site_chapter_identity_accepts_a_smart_dashed_witness(tmp_path, monkeypatch):
    # one chapter whose longest line carries `--`; one site page rendering it with U+2013
    ...  # build the minimal book root + page the way the existing site tests in tests/ do, then
    vf._verify_site_chapter_identity([page])  # must not raise
```

- [ ] **Step 2: Run to verify they fail** (`.venv/bin/python -m pytest tests/test_verify_site_witness.py -v`; the first fails on the en dash).
- [ ] **Step 3: Implement**: extend the fold in `normalized()` (a `str.replace` chain or a second translate table for the single-codepoint cases plus `replace` for the multi-char targets; order em dash before en dash).
- [ ] **Step 4: Tests pass; run `tests/test_verify_editions.py` too.**
- [ ] **Step 5: Prove on the real book**: `scripts/dev-render.sh site` then, from `examples/alice-in-wonderland`, call `verify_formats.verify_site(<built site dir>)` with `.venv/bin/python`; it must pass. Then `scripts/dev-render.sh all` must exit 0.
- [ ] **Step 6: CHANGELOG `### Fixed` bullet** (one sentence: the reader-site witness check no longer refuses a correct build whose witness line carries a smart dash or ellipsis).
- [ ] **Step 7: Commit**: `Fold smart dashes in the site witness check so a correct build is not refused`.

---

### Task 4: A scheduled early warning for expiring ledger entries

**Files:**
- Create: `scripts/ledger_review_watch.py`
- Create: `tests/test_ledger_review_watch.py`
- Create: `.github/workflows/ledger-review.yml`
- Modify: `CONTRIBUTING.md` (one paragraph under the quality-gate section)

**Interfaces:**
- Produces: `ledger_review_watch.expiring(ledger: dict, today: date, horizon_days: int = 30) -> list[tuple[str, date, str]]` (subject, review_by, reason), `ledger_review_watch.render_issue(rows) -> tuple[str, str]` (title, body), and a CLI `python3 scripts/ledger_review_watch.py [--today YYYY-MM-DD] [--horizon 30] [--open-issue]`. The title is the constant `"Producer ledger: pending entries expire within 30 days"` so the workflow can dedupe by exact title.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ledger_review_watch.py
import datetime as dt, importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location(
    "ledger_review_watch", Path(__file__).resolve().parents[1] / "scripts" / "ledger_review_watch.py")
w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)

LEDGER = {"version": 1, "producers": {}, "pending": {
    "a:x": {"reason": "owed verifier (#300)", "review_by": "2027-01-15"},
    "b:y": {"reason": "owed verifier (#301)", "review_by": "2027-06-01"},
    "c:z": {"reason": "already expired", "review_by": "2026-12-01"},
}}

def test_expiring_includes_soon_and_already_expired_but_not_far():
    rows = w.expiring(LEDGER, dt.date(2026, 12, 20), 30)
    assert [r[0] for r in rows] == ["c:z", "a:x"]      # soonest first

def test_nothing_expiring_is_empty():
    assert w.expiring(LEDGER, dt.date(2026, 6, 1), 30) == []

def test_issue_title_is_stable_and_body_lists_each_subject():
    title, body = w.render_issue(w.expiring(LEDGER, dt.date(2026, 12, 20), 30))
    assert title == "Producer ledger: pending entries expire within 30 days"
    assert "c:z" in body and "a:x" in body and "2027-01-15" in body
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_ledger_review_watch.py -v`
Expected: FAIL (file not found).

- [ ] **Step 3: Implement `scripts/ledger_review_watch.py`**

Pure functions as specified; the CLI loads `.celebrimbor/producers.yaml` with `press.yamlio.load`, prints the rows, exits 0 when empty and 0 when non-empty (it warns, it does not fail). With `--open-issue` it runs `gh issue list --state open --search "<title> in:title" --json number` and either `gh issue edit <n> --body` or `gh issue create --title --body --label maintenance`. Subprocess calls live in this script, which is outside `src/press`, so the adapters boundary gate does not apply; say so in the module docstring.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_ledger_review_watch.py -v`
Expected: 3 passed.

- [ ] **Step 5: Add the workflow**

`.github/workflows/ledger-review.yml`: `on: schedule: - cron: "17 8 * * 1"` plus `workflow_dispatch`; `permissions: contents: read, issues: write`; one job on `ubuntu-24.04` that checks out with the same pinned `actions/checkout` SHA as `roadmap.yml`, sets up Python with the same pinned `actions/setup-python`, installs with `pip install --require-hashes -r requirements-lock.txt` then `pip install --no-deps -e .` (execution ruling: the plan first said `pip install -e .`; the final review flagged unpinned PyPI bytes in a job holding `issues: write`, so the install follows `action.yml`'s lock-and-hashes law), a `concurrency` group mirroring `roadmap.yml`'s write job, and runs `python3 scripts/ledger_review_watch.py --open-issue` with `GH_TOKEN: ${{ github.token }}`.

- [ ] **Step 6: Run it once by hand to prove the dedupe**

Run: `python3 scripts/ledger_review_watch.py --today 2027-01-20 --horizon 30` (dry, no issue) and confirm it lists the Class C entries dated 2027-02-01. Then `gh workflow run ledger-review.yml` after the push in Step 8 and confirm exactly one issue exists after two runs.

- [ ] **Step 7: Document**

In `CONTRIBUTING.md`'s quality-gate section: a pending producer is debt with a deadline; the Monday ledger-review job opens or updates one issue when any entry is within 30 days; resolving it means writing the verifier, not moving the date.

- [ ] **Step 8: Commit**

```bash
git add scripts/ledger_review_watch.py tests/test_ledger_review_watch.py .github/workflows/ledger-review.yml CONTRIBUTING.md
git commit -m "Warn thirty days before a producer review date expires, instead of failing the gate on the day"
```

---

### Task 5: Merge the Dependabot backlog on a green gate

**Files:**
- Modify: `requirements-lock.txt` (regenerated), `pyproject.toml` (dev floors), `.github/workflows/*.yml` (action SHAs)

**Interfaces:**
- Consumes: Task 2's green gate (these PRs fail only on `celebrimbor.producers`).

- [ ] **Step 1: Push the branch carrying Tasks 1–4 and open its PR; wait for `Press selftest` green.**

- [ ] **Step 2: Rebase and merge, in this order, letting CI prove each:** #253 (actions group), #239, #240, #241, #242, #243 (dev floors), then #254 (pypdf 6.21.4).

For #254: after merging, run `scripts/lock-deps.sh` locally (Docker required) so `requirements-lock.txt` carries pypdf 6.21.4's hashes, then `scripts/verify.sh --full`. Commit the lock as `Regenerate the dependency lock for pypdf 6.21.4`.

- [ ] **Step 3: Close, do not merge, #181** (Ubuntu 26.04 toolchain base). Comment: a toolchain base change alters a valid book's output and is a major in its own right; tracked for the v4 window.

- [ ] **Step 4: Triage #204 and #146** (both non-bot, from July): rebase if still wanted, otherwise close with a one-line reason. Decision rests with the maintainer; the implementer leaves a comment summarizing each diff and stops.

- [ ] **Step 5: Confirm main is green**

Run: `gh run list --workflow "Press selftest" --branch main --limit 1 --json conclusion`
Expected: `success`.

---

### Task 6: Cut v3.0.0

**Files:**
- Modify: `CHANGELOG.md` (roll `[Unreleased]` → `## [3.0.0] - <date>`)
- Modify: `docs/MIGRATION.md` (add "What v2 → v3 actually changes")
- Modify: `src/press/data/template/requirements.txt:4`, `src/press/data/template/dot-github/workflows/book.yml:18` (`@v2` → `@v3`)
- Modify: `src/press/migrate.py` only if `to_major` is not already derived from the installed press version (check `plan(root, to_major)` callers in `__main__.py`)
- Modify (by the script): `pyproject.toml` version, `.github/workflows/build.yml` action pin

**Interfaces:**
- Consumes: a green main (Task 5).
- Produces: immutable tag `v3.0.0`, floating `v3`, a GitHub Release.

- [ ] **Step 1: Write the migration section**

In `docs/MIGRATION.md`, after the v1 → v2 section, add `## What v2 → v3 actually changes` covering, from the CHANGELOG: the figure treatment (placement vocabulary, numbered figures, List of Figures), the fine-press typography pass (microtype, oldstyle figures, selnolig, widow/orphan/runt discipline, the abbreviation-spacing filter), and the statement that these move glyph positions and line breaks in **every** book, so v3 is a re-proof of a book's PDF, not a byte-identical repin. Update the pin table to `@v2` → `@v3`.

- [ ] **Step 2: Move the template pins to `@v3`** in the two template files, and add a test if none exists: `tests/test_scaffold*.py` asserting the scaffolded book's `requirements.txt` and workflow name the press major equal to the first dot-separated component of `press.version()`. That function reads the installed distribution's version; there is no `__version__` attribute.

- [ ] **Step 3: Confirm `press migrate` targets v3**

`_run_migrate` in `src/press/__main__.py:201` computes `to_major = diagnosis.from_major + 1`, so a `@v2` book already plans `@v3`; no code change is expected. Prove it: in a scratch copy of a `@v2` book (the Alice example's book directory, or Make Ready), run `press migrate` with this checkout installed editable.
Expected: the plan shows `@v2 → @v3` in both pin sites and writes nothing.

- [ ] **Step 4: Roll the changelog**

Rename `## [Unreleased]` to `## [3.0.0] - <today>`, insert a fresh empty `## [Unreleased]` above it, and write the release's opening paragraph: a design major; name the two design changes and that everything else is compatible.

- [ ] **Step 5: Run the local release gates (memory `press-release-gates`)**

```bash
scripts/verify.sh --full
python3 -m build --wheel --outdir /tmp/dw && python3 -m venv /tmp/tui && /tmp/tui/bin/pip install "$(echo /tmp/dw/*.whl)[tui]" pytest pytest-asyncio && /tmp/tui/bin/python -m pytest tests/test_desk_app.py tests/test_desk_run.py
git status --porcelain
```

Expected: verify GREEN including the container gauntlet; desk suite passes from the wheel; porcelain output empty.

- [ ] **Step 6: Commit the roll and push to main (via PR, CI green).**

```bash
git add CHANGELOG.md docs/MIGRATION.md src/press/data/template tests/
git commit -m "Roll the changelog into 3.0.0; template and migration target v3"
```

- [ ] **Step 7: Release**

Run: `scripts/release.sh v3.0.0`
Expected: the script pins build.yml and pyproject, commits, tags, waits for the tag's release contract, floats `v3`, publishes the Release. If any step fails, fix and **rerun the same command**; do not hand-tag.

- [ ] **Step 8: Verify the public state**

Run: `gh release view v3.0.0 --json tagName,isDraft` and `git ls-remote origin refs/tags/v3`
Expected: release exists, not draft; `v3` resolves to the same commit as `v3.0.0`. Open <https://clintecker.github.io/press/> and confirm the changelog page shows 3.0.0.

---

### Task 7: Move Make Ready to v3 and keep the physical proof in view

**Files (in `~/code/make-ready`):**
- Modify: `requirements.txt`, `.github/workflows/<ci>.yml` (through `press migrate apply`)

**Interfaces:**
- Consumes: tag `v3.0.0` and floating `v3` (Task 6).

- [ ] **Step 1: Preflight the book's working tree**

Run: `cd ~/code/make-ready && git status --short`
Expected on 2026-11-10: `M tex/title-page-print.tex` and `?? config/qualification.yaml`. Show the diff to the maintainer; commit, stash, or discard **by their decision** before migrating. Do not migrate over an unexplained local change.

- [ ] **Step 2: Migrate**

Run: `press migrate` (plan), then `press migrate apply`, then `press migrate status`.
Expected: both pin sites now read `@v3`; a backup is recorded.

- [ ] **Step 3: Build and verify locally against the pinned toolchain**

Run: `scripts/dev-render.sh --book ~/code/make-ready --preview` from the press checkout, then `press all` inside the book with press v3.0.0 installed from the tag (`pip install "press @ git+https://github.com/clintecker/press@v3.0.0"`).
Expected: every verifier passes. Look at the page previews around every plate, the first page of every chapter (drop caps, hung quotes), and any page with a wrap figure. A visual regression here is a v3.0.1 fix in press, not a book edit.

- [ ] **Step 4: Push the book and let its CI build on `build.yml@v3`.** Expected: green; the published reader and PDF update.

- [ ] **Step 5: Hand the golden-copy order (#143) to the maintainer**

Write a short checklist comment on #143: the edition id of this v3 build, the cost cap, the destination allowlist, the inspection points from #117, and where the receipts go. This step is human-run and paid; the implementer prepares it and stops.

---

## What comes after this round (not in this plan)

Each gets its own plan when Round 0 ships; the specs already exist.

- **Round 1 — v4.0.0, edition parity.** First `docs/LUA-QUALITY-PLAN.md` § M3 (the luacov ratchet, within-major) so the filter rewrite has a floor under it; then `docs/EDITION-PARITY-PLAN.md` M1–M3 (placements everywhere, illustration navigation, set-pieces at full fidelity), with the cross-edition verification shipping *with* each capability. M4–M5 only if M1–M3 land cleanly.
- **Round 2 — the finisher.** Issues #219 (verify a supplied print-ready interior; useful on press's own PDFs first), then #218 (the `interior:` source mode), then #220 (honest degradation of the reading site). Acceptance is a real externally-designed interior through the whole path.
- **Stays parked:** the commerce icebox (#119–#142), #173, #224, #6, and the Ubuntu 26.04 toolchain base (#181, a future major).
