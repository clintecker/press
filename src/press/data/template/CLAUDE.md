# CLAUDE.md

This repository is a book: the manuscript, its config, and its art, and
nothing else. All machinery (builds, checks, verification, editorial
workflows, authoring skills) lives in the press package. If this book
seems to need machinery, the machinery belongs in the press, not here.

## Layout

- `book/chapters/*.md` is the manuscript, ordered by filename prefix
  (`00-`, `01-`, ...). `book/appendices/` (optional) orders by letter
  prefix (`a-`, `b-`, ...).
- `config/metadata.yaml` is identity and verification: title, author,
  slug, sentinels, minimum pages. `config/house-rules.yaml` (optional)
  adds banned patterns and jargon allowances.
- `assets/` and `tex/title-page.tex` are optional art and front matter;
  every build degrades gracefully when they are absent.
- CI calls the reusable press workflow; `.github/workflows/book.yml` is
  the whole file and should stay that way.

## Commands

`press <target>` (or `python3 -m press <target>`, or `make <target>`)
from the repo root:

- `press check` — editorial law: source checks, style audit, jargon lint.
  Run it after any manuscript change.
- `press all` — check, build every format, verify every artifact.
- `press pdf` / `epub` / `html` / `site` / ... — one format.
- `press verify` / `press verify-formats` — rebuild and verify (never
  verifies stale artifacts; the rebuild is deliberate).
- `press aesthetic` — the book's effective visual identity;
  `press aesthetic "<brief>"` drafts `config/aesthetic.yaml` from your
  description of the look (any era, any shelf), which the art
  workflows then apply. Without the file the house Victorian idiom
  applies.
- `press art accept <file> --as cover|plate:<name>|logomark|portrait` —
  take a commissioned image into the book in house format; prompts come
  from the `art-direction` workflow's `art/commissions.md`, and
  `press art commission` submits them to image models. Supply your
  photograph at `art/author-photo.jpg` and the portrait commission
  engraves you rather than an invented author. The photograph is the
  reference an engraver works from: head and shoulders filling the
  frame, no hat, no sunglasses, even light, and no other face in the
  shot (including faces printed on clothing). Try alternates with
  `--photo <path>`; candidates number upward and never overwrite.
- `press skills` — the installed authoring skills with absolute paths.
  Read the four prose skills before composing or revising prose; read the
  design skills before art direction.
- `press workflows` — the installed agent workflows with paste-ready
  invocations.

## Workflows

Copies scaffolded into `.claude/workflows/` (pinned; the header comment
records the press version they came from). `editorial-passes` is the
iterative editorial machine for after composing or revising chapters;
`authorities-research` builds `config/authorities.yaml`, the table of
authorities, from researched sources; `art-direction` writes
`art/commissions.md` with finished image-model prompts for the cover,
chapter plates, logomark, and author portrait. Run `press workflows` from this
repo for the exact paste-ready invocations and current args; it also
reports whether the pinned copies have drifted from the installed press.

## House laws

`press check` enforces these mechanically; write to them rather than
fixing after:

- No em or en dashes anywhere; rewrite the sentence instead.
- Straight quotes only; sentence-case headings; no manual heading
  numbers.
- ASCII plus accented latin only; paragraphs under 190 words; no
  trailing whitespace.
- Sentinel strings in `config/metadata.yaml` must survive every
  revision verbatim; they are how the verifiers prove the book is in
  the artifacts.
- Fixtures under `tests/known-bad/` must stay rejected; they are the
  proof the checkers still work.
