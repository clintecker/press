# press desk: the TUI plan

Status: designed, not scheduled. Three research passes (framework
survey, interface design, integration architecture) ran on 2026-07-19;
this document is their consolidated result. When the work is
scheduled it joins ROADMAP.md; nothing here is built yet.

## Framework decision

**Textual**, pinned `textual>=8,<9`, as an optional extra
(`pip install press[tui]`). Evidence as of 2026-07-19: MIT licensed;
v8.2.8 released 2026-06-30 with eight releases March–June 2026
(actively maintained by Will McGugan personally after Textualize the
company wound down in May 2025); asyncio-native; real adopters
(Bloomberg Memray, Harlequin, Toolong); a genuine theming system (a
warm letterpress palette is ~30 lines of Theme + TCSS); and the only
headless CI test story in the field (`App.run_test()` + Pilot +
`pytest-textual-snapshot` SVG snapshots).

Rejected: urwid (LGPL, palette-not-stylesheet theming, no headless
harness), prompt_toolkit (REPL-shaped, wrong for dashboards), py_cui
(dormant since 2022), blessed (too low-level), pyTermTk/PyTermGUI
(single-hobbyist bus factor). Lighter fallback if scope shrinks to
pretty streaming output: Rich alone (already in Textual's tree).

## The command: `press desk`

Runs only inside a book repo (same `booklib.root()` discovery and the
same refusal outside one). Seven screens on digit keys, a `:` command
palette over the full target surface, `?` help. Footer of every
screen names the CLI equivalent (`$ press verify-formats`) — the TUI
teaches its own absence.

1. **DESK** — identity row from `bookmodel.Book`; artifact table in
   `registry.ARTIFACTS` order with three states (`● fresh`,
   `○ STALE (reason file)`, `— not built`) derived from dist/ mtimes
   vs source mtimes; last-run panel with per-stage timings and deltas;
   doctor summary line; art-candidates-waiting count.
2. **BUILD (run view)** — stage list computed from
   `registry.build_order()` before launch; live output pane streaming
   the subprocess; the first-LuaLaTeX-run font-scan scar annotated
   ("this is not a hang"); exit nonzero jumps to PROBLEMS.
3. **PROBLEMS** — captured refusals parsed into a navigable list
   (`path:line` patterns; unparseable lines kept raw at the bottom,
   never dropped). Enter opens `$EDITOR` at the line; `r` re-runs the
   exact target that produced the list. The fix loop is three keys.
4. **CHECKS** — viewers over `build/jargon-report.txt`,
   `build/editorial-report.md`, wordcount.
5. **ART** — commissions from `art/commissions.md` joined with
   acceptance records; candidate grid with a terminal-graphics ladder
   (kitty → iTerm2 → sixel → chafa → open externally); aspect checks
   pre-flighted with the same tolerance art.py enforces; accept modal
   shells `press art accept`.
6. **OPERATOR** — improve/research/aesthetic through the run view;
   `--apply` stays two keys plus a confirm.
7. **DOCTOR** — `doctor.examine()` rendered with the cost column;
   gates DESK actions with the reason when a tool is missing.

Top five interactions by value: refusal→editor→rerun loop; staged
run view with timings; artifact freshness; art review with
pre-flighted accepts; the generated palette (surface parity with the
CLI, selftest-enforceable).

## Integration laws

- **Optional extra, single file.** `src/press/tui.py` top-level (so
  `selftest.modules()` import-checks it on a bare install), textual
  imported lazily inside `main()` with a doctor-style refusal naming
  the extra. `ui` route in `__main__.py` dispatch; `check_docs`
  then forces USAGE/README/REFERENCE mentions mechanically.
- **Facts in-process, work out-of-process.** The TUI imports
  `registry`, `bookmodel`, `booklib`, `doctor` for reading only.
  Every action spawns `python -m press <target>` as a subprocess and
  streams its output. This is load-bearing: the CLI routes own the
  dependency edges (verify rebuilds first), so the TUI structurally
  cannot bless a stale artifact; SystemExit stays the checkers'
  voice; lru caches never go stale across runs.
- **Two seam refactors only**: `doctor.examine()` split from its
  printer; `check_source.problems()` extracted (mirroring
  `registrations.failures()`). No verifier restructuring — fail-fast
  SystemExit is the verifier's voice and the TUI never calls them
  in-process.
- **Exit codes verbatim.** The child's returncode is the verdict; the
  TUI never reinterprets output text. One run at a time (dist/ is
  shared mutable state).
- **Testing inside the selftest philosophy**: a `check_tui()` that
  skips with a note when textual is absent, and otherwise drives the
  real app headless (Pilot) against a scaffolded book via
  `_borrow_book`; assert the artifact table equals the registry and
  the environment rows equal `doctor.examine()`. A drift guard
  asserts no artifact name appears as a string literal in tui.py.

## First milestone (M-TUI-1)

DESK screen (identity, artifact freshness, doctor) + target picker +
streamed run pane with exit verdict. Touchpoints: pyproject `tui`
extra; `src/press/tui.py`; `ui` route + USAGE line; `doctor.examine()`
split; `check_source.problems()` split; `check_tui()` in selftest;
README/REFERENCE via `--write-docs`; one CI job installing `.[tui]`.
Out of scope for M1: timing parsers, watch mode, verifier
restructuring, anything touching output bytes (keeps it inside the
current major under the design contract).
