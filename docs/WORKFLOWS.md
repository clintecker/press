# Workflows and skills

The press ships two kinds of authoring machinery as package data, so a
book gets it with no copy-paste and no drift: **skills** (guides an agent
reads before it writes prose or directs art) and **workflows** (multi-step
agent procedures). Both are versioned with the press, listed by the CLI,
and resolved from the installed package first.

- `press skills` lists the installed skills with their paths.
- `press workflows` prints paste-ready workflow invocations.

Run a workflow with the Workflow tool by name from inside a book. The
scaffold lays the workflows into a book's `.claude/workflows/`, stamped
with the press version so drift is visible.

## The skills

Under `src/press/data/skills/`:

- Four prose skills, read before composing any chapter.
- **overused-jargon**, the watchlist skill. Its
  `references/watchlist.csv` is the single source of truth the jargon
  lint reads. It also ships a standalone `scripts/jargon_lint.py` (see
  below).
- Design skills for covers, plates, and logomarks.
- The registrations skill: the ISBN/LCCN/ISSN paperwork end to end.

## The workflows

Under `src/press/data/workflows/`:

- **editorial-passes** — per-chapter skill passes plus whole-book cadence,
  repetition, and arc passes; per-chapter synthesizers apply the
  suggestions; `press check` closes each round until suggestions dry up.
- **authorities-research** — builds the sources ledger.
- **aesthetic-brief** — drafts `config/aesthetic.yaml` from a one-line
  brief (`press aesthetic "<brief>"`).
- **art-direction** — reads the manuscript, applies the design skills, and
  writes paste-ready image-model prompts to `art/commissions.md`.

## The jargon checker: two copies, one contract

The jargon checker exists twice on purpose, and the two copies are held
in lockstep by a parity contract rather than by hope.

- **`src/press/jargon_lint.py`** is the package copy. `press check` runs
  it as `python -m press.jargon_lint`; it resolves its default watchlist
  through the installed package (`press.instruments`). This is the
  canonical implementation and the **owner** of the checker's behaviour.
- **`src/press/data/skills/overused-jargon/scripts/jargon_lint.py`** is
  the **portable** copy. An author or agent runs it standalone, straight
  from a checkout, with no `press` on the path — so it must not import the
  package. It resolves the same watchlist relative to its own file.

Both read the one watchlist,
`src/press/data/skills/overused-jargon/references/watchlist.csv`.

### Why a copy at all

The skill has to be usable without installing the press. Extracting a
shared engine would make the portable copy depend on the package and
defeat that. So the two files carry the same logic, and a contract proves
they stay equal instead of a shared import enforcing it.

### The parity contract

A matching, normalization, allowlist, or reporting fix must land in
**both** files. The contract closes the drift on every `press selftest`
and every test run:

- **`selftest.check_jargon_parity`** compares the two sources definition
  by definition. Every top-level function and class except `parse_args`
  (whose only sanctioned difference is how each copy finds its default
  watchlist) must be byte-identical, both copies must expose the same
  status table, and both must resolve the *same* default watchlist file.
  A logic change to only one copy turns the selftest red and names the
  drifted function.
- **`tests/test_jargon_parity.py`** adds the behavioural evidence. A
  versioned fixture/contract corpus under `tests/corpus/jargon_parity/`
  — plus the shipped known-bad fixtures and a differential property fuzz
  — is driven through *both* implementations, asserting identical
  findings (stable diagnostic identity with file and line), exit codes,
  and refusal messages. Cases cover Unicode and word-boundary edges, the
  allowlist, non-prose stripping, the regex path, and malformed
  watchlists. A divergence the fuzzer finds is minimized and stored under
  `tests/corpus/jargon_parity/seeds/` as a permanent regression case.

The corpus is versioned (`tests/corpus/jargon_parity/VERSION` and the
`version` key in `cases.yaml`); bump it when a case is added or changed so
a book pinning an older press can tell the contract moved.

This is the invariant `INV-editorial-jargon-parity`: the package checker
and the portable skill copy return equivalent findings and refusals for
the same text and watchlist, so a fix or rule cannot land in one execution
surface unnoticed.
