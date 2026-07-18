# press

The 2389 Research Press: everything required to turn a directory of
Markdown chapters into a publishable book. One `press all` produces a
verified 6 x 9 PDF, EPUB, single-file HTML, per-chapter reader site,
stitched Markdown, plain text, DOCX, a GitHub Pages site with public
downloads, and gated GitHub releases; the print pack adds a
print-profile interior, a cover wrap with computed spine and EAN-13
barcode, and retail channel checklists.

Extracted from the production of *Mostly Done.* so the next book
inherits the pipeline, the design, the editorial enforcement, and the
scars.

## Start a book

```sh
pip install -e .          # from a clone of this repo
press new my-book         # scaffold a new book repository
cd my-book && git init && make all
```

Everything the pipeline knows about a book comes from the book's own
`config/` (see CLAUDE.md for the full contract). The scaffolded workflow
calls this repo's reusable build at a pinned tag. Two one-time grants per
setup: this repo's Actions access is set to "repositories owned by
clintecker" (done once, already set), and each new book repo needs read
access to the private toolchain package under its Manage Actions access
settings before its first CI run can pull the image.

## Targets

- Building: `pdf epub html markdown site txt docx pages source all` --
  `press all` runs the full gauntlet: editorial checks (including
  proving the checkers can fail), every format, source archive, Pages
  assembly, then structural verification of every artifact.
- Checking: `check style verify verify-formats` -- `check` is the
  editorial law (source checks, checker self-test, style audit, jargon
  lint, registrations arithmetic, orphaned plates); the verify targets
  rebuild before verifying so a stale artifact can never be blessed.
- Print pack: `print verify-print coverwrap publish` -- a twoside
  interior with mirrored margins and black ink (verified from the
  rendered pages), a cover wrap whose spine width is computed from the
  interior and paper stock with a validated EAN-13 barcode, and
  `press publish kdp|ingram` channel checklists.
- Art: `art` -- `press art commission` submits the prompts the
  `art-direction` workflow wrote to image models (GPT Image, Gemini) at
  print-grade sizes, collecting candidates under `art/candidates/`; an
  author photograph at `art/author-photo.jpg` turns the portrait
  commission into an engraving of the actual author. `press art accept
  <file> --as cover|plate:<name>|logomark|portrait` takes a chosen
  image into the book in house format.
- Operator: `improve research aesthetic` -- the agent workflows as
  shell commands, driven headlessly through the Claude Code CLI.
  `press improve` writes `build/editorial-report.md` and touches
  nothing (`--apply` is the deliberate hand); `press research` builds
  the table of authorities; `press aesthetic` prints the book's
  effective visual identity, and `press aesthetic "<brief>"` drafts
  `config/aesthetic.yaml` from an author's description ("1970s pulp
  sci-fi paperback"), which every art commission then applies.
- Instruments: `skills workflows` -- the packaged authoring skills and
  agent workflows, with installed paths, paste-ready invocations, and
  pinned-copy drift detection inside a book.
- Utilities: `render wordcount clean new selftest` -- `press selftest`
  is the press checking itself: module imports, check-digit arithmetic,
  and that this README and the CLI usage stay honest about every
  target.
