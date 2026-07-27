# Lua filter quality: testing, coverage, linting, formatting

## Current state

Six Lua filters run inside pandoc's bundled Lua 5.4 and shape every edition:
`chapter-dropcap.lua`, `figure-numbering.lua`, `print-safe-images.lua`,
`scene-break.lua`, `set-pieces.lua`, `typographic-spacing.lua`. This is real
production code — `figure-numbering.lua` alone carries ~60 branch points
(per-format × per-placement × per-width) — and it gets materially less
engineering rigour than the Python beside it.

**What exists.** Integration tests, pandoc-gated. Each filter but one has a
pytest that runs `pandoc --lua-filter=…` and asserts the output
(`test_figure_numbering_filter.py`, `test_figure_placement.py`,
`test_set_pieces.py`, `test_scene_break.py`, `test_dropcaps_filter.py`,
`test_typographic_spacing.py`). Every one is
`skipif(shutil.which("pandoc") is None)` — so on a dev box without pandoc they
all silently skip, and only the toolchain image, which ships pandoc, actually
runs them.

**What is missing.**

- **No syntax gate.** Nothing compiles a filter before a render. A typo — like
  the stray non-ASCII character an edit dropped into a `\pandocbounded` comment
  earlier this session — surfaces only when pandoc or LuaLaTeX chokes mid-build,
  not at commit.
- **No linter.** No luacheck/selene, no `.luacheckrc`. Undefined globals, unused
  locals, shadowed variables, and typo'd field accesses go uncaught.
- **No formatter.** No stylua / `stylua.toml`. Style (2-space indent, ~88 cols)
  is by hand and by habit, not enforced.
- **No coverage.** `scripts/coverage_ratchet.py` and `scripts/mutation_ratchet.py`
  gate the Python and never see the Lua; we do not know which of those ~60
  branches any test exercises. The placement matrix (6 placements × 3 widths × 5
  formats) is a lot of untracked paths.
- **A filter with no focused test.** `print-safe-images.lua` has no filter test
  (`test_print_safe.py` covers the Python `print_safe` module, not the Lua); it
  is exercised only incidentally through full-build integration, if at all.
- **No Lua tooling in the toolchain image.** The image ships `pandoc` — hence a
  Lua 5.4 interpreter, `pandoc lua` — but no luacheck, selene, stylua, or luacov.

## Goals

Treat the Lua as first-class: a syntax gate, a linter, and a formatter on every
commit; fast pure-logic unit tests that need no pandoc; integration tests that
cannot silently skip where they must run; and line coverage tracked with a
no-regression ratchet, exactly as the Python is. None of this changes rendered
output, so every item is `[within-major]`.

## Plan

Ordered cheapest-and-highest-value first.

### 1. Syntax gate — `[within-major]` · effort S · risk low

A `tests/test_lua_compiles.py` that, for every `src/press/data/lua/*.lua`, runs
`pandoc lua -e "assert(loadfile(arg[1]))" -- <file>` — pandoc's own Lua 5.4, no
extra install — and asserts it loads. Wire the same one-liner into
`.pre-commit-config.yaml` as a local hook. Fails the moment a filter has a syntax
error, instead of deep in a LuaLaTeX run. It replaces the ad-hoc `luac -p` reached
for by hand today.

### 2. Formatter — stylua — `[within-major]` · effort S · risk low (one-time churn)

Add `stylua.toml` (`indent_type = "Spaces"`, `indent_width = 2`,
`column_width = 88`, `quote_style = "AutoPreferDouble"`) and the official
`JohnnyMorganz/StyLua` pre-commit hook. One reformat commit touches all six files
— whitespace only, output byte-identical, so not a design change — after which
`stylua --check` gates. stylua ships as a single static binary; add it to the
toolchain image.

### 3. Linter — luacheck — `[within-major]` · effort M · risk low

Add a `.luacheckrc` scoped to the filter idiom, so pandoc's injected globals and
the filter callbacks are not flagged:

