# press

The 2389 Research Press pipeline: everything required to turn a directory
of Markdown chapters into a verified 6 x 9 print PDF, EPUB, single-file
HTML, per-chapter reader site, stitched Markdown, plain text, DOCX, a
GitHub Pages site with public downloads, and gated GitHub releases.

Extracted from the production of *Mostly Done.* so the next book inherits
the pipeline, the design, the editorial enforcement, and the scars.

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

`press all` runs the full gauntlet: editorial checks (including proving the
checkers can fail), every format, source archive, Pages assembly, then
structural verification of the PDF (trim, fonts, sentinels, ink on every
page, plate-link destinations) and of every other format. Individual
targets: `pdf epub html markdown site txt docx pages source check style
verify verify-formats render wordcount clean`.
