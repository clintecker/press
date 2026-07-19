# `press desk`: direction and delivery plan

Status: scheduled as
[v1.15 — Operator desk](https://github.com/clintecker/press/milestone/11),
after the accumulated-trust work in v1.12–v1.14. v1.10 is complete; v1.11 is
the active implementation front. The desk work must not bypass or compete with
the typed-adapter, test-harness, and trust-receipt foundations it consumes.

## Product purpose

`press desk` is an optional terminal interface for operating a book repository.
It makes the existing press easier to observe and drive; it is not a second
publishing engine. A user should learn the CLI while using it: every action
shows its exact `press ...` equivalent, every refusal keeps the checker’s
meaning, and uninstalling the extra leaves a complete command-line workflow.

The v1.15 MVP contains three user-visible surfaces:

1. **DESK** — normalized book identity, every applicable artifact’s evidence
   state, doctor capabilities, and actions with explicit refusal reasons.
2. **Target picker and palette** — generated from the same typed command catalog
   as CLI help and the public reference.
3. **RUN** — the exact child invocation, structured stage evidence, verbatim
   stdout/stderr, cancellation state, and the child’s unmodified verdict.

PROBLEMS/editor integration, CHECKS, ART review, OPERATOR flows, run history,
timing comparisons, terminal graphics, and watch mode remain later work. They
must grow from the v1.15 command, event, evidence, and testing contracts rather
than being prebuilt as speculative screens.

## Framework decision and current research

Use **Textual**, pinned to the supported v8 major as an optional `tui` extra:
`pip install press[tui]`. The decision was reverified on 2026-07-19 against
primary sources:

- [Textual v8.2.8](https://github.com/Textualize/textual/releases/tag/v8.2.8)
  was released 2026-06-30.
- Textual’s official
  [`App.run_test()` and Pilot guidance](https://textual.textualize.io/guide/testing/)
  provides headless interaction at fixed terminal sizes.
- Its [worker contract](https://textual.textualize.io/guide/workers/) explicitly
  covers non-blocking subprocess I/O.
- Its [theme API](https://textual.textualize.io/guide/design/) supports a
  registered press palette without embedding book-specific design facts.
- Python packaging formally supports
  [optional dependency extras](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/#dependencies-optional-dependencies).

The choice is an adapter decision, not a domain dependency. Read models, command
descriptors, evidence projection, event parsing, and process control must import
no Textual code. A future framework change should replace the UI adapter without
rewriting publishing policy.

## Directionality laws

### Facts flow inward from authoritative models

Book identity comes from `bookmodel.Book`; artifact identity and order come from
`registry.ARTIFACTS`; commands come from one typed command catalog; capability
gating comes from typed doctor findings; artifact state comes from content
digests and trust receipts. Widgets do not parse YAML, probe tools, walk `dist/`,
or restate command and artifact names.

### Reads are in-process; mutations cross the CLI boundary

The desk may assemble immutable read models in-process. Every build, check,
verification, art, operator, clean, or other mutation launches
`sys.executable -m press <cataloged invocation>` in the book root. This preserves
the CLI’s dependency edges, exit semantics, cache lifetime, and stale-artifact
guards. Exactly one mutating child may run for a book at a time.

### The return code is the verdict; events are evidence

Human stdout is not an API. Child commands expose an opt-in, versioned structured
event channel for stages, diagnostics, artifacts, and completion while retaining
raw stdout/stderr. The child return code or termination signal remains the
verdict. Unknown or malformed events are visible protocol failures; they cannot
turn a failed child green or cause raw output to disappear.

### Nothing correctness-bearing is time-based

The desk never infers “fresh” or “stale” from mtimes, wall clocks, durations, or
polling intervals. Truthful artifact states are absent, present-unverified,
verified-current, changed-since-proof, or invalid/incomplete evidence. A
font-scan scar may be shown when a named LuaLaTeX stage is active, not after a
timer expires. Tests use completion signals and controlled fake processes, never
sleeps.

### Optional means independently proven

A bare installed wheel must import and run without Textual. A wheel installed
with `[tui]` must load all desk assets and pass headless tests. Missing extras,
wrong roots, unavailable tools, spawn failures, nonzero children, cancellation,
and corrupt evidence are active signals with exact tests, not screenshots or
log-text guesses.

## Architecture seams

- A small lazy CLI entry owns the one public name: `press desk`. There is no
  `press ui` alias.
- A composable `press.desk` package separates application shell, screens,
  widgets, immutable read models, and adapters; the seven-screen vision does not
  become one `tui.py` god module.
- The command catalog generates CLI help, reference documentation, target picker,
  and palette membership. Argument-bearing commands use typed forms; arbitrary
  shell strings are never accepted.
- `doctor.examine(probe=...)` returns typed findings and the existing CLI becomes
  a renderer over them.
- Artifact status projects registry entries through digest/receipt evidence from
  the accumulated-trust chain. Present bytes without current proof are explicitly
  unverified.
- A UI-independent process controller owns launch, stream framing, structured
  event parsing, cancellation, concurrency refusal, and terminal outcomes.
- Textual workers adapt that controller; they do not contain subprocess policy.

## Testing contract

The testing scaffold precedes feature screens. It uses Textual Pilot with fixed
80×24 and expanded viewports, composable neutral book fixtures, injected doctor
and evidence models, and controlled fake child processes. Semantic assertions
cover focus, bindings, state transitions, return codes, exceptions, refusals,
files, digests, and receipts. SVG snapshots supplement those assertions for
layout review; they never substitute for behavior proof.

One installed end-to-end gate must cross the complete boundary: wheel plus
`[tui]`, neutral scaffold, real desk headlessly, generated command selection,
real CLI child, raw and structured output, exact verdict, and refreshed evidence.
Seeded sabotage must prove the gate refuses missing extras, wrong roots,
malformed events, child failure, changed bytes, wrong receipts, and concurrent
launches.

## Delivery graph

Foundation work can proceed only when its named earlier-milestone dependencies
are ready:

- [#100 command catalog](https://github.com/clintecker/press/issues/100)
- [#101 digest/receipt artifact status](https://github.com/clintecker/press/issues/101)
  (depends on [#93 trust receipts](https://github.com/clintecker/press/issues/93))
- [#102 structured child-event protocol](https://github.com/clintecker/press/issues/102)
- [#103 typed doctor findings](https://github.com/clintecker/press/issues/103)
- [#104 optional package and entry boundary](https://github.com/clintecker/press/issues/104)
- [#108 headless harness](https://github.com/clintecker/press/issues/108)

Composition follows those foundations:

- [#105 single-child controller](https://github.com/clintecker/press/issues/105)
- [#106 DESK read model](https://github.com/clintecker/press/issues/106)
- [#107 Textual shell and theme](https://github.com/clintecker/press/issues/107)
- [#109 streamed RUN view](https://github.com/clintecker/press/issues/109)
- [#111 generated picker and palette](https://github.com/clintecker/press/issues/111)
- [#112 DESK screen](https://github.com/clintecker/press/issues/112)

Delivery closes through:

- [#110 installed wheel matrix](https://github.com/clintecker/press/issues/110)
- [#113 public and contributor documentation](https://github.com/clintecker/press/issues/113)
- [#114 installed end-to-end release gate](https://github.com/clintecker/press/issues/114)

The milestone is not complete merely because the interface launches. It is
complete when the installed, deterministic, evidence-bearing workflow is part of
the accumulated-trust release chain.
