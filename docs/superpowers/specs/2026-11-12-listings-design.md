# Listings (Round 1D, v4): design

Date: 2026-11-12. Owner's choice from four rendered candidates: B, hairlines
above and below. Closes press #293 (example captions) and gives the house a
listing design, which the PDF never had (an untagged fence was bare verbatim
and a caption was an author's bold paragraph).

## What the reader sees

In the PDF, every code block (tagged or not) is set at `\small` between two
hairline rules the full width of the measure, with 9 pt plus 2 pt of space
above the block and below it, and 4 pt between each rule and the code. A
block that is also an example carries its caption directly above the top
rule in the house caption form, bold "Example C.N." followed by the title in
italic, flush left, with 3 pt between the caption and the rule, a keep so
the caption never strands (`\Needspace` for caption plus two lines) and
`\nopagebreak` after the caption. A long block may still break across
pages; the rules close and reopen at the break (fvextra's frame handles it,
or the design accepts a rule only at the true top and bottom; the
implementer chooses and documents). Nothing changes inside the block: the
0.86 code face, breaklines, the house hyphenation rules.

In HTML, the reader site, and the EPUB, a caption is a paragraph with class
`example-caption` set in the caption style (bold number, italic title,
small, above the block); the existing `pre` panel stays.

In DOCX and plain text, the caption is an ordinary paragraph in the
`Caption` style where pandoc has one, plain otherwise.

## How an author writes one

Two spellings, both recognised by a Lua filter:

1. The implicit form the book already uses: a paragraph whose only content
   is `**Example C.N. Title**` (or `**Example N. Title**`) immediately
   followed by a code block. The filter turns the paragraph into the
   caption and attaches it to the block.
2. The explicit form: a fence attribute `caption="Installing the toolchain
   on macOS"` with an optional `id`; the number is authored in the caption
   text as the house numbers tables today (no automatic numbering in this
   round).

A bold paragraph before anything other than a code block is left alone.

## Verification

- Filter tests: both spellings, in latex and html output; a bold paragraph
  not followed by a fence is untouched; a book with no fences is
  byte-identical filtered and unfiltered.
- A PDF-family test: a caption near a page foot stays with its listing
  (pdftotext page split), and a long listing across a page break builds.
- The fence pixel-identity test from #279 is re-based: it compared against
  kernel verbatim; the rules are a design change, so the test now proves
  the inside of the block (the code lines' positions relative to the first
  line) is unchanged while the frame is new.
- Acceptance on *Publishing with Press*: all 113 example captions attach
  (count `example-caption` in the reader site), no caption strands at a
  page foot (scan with pdftotext as the typesetter audit did), Example 2.4
  on folio 28 rendered and looked at.

## Docs and contract

docs/BOOK-PARTS.md (or the authoring doc that covers code) gains "Examples
and listings"; CHANGELOG [Unreleased] v4 entry; MIGRATION.md's v4 section
names the listing rules (every code block changes appearance; page breaks
move). Round 1B's docx task list is unaffected.