```lua
std = "lua54"
max_line_length = 88
read_globals = { "pandoc", "FORMAT", "PANDOC_VERSION",
                 "PANDOC_STATE", "PANDOC_READER_OPTIONS" }
globals = { "Pandoc", "Meta", "Div", "Image", "Figure", "Para", "Plain",
            "Header", "Cite", "Str", "RawBlock", "RawInline" }
```

plus a pre-commit hook. Catches undefined globals, unused locals, shadowing, and
over-long lines. Primary recommendation is **luacheck** (the established
pandoc-filter linter). Where adding a Lua + luarocks layer to the image is
unwelcome, **selene** — a single Rust binary with a custom pandoc `std` TOML — is
the drop-in alternative. Pick one, not both.

### 4. Pure-logic unit tests — `[within-major]` · effort M · risk low

The filters mix pure computation — the tail's sine offset and size ramp, the
cascade step, the fairy-dust geometry, `width_opt`, the `MEASURE_*`/`MEASURE_GUARD`
maps, the `\Needspace` guard sizing — with pandoc-AST manipulation. Extract the
pure helpers into a `require`-able module (`src/press/data/lua/press-util.lua`)
and unit-test them under standalone Lua 5.4 (or `pandoc lua`) with **busted**:
fast, deterministic, no render, runnable on any dev box. The AST-shaping stays
integration-tested through pandoc. The split also removes the measure tables now
duplicated between `figure-numbering.lua` and the CSS-side logic.

### 5. Coverage + ratchet — luacov — `[within-major]` · effort L · risk M

Measure line coverage of the filters and gate it. Mechanism: put luacov on
`LUA_PATH`, run the integration + unit suites with `require("luacov")` active
(pandoc's embedded Lua honours it when the module loads at filter start, or via a
tiny wrapper filter prepended in a coverage mode), collect `luacov.stats.out`, and
add `scripts/lua_coverage_ratchet.py` in the exact shape of
`scripts/coverage_ratchet.py` — a committed floor CI refuses to drop below.
Fallback if hooking pandoc's embedded Lua proves unreliable: measure coverage of
the extracted pure module (§4) under standalone lua + luacov, and keep the AST
paths on the integration suite's pass/fail. Wire into `scripts/gauntlet.sh` and
`scripts/verify.sh` beside the Python ratchets.

### 6. Close the test gaps — `[within-major]` · effort S · risk low

Add `test_print_safe_images_filter.py` that runs `print-safe-images.lua` through
pandoc — the one filter with no focused test. Then read the coverage report from
§5 and add cases for the uncovered branches, especially the placement × width ×
format matrix in `figure-numbering.lua` and the format branches in
`set-pieces.lua`.

### 7. No silent skip in CI — `[within-major]` · effort S · risk low

Every Lua test is `skipif(no pandoc)`. Add the epubcheck-style guard (see
`verify_formats.py:353-368`): when `PRESS_TOOLCHAIN` is set, a missing pandoc is a
hard error, not a skip, so the Lua suite and the syntax gate can never green-skip
where a release is cut. Add luacheck/selene, stylua, and luacov to the toolchain
image so §1–§5 have their tools in CI, and document them in `press doctor`.

## Sequencing

- **M1 (about a day): the cheap gates.** Syntax gate (§1), formatter (§2), linter
  (§3), toolchain tools + no-silent-skip (§7). Immediate regression protection,
  zero output change.
- **M2: real tests.** Pure-logic extraction + unit tests (§4); the missing
  print-safe test and the first matrix cases (§6).
- **M3: coverage.** luacov + ratchet (§5), wired into the gauntlet beside the
  Python ratchets; backfill §6 against the coverage report.

## Non-goals

- No rewrite of the filters and no change to rendered output — every item is
  `[within-major]`.
- No heavyweight Lua build system or luarocks-in-CI if a single-binary linter
  (selene) and pandoc's own Lua interpreter suffice.
- Not chasing 100% line coverage; the ratchet is a floor that only rises, as with
  the Python.
