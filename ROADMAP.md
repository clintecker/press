# Roadmap: press as the whole publisher

The idea, stated once: a book repository holds the manuscript, its config,
and its art, and nothing else. The press holds everything a publisher
holds: the build and verification machinery, the editorial law, the agent
skills and workflows that compose, refine, and source prose, the art
direction that briefs image models, the front matter, and the preparation
for real publication (retail channels, print on demand, registrations).
Someone who "gets" press should be able to run `press new`, write
chapters, and end with every artifact a publisher needs: EPUB, HTML,
website, print-ready interior and cover wrap, and a checklist of the
paperwork, without the book repo growing any machinery of its own.

The press already practices its laws (facts stated once, generators over
checkers over conventions, artifacts verified as objects, scars become
law). Every milestone below extends those laws to a new territory.

## Where press is today (v1.0.x)

Works: all eight artifact builds; editorial law (`press check`) with
self-tested checkers; structural verification of every format; subject
index and table-of-authorities generators with orphan enforcement; the
sources companion document; `press new` scaffold; CI via composite action
plus reusable workflow and prebuilt toolchain image; private-to-private
consumption with per-repo package grants; two agent workflows
(editorial-passes, authorities-research) shipped as package data and
scaffolded into books.

Leaks the milestones must fix: skills and workflows resolve from a press
checkout path on disk, not from the installed package; art prompts were
hand-written per book; the treatise title page and colophon are
hand-authored TeX per book despite being derivable from metadata; nothing
exists between "verified PDF" and "book on sale."

## M1: self-contained press

No step may depend on a press checkout existing on disk.

- Package `skills/` into `press.data` (they are authoring instruments, not
  repo docs). `press skills` lists them with absolute installed paths;
  workflows resolve skills from the package first, checkout second.
- Scaffold a book CLAUDE.md from the template: what this repo is, the
  press commands, the available workflows and their exact invocations
  (root and press args), where the skills live, the house laws. This is
  how an agent opening any press book knows the whole system.
- `press workflows` prints each packaged workflow with its Workflow-tool
  invocation, ready to paste.
- Add epubcheck to the toolchain image and `verify_formats`; retail
  channels reject invalid EPUBs, so the press must reject them first.

## M2: the art department

Press holds the prompts; the book holds only the accepted images.

- `art-direction` workflow: reads the manuscript and metadata, applies the
  design skills (cover-design, plates-and-woodcuts, press-logomark), and
  writes `art/commissions.md`: finished, paste-ready prompts for an image
  model, covering cover, interior plates keyed to chapters, logomark, and
  author portrait, with every visible word named verbatim per the skill.
- `press art accept <file> --as cover|plate:<name>|logomark`: intake that
  converts to house format (JPEG q88 for grain, PNG for line art),
  enforces the geometry scars (text-block height cap, trim aspect),
  places the file, and updates the commission record to describe the
  accepted image so it can be reproofed if lost.
- Plate placement stays manual or agent-driven (captions are prose), but
  `press check` learns to flag images on disk that no chapter references.

## M3: front matter from metadata

The treatise title page, colophon, and epigraph become a generator.

- A press-data TeX template renders the stacked Victorian title page from
  title, subtitle (split on its OR clauses), author, place, and year; the
  colophon from copyright, imprint, contact, registration numbers, and an
  optional rights-notice and motto in config. A book may still supply
  tex/title-page.tex to override entirely.
- Activation is the presence of `config/front-matter.yaml` (which also
  holds the epigraph: quote, attribution). The scaffold includes the
  file, so new books get generated front matter by supplying nothing
  else; pinned books keep their rendered output, as the contract
  requires, until they add the file.
- The imprint device and cover plate slot in automatically when the assets
  exist (both already optional in the pipeline).

## M4: the print pack

From "verified PDF" to "uploadable to KDP and IngramSpark."

- A `print` build profile: twoside class options, mirrored inner/outer
  margins with a gutter, black links (no colored ink in print), optional
  higher-resolution image pass. `press print` builds
  `dist/<slug>-interior.pdf`; `verify_pdf` learns per-profile checks
  (mirrored margins, no color annotations).
- Cover wrap generator: `press coverwrap` computes spine width from page
  count and configured paper stock, lays front cover art, spine (title,
  author, imprint), and back cover (blurb from metadata description, the
  imprint device, ISBN barcode) into a single trim+bleed PDF sized to the
  channel's template. Spine math is a generator, never a hand-entered
  number.
- EAN-13 barcode generated from the ISBN (with optional price add-on).
- Channel checklists: `press publish kdp` / `press publish ingram` emit a
  checklist document of exactly what that channel needs (file specs,
  marketing image sizes, category and keyword slots, description HTML),
  with the items the press already produced checked off and file paths
  attached.

## M5: registrations

The paperwork becomes config plus a skill, not tribal knowledge.

- `config/metadata.yaml` gains a registrations block: isbn (per format:
  print, epub), issn for serials, lccn. The press validates ISBN check
  digits, injects the numbers into the colophon, EPUB metadata, and the
  barcode, and refuses a release tagged as a retail edition while a
  registration placeholder remains.
- A `registrations` skill documents the actual processes end to end:
  buying ISBNs (Bowker), the LCCN PCN program, ISSN applications, CIP
  data blocks, so an agent can walk the author through each with current
  steps rather than reinventing them per book.
- Placeholders stay honest: `[ISBN pending]` renders until the real
  number lands in config, exactly as today.

## M6: the operator

The whole publisher behind one installed command, no session required.
`press new` already initializes; the builds already produce; the gap is
that the agent machinery (editorial passes, authorities research) runs
only inside a live Claude Code session hosting the Workflow tool.

- `press improve` and `press research` drive the packaged workflows
  headlessly through the Claude Code CLI or Agent SDK, so "process this
  directory for prose quality" and "research the claims and build the
  bibliography" are shell commands, not session rituals.
- A report mode for the editorial machine: suggestions gathered and
  written to `build/editorial-report.md` (what to add, cut, soften,
  strengthen, revoice) without applying them, for the author who wants
  the counsel but not the hand on the manuscript.
- `press publish <channel>` stays a checklist generator (M4); the
  self-service platforms have no upload APIs worth trusting, so the
  press prepares everything and the author clicks.

## M7: the catalog (later)

One press site listing every book with covers and download links, built
from the books' own metadata. Optional; single-book Pages sites already
work.

## Untangling notes (current entanglements to dissolve)

- Done on main (ships as v1.1.0): skills are package data under
  `src/press/data/skills/` and workflows resolve them through
  `press skills` before any checkout fallback.
- Done on main: books' `.claude/workflows/` are copies from press data
  (books pin behavior); `press new` stamps the press version into them so
  drift is visible.
- The local build venv for make-ready lives in a session scratchpad and
  points at the press checkout via editable install; a plain
  `pip install -e ~/code/press` in any environment replaces it.
- Mostly Done. runs its own frozen pre-press pipeline by design (shipped
  at v1.0.x, org-owned while press is personal); it stays frozen unless a
  second edition forces the ownership question.

## Sequencing

M1 and M3 are small and unlock the "content-only book" promise; do them
first. M2 is a workflow plus an intake command. M4 is the largest (new
TeX profile, spine math, barcode, wrap layout) and should land behind its
own verify gates. M5 is mostly config plumbing plus one skill. M6 rides
on M1's packaged workflows and can land any time after them. Each
milestone ships as a minor tag; anything that changes a pinned book's
rendered output waits for v2.
