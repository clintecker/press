"""Real-tool integration runner: the PDF reading edition.

Builds a source-only factory book to ``dist/<slug>.pdf`` with the actual
pandoc -> LuaLaTeX -> latexmk toolchain, then inspects it with the real
``verify_pdf`` verifier (Poppler's pdfinfo/pdffonts/pdftotext/pdftoppm).
No fake process, no mock verifier, no network. When any tool is absent
the runner skips naming the toolchain capability, so a missing tool is
never read as an artifact failure. The cover-wrap runner proves the
print-profile interior, so it is not rebuilt here.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from tests import factories
from tests.integration._harness import (
    PDF_TOOLCHAIN,
    Evidence,
    digest_outputs,
    missing_tools,
    skip_reason,
    source_manifest_digest,
    tool_versions,
)
from tests.test_table_shapes_filter import GRID, LEDGER

REQUIRED = PDF_TOOLCHAIN
requires_pdf_toolchain = pytest.mark.skipif(
    bool(missing_tools(REQUIRED)), reason=skip_reason(REQUIRED)
)


def _book(root):
    return (
        factories.BookFactory(slug="int-pdf")
        .with_sentinels(
            "first witness of the pdf runner",
            "second witness of the pdf runner",
        )
        .with_chapter(
            "00-intro.md",
            "# Intro\n\nHere the first witness of the pdf runner stands in a "
            "plain sentence long enough to survive typesetting.\n",
        )
        .with_chapter(
            "01-more.md",
            "# More\n\nHere the second witness of the pdf runner stands in "
            "another plain sentence long enough to survive typesetting.\n",
        )
        .build(root)
    )


@requires_pdf_toolchain
@pytest.mark.layer("integration")
@pytest.mark.invariant("INV-pdf-ink")
@pytest.mark.proof("positive")
def test_reading_pdf_carries_ink(tmp_path):
    from press import booklib, registry, verify_pdf

    handle = _book(tmp_path)
    evidence = Evidence(
        family="pdf",
        required_tools=REQUIRED,
        tool_versions=tool_versions(REQUIRED),
        input_manifest_digest=source_manifest_digest(handle.root),
    )
    with handle.use():
        slug = booklib.slug()
        dist = booklib.root() / "dist"
        registry.build("pdf")
        rc = verify_pdf.main([str(dist / f"{slug}.pdf")])
        evidence.record_verifier("verify_pdf.main")
        evidence.record_invariant("INV-pdf-ink")
        evidence.record_invariant("INV-pdf-detector")  # self_test_detector runs in main
        evidence.record_invariant("INV-format-witness")  # sentinels checked in the PDF
        evidence.outputs = digest_outputs(dist, [f"{slug}.pdf"])
    evidence.write(tmp_path)

    assert rc == 0, "verify_pdf refused the freshly built reading PDF"
    assert f"{slug}.pdf" in evidence.outputs, "no reading PDF was produced"
    assert all(evidence.tool_versions[tool] != "absent" for tool in REQUIRED), (
        "an unskipped PDF runner recorded a tool as absent"
    )
    assert "verify_pdf.main" in evidence.verifiers


# A two-column grid table (cells may hold blocks): a two-letter key, and an
# entry whose prose carries a definition list of its own.
NESTED_LEDGER = """\
+-----------+------------------------------------------------+
| Key       | Meaning                                        |
+===========+================================================+
| `id`      | The identifier of the row, which names it once |
|           | and for all across every edition of the book.  |
+-----------+------------------------------------------------+
| `opts`    | The options this entry accepts, set out as a   |
|           | list of their own beneath it.                  |
|           |                                                |
|           | inner                                          |
|           | :   the nested definition of one option        |
+-----------+------------------------------------------------+
"""

LONG_IDENTIFIER = "a-very-long-identifier-that-cannot-break-at-all-anywhere-in-sixty-chars"


def _book_with(root, chapter: str):
    return (
        factories.BookFactory(slug="int-pdf-tables")
        .with_sentinels("witness of the table runner")
        .with_chapter(
            "00-tables.md",
            chapter.replace(
                "# Ch\n\n",
                "# Tables\n\nHere the witness of the table runner stands in a plain "
                "sentence long enough to survive typesetting.\n\n",
                1,
            ),
        )
        .build(root)
    )


# Plain justified prose, enough for several full pages after a table.
_PROSE = "\n\n".join(
    "The house sets a plain paragraph here so that the measure of the page is "
    "calibrated on justified text rather than on the table it follows. " * 6
    for _ in range(24)
)


@requires_pdf_toolchain
@pytest.mark.layer("integration")
@pytest.mark.proof("positive")
def test_a_ledger_table_sets_in_the_pdf_without_a_longtable(tmp_path):
    from press import booklib, build

    # LEDGER, then a grid-table ledger whose two-letter key must still take a
    # line of its own and whose second entry holds a definition list of its
    # own (a nested list once sent LuaLaTeX into an endless \item loop).
    handle = _book_with(tmp_path, LEDGER + "\n" + NESTED_LEDGER)
    with handle.use():
        root = booklib.root()
        # A subprocess with a deadline, so a TeX loop fails the test, not hangs it.
        subprocess.run([sys.executable, "-m", "press", "pdf"], cwd=root, check=True, timeout=600)
        # The .tex pandoc hands LuaLaTeX, written through the same defaults.
        build.pandoc_build("pdf", "build/ledger-check.tex")
        tex = (root / "build" / "ledger-check.tex").read_text(encoding="utf-8")
        pdf = root / "dist" / f"{booklib.slug()}.pdf"
        text = subprocess.run(
            ["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True
        ).stdout

    assert "\\begin{PressLedger}" in tex and "\\end{PressLedger}" in tex
    assert "longtable" not in tex, "a ledger table still reached LaTeX as a longtable"
    assert "\\PressLedgerCaption{Table 15.5. The skills that come with press}" in tex
    assert "\\PressLedgerLegend{Skill" in tex and "\\PressLedgerLegend{Key" in tex
    lines = [line.strip() for line in text.splitlines()]
    assert "hemingway" in lines and "humanizer" in lines
    # The manpage form for every key: even `id` stands alone on its line.
    assert "id" in lines, "a short key ran into its prose"
    assert any(line.startswith("The identifier of the row") for line in lines)
    assert "inner" in lines and any("nested definition" in line for line in lines)


@requires_pdf_toolchain
@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_a_grid_with_a_long_identifier_ends_within_the_body_measure(tmp_path):
    from press import booklib, registry, verify_pdf

    # One cell holds an identifier wider than any column it could get; another
    # holds a hyphenated flag that fits, beside prose that must wrap. Pages of
    # plain prose follow, so the body measure is calibrated on justified text.
    grid = GRID.replace("| pocket | 5 x 8 |", f"| pocket | `{LONG_IDENTIFIER}` |").replace(
        "| 0.78in |", "| `--foil-bright` sets the foil on every cover the house prints |"
    )
    handle = _book_with(tmp_path, grid + "\n" + _PROSE)
    with handle.use():
        pdf = booklib.root() / "dist" / f"{booklib.slug()}.pdf"
        registry.build("pdf")
        # -layout keeps a line-end hyphen; plain pdftotext would drop it.
        text = subprocess.run(
            ["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True
        ).stdout
        pages = text.split("\f")
        index = next(i for i, page in enumerate(pages) if "pocket" in page)
        out = tmp_path / "render"
        out.mkdir()
        subprocess.run(["pdftoppm", "-png", "-r", "120", str(pdf), str(out / "page")], check=True)
        images = sorted(out.glob("page*.png"))
        start = verify_pdf.first_body_index(pdf)
        measure = verify_pdf.text_block_right(images, "reading", start)[0]
        edges = {
            page: right
            for page, _cls, right in verify_pdf._block_right_edges(images, "reading", start)
        }

    lines = [line.strip() for line in pages[index].splitlines()]
    assert any("--foil-bright" in line for line in lines), "a flag that fits was split"
    # The too-wide identifier may break only after a hyphen it already has:
    # its pieces, rejoined across line ends, read exactly, no hyphen invented.
    # (-layout interleaves the neighbouring column, so pick the pieces out.)
    pieces = [w for w in pages[index].split() if "-" in w and w in LONG_IDENTIFIER]
    assert "".join(pieces) == LONG_IDENTIFIER, f"the identifier was mangled: {pieces}"
    # The median is only a measure when prose pages outnumber the grid page.
    assert len(edges) >= 3, f"too few body pages to calibrate the measure: {sorted(edges)}"
    assert index + 1 in edges, "the grid page rendered blank or fell in the front matter"
    overrun = edges[index + 1] - measure
    assert overrun <= verify_pdf.TEXT_BLOCK_SLACK, (
        f"grid ink ends at x={edges[index + 1]}, {overrun} px past the body measure {measure}"
    )
