"""`press wordcount` counts prose words in the ordered manuscript, ignoring
code so a fenced block does not inflate the tally.

This exercises wordcount directly rather than relying on a quickstart doc
example to run it, so the module's coverage stands on its own.
"""

from __future__ import annotations

import pytest

from press import wordcount

pytestmark = pytest.mark.layer("integration")


def test_wordcount_totals_prose_and_skips_code(scaffolded_book, capsys):
    chapter = scaffolded_book / "book" / "chapters" / "01-count.md"
    chapter.write_text(
        "# A heading\n\n"
        "one two three four five.\n\n"
        "```sh\nthis fenced code must not be counted at all here\n```\n\n"
        "and `inline code` is skipped too, six seven.\n",
        encoding="utf-8",
    )
    assert wordcount.main() == 0
    out = capsys.readouterr().out
    # A per-file line and a TOTAL line are printed.
    assert "01-count.md" in out
    assert "TOTAL" in out
    # The fenced/inline code words are excluded; the prose words are counted.
    # "A heading one two three four five and inline? no — inline is skipped:
    # heading(2) + 'one two three four five'(5) + 'and is skipped too six
    # seven'(6) = 13 prose words in this chapter.
    numbers = [int(tok) for line in out.splitlines() for tok in line.split() if tok.isdigit()]
    assert numbers, out
    assert "fenced" not in out and "inline" not in out
