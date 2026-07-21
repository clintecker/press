<picture>
  <source media="(prefers-color-scheme: dark)" srcset="site/brand/press-lockup-dark.svg">
  <img src="site/brand/press-lockup.svg" alt="press" width="300">
</picture>

# press

A complete small press: everything required to turn a directory of
Markdown chapters into a publishable book. One `press all` produces a
verified 6 x 9 PDF, EPUB, single-file HTML, per-chapter reader site,
stitched Markdown, plain text, DOCX, a GitHub Pages site with public
downloads, and gated GitHub releases; the print pack adds a
print-profile interior, a cover wrap with computed spine and EAN-13
barcode, and retail channel checklists.

Extracted from the production of *Mostly Done.* so the next book
inherits the pipeline, the design, the editorial enforcement, and the
scars.

New here? The
[quickstart](https://github.com/clintecker/press/blob/main/docs/QUICKSTART.md)
is the canonical first-run path: a copyable walk from a blank machine to a
built, verified book. Install with docs/INSTALL.md; understand the machine
with the
[architecture](https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md),
configure a book with the
[configuration reference](https://github.com/clintecker/press/blob/main/docs/CONFIGURATION.md),
look up any artifact in the generated
[reference](https://github.com/clintecker/press/blob/main/docs/REFERENCE.md),
trace every guarantee in the generated
[invariant ledger](https://github.com/clintecker/press/blob/main/docs/INVARIANTS.md),
see what is coming in the
[roadmap](https://github.com/clintecker/press/blob/main/ROADMAP.md) and what
changed in the
[changelog](https://github.com/clintecker/press/blob/main/CHANGELOG.md);
contribute with CONTRIBUTING.md.

MIT licensed, code and bundled content alike (the authoring skills,
templates, and design files ship under the same terms; see LICENSE).
A book you make with the press is yours entirely.

The press is maintained by one person (Clint Ecker, LGTM Systems, LLC);
[GOVERNANCE.md](GOVERNANCE.md) says plainly how decisions, releases, and
conduct are handled, and [CONTRIBUTING.md](CONTRIBUTING.md) is the one
command to verify a change.

## Start a book

```sh
pip install -e .          # from a clone of this repo
press --version           # confirm the install; press --help lists commands
press new my-book         # scaffold a new book repository
cd my-book && git init && make all
```

Everything the pipeline knows about a book comes from the book's own
`config/` (see CLAUDE.md for the full contract). The scaffolded workflow
calls this repo's reusable build at a pinned tag, which pulls a public,
versioned toolchain image; a book under any account builds with no
package grant and no configured secret. The pipeline pins the image so
every build runs against the exact toolchain bytes the release was proven
on.

## Targets

- Building: `pdf epub html markdown site txt docx pages source all` --
  `press all` runs the full gauntlet: editorial checks (including
  proving the checkers can fail), every format, source archive, Pages
  assembly, then structural verification of every artifact.
- Checking: `check style verify verify-formats verify-pages` --
  `check` is the editorial law (source checks, checker self-test,
  style audit, jargon lint, registrations arithmetic, orphaned
  plates); the verify targets rebuild before verifying so a stale
  artifact can never be blessed, and `verify-pages` crawls the public
  site: every local reference must resolve, every declared download
  must exist and be linked, and the book's sentinels must appear on
  the public reading surface.
- Print pack: `print verify-print coverwrap publish isbn` -- a twoside
  interior with mirrored margins and black ink (verified from the
  rendered pages), a cover wrap whose spine width is computed from the
  interior and paper stock with a validated EAN-13 barcode,
  `press publish kdp|ingram` channel checklists, and `press isbn assign`
  to mint ISBNs from a registrant prefix you own.
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
  sci-fi paperback"), which every art commission then applies. For
  the web surfaces the stylesheet itself is the book's to own:
  `assets/web/reader.css` replaces the house reader sheet entirely,
  and `assets/web/extra.css` appends declarations that win the
  cascade on both the reader and the landing page.
- Instruments: `skills workflows desk` -- the packaged authoring skills
  and agent workflows (with installed paths, paste-ready invocations,
  and pinned-copy drift detection inside a book), and `press desk`, the
  optional operator desk: a terminal interface over these same targets
  that reads facts from the registries and runs every action as a
  `press` child (`pip install 'press[tui]'`).
- Utilities: `render wordcount clean new config selftest doctor` --
  `press config get|set|unset|list|validate` reads and writes every book
  configuration field, validating each value before it writes;
  `press doctor` examines every external dependency and says what
  works, what is missing, and what each absence costs; `press selftest`
  is the press checking itself: module imports, check-digit arithmetic,
  and that this README and the CLI usage stay honest about every
  target.
