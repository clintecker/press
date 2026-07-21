---
name: registrations
version: 1.0.0
description: The book paperwork, end to end - buying ISBNs, the LCCN PCN program, ISSN for serials, CIP data - and how each number flows through the press config into the colophon, EPUB metadata, and the cover barcode.
compatibility: any-agent
---

# Registrations

## Purpose

The numbers that make a book a citable, orderable object are cheap to
get and expensive to get wrong. This skill documents each process so an
agent can walk an author through it with current steps, and documents
where each number lives in a press book so it is stated exactly once.

## Where the numbers live

All of them in `config/metadata.yaml`, under `registrations:`. The
press validates check digits on every `press check`, injects the
numbers into the colophon and the EPUB package metadata, and draws the
print ISBN as the wrap barcode. Write `pending` for a number you have
applied for but not received; it renders as `[pending]` and blocks a
`retail: true` edition until the real number lands. Never type a number
anywhere else; the config is the single stated copy.

## ISBN (every trade book)

- Buy from the national agency; in the United States that is Bowker
  (myidentifiers.com). Buy the 10-pack; single ISBNs are priced as a
  penalty for not planning, and every format needs its own number.
- One ISBN per format: the print edition and the EPUB edition are
  different products. The press keeps them under `isbn: {print, epub}`.
- After the one-time purchase you assign numbers from your own prefix
  offline — there is no issuance API. Record the prefix as
  `registrations.isbn-block: {prefix, size}` and let `press isbn assign
  print|epub` mint the next unused number (check digit computed); `press
  isbn status` shows the block's usage.
- Do not use a free channel-assigned ISBN (KDP will offer one); it
  names the channel as publisher and cannot follow the book to another
  printer.
- The check digit is arithmetic, and the press verifies it. If `press
  check` refuses a number you were issued, the number was transcribed
  wrong; recheck the invoice, not the code.
- After assignment, register the title's metadata at the agency; a
  bare ISBN with no title record helps nobody order the book.

## LCCN (US books expecting library shelves)

- The Preassigned Control Number (PCN) program at the Library of
  Congress issues LCCNs before publication, free, via loc.gov/publish/pcn.
  The publisher (not the author) applies once for an account, then per
  title.
- Apply before the book is printed; the LCCN belongs on the copyright
  page, and the press renders it in the colophon from config.
- After publication, send the Library its complimentary copy; the PCN
  obligation is real.

## ISSN (serials only)

- Only for a continuing series under one title (a journal, an annual).
  A trilogy is not a serial.
- In the US, the ISSN National Center at the Library of Congress
  issues them free (loc.gov/issn). The press validates the mod-11
  check digit, X included.

## CIP data blocks

- Full CIP (Cataloging in Publication) is limited to publishers in the
  program; small presses generally use P-CIP: a cataloging block
  prepared by a librarian or service, printed on the copyright page.
- If the book carries one, it is prose on the copyright page, not
  config; keep it in `tex/title-page.tex` or the book's front matter
  overrides, because its layout is fixed by cataloging convention.

## Order of operations for a first book

1. Buy ISBNs (both formats) as soon as the title settles.
2. Apply for the LCCN when the manuscript is complete enough to name.
3. Enter both under `registrations:` as they arrive, replacing
   `pending`.
4. Set `retail: true` when preparing the retail release; `press check`
   then refuses to pass while anything is still pending.
5. The colophon, EPUB, barcode, and channel checklists update
   themselves from config on the next build.
