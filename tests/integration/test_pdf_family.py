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

import re
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from tests import factories
from tests.integration._harness import (
    PDF_TOOLCHAIN,
    Evidence,
    digest_outputs,
    make_plate,
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
    assert "\\begin{longtable}" not in tex, "a ledger table still reached LaTeX as a longtable"
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
    from press import booklib, registry
    from press import verify_text_block as text_block

    # One cell holds an identifier wider than any column it could get; another
    # holds a hyphenated flag that fits, beside prose that must wrap. Pages of
    # plain prose follow, ending on the measure the grid must respect.
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
        overruns = dict(
            text_block.text_block_overruns(images, "reading", text_block.first_body_index(pdf))
        )

    lines = [line.strip() for line in pages[index].splitlines()]
    assert any("--foil-bright" in line for line in lines), "a flag that fits was split"
    # The too-wide identifier may break only after a hyphen it already has:
    # its pieces, rejoined across line ends, read exactly, no hyphen invented.
    # (-layout interleaves the neighbouring column, so pick the pieces out.)
    pieces = [w for w in pages[index].split() if "-" in w and w in LONG_IDENTIFIER]
    assert "".join(pieces) == LONG_IDENTIFIER, f"the identifier was mangled: {pieces}"
    # The measure is the profile's geometry; the grid page ends within the
    # protrusion slack of it, as the prose pages after it do.
    assert index + 1 in overruns, "the grid page rendered blank or fell in the front matter"
    assert overruns[index + 1] <= text_block.TEXT_BLOCK_SLACK, (
        f"grid ink runs {overruns[index + 1]} px past the text block"
    )
    assert max(overruns.values()) <= text_block.TEXT_BLOCK_SLACK, overruns


# One ordinary paragraph long enough to wrap, led by a word that appears
# nowhere else in the book so its first line can be found by text.
_FOLLOWING = (
    "Afterplate the paragraph that follows the frontispiece runs on long enough "
    "to break across several lines of the measure, so that its first line and "
    "its second line can be told apart by where each begins on the page, and "
    "the house indent, if it survived the caption, shows as the difference "
    "between them.\n"
)


def _frontispiece_book(root):
    handle = (
        factories.BookFactory(slug="int-frontis")
        .with_sentinels("witness of the frontispiece runner")
        .with_chapter(
            "00-intro.md",
            "# Intro\n\nHere the witness of the frontispiece runner stands in a "
            "plain sentence long enough to survive typesetting.\n\n"
            "![The plate.](assets/fig/plate.png){.figure place=frontispiece "
            'fig-alt="A dark oval inside a ruled border"}\n\n' + _FOLLOWING,
        )
        .build(root)
    )
    make_plate(handle.root / "assets" / "fig" / "plate.png")
    return handle


def _first_two_line_starts(pdf, lead: str) -> tuple[float, float]:
    """The x of the first word on the first and second lines of the
    paragraph whose first word is *lead*, from Poppler's layout boxes."""

    xml = subprocess.run(
        ["pdftotext", "-bbox-layout", str(pdf), "-"], capture_output=True, text=True, check=True
    ).stdout
    blocks = re.findall(r"<block[^>]*>(.*?)</block>", xml, re.S)
    for block in blocks:
        lines = re.findall(r"<line[^>]*>(.*?)</line>", block, re.S)
        starts = []
        for line in lines:
            m = re.search(r'<word xMin="([\d.]+)"[^>]*>([^<]*)</word>', line)
            if m:
                starts.append((float(m.group(1)), m.group(2)))
        if len(starts) >= 2 and starts[0][1] == lead:
            return starts[0][0], starts[1][0]
    raise AssertionError(f"no wrapped paragraph begins with {lead!r}")


@requires_pdf_toolchain
@pytest.mark.layer("integration")
def test_the_paragraph_after_a_frontispiece_keeps_its_indent(tmp_path):
    # \captionof sets \noindent and \sloppy and, as a command, leaves them
    # set; emitted bare, one frontispiece killed the 1.1em house indent on
    # every page after it (#292). The caption now sits in its own group, so the
    # first paragraph on the page after the plate still begins a house indent
    # (about 1.1em, so well over 6pt) to the right of its own second line.
    from press import booklib, registry

    handle = _frontispiece_book(tmp_path)
    with handle.use():
        registry.build("pdf")
        pdf = booklib.root() / "dist" / f"{booklib.slug()}.pdf"
        first, second = _first_two_line_starts(pdf, "Afterplate")

    assert first - second > 6, (
        f"the paragraph after the frontispiece lost its indent: first line at "
        f"x={first}, second at x={second}"
    )


# A grid-table ledger whose entry holds a bullet list of its own.
_LEDGER_WITH_BULLETS = """\
+-----------+------------------------------------------------+
| Key       | Meaning                                        |
+===========+================================================+
| `opts`    | The options this entry accepts, set out as a   |
|           | list of their own beneath it, one per line.    |
|           |                                                |
|           | - Bulletword names the first option            |
+-----------+------------------------------------------------+
"""


@requires_pdf_toolchain
@pytest.mark.layer("integration")
def test_a_list_nested_in_a_ledger_entry_keeps_the_house_label_gap(tmp_path):
    # The ledger's description sets labelsep=1.6em for its hang, and a list
    # nested in an entry inherited it: a bullet sat 1.6em from its text. The
    # house itemize and enumerate state the class's own label gap (about
    # 0.5em), so the nested bullet sits as close as any other.
    from press import booklib, registry

    handle = _book_with(tmp_path, _LEDGER_WITH_BULLETS)
    with handle.use():
        registry.build("pdf")
        pdf = booklib.root() / "dist" / f"{booklib.slug()}.pdf"
        xml = subprocess.run(
            ["pdftotext", "-bbox-layout", str(pdf), "-"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    # (x0, y0, x1, word) for every word; Poppler may split a wide gap into
    # two lines, so the bullet is found by its baseline, not its line.
    words = [
        (float(x0), float(y0), float(x1), word)
        for x0, y0, x1, word in re.findall(
            r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)"[^>]*>([^<]*)</word>', xml
        )
    ]
    text = next(w for w in words if w[3] == "Bulletword")
    bullet = next(w for w in words if w[3] == "\u2022" and abs(w[1] - text[1]) < 3)
    gap = text[0] - bullet[2]
    # 1.6em at 10pt is 16pt; the house gap is 5pt.
    assert gap < 8, f"the nested bullet sits {gap:.1f}pt from its text"


def _wrapped(lead: str) -> str:
    """A paragraph led by *lead* (a word found nowhere else) long enough to
    wrap, so its first and second lines can be told apart."""

    return (
        f"{lead} the paragraph runs on long enough to break across several lines "
        "of the measure, so that its first line and its second line can be told "
        "apart by where each begins on the page, and the house indent, if the "
        "ledger caption above left it alive, shows as the difference.\n"
    )


def _line_starts(pdf, lead: str) -> tuple[float, float]:
    """The x of the line whose first word is *lead* and of the line after it,
    in Poppler's reading order across blocks (an indent-less paragraph merges
    into the block before it, which _first_two_line_starts would miss)."""

    xml = subprocess.run(
        ["pdftotext", "-bbox-layout", str(pdf), "-"], capture_output=True, text=True, check=True
    ).stdout
    starts = [
        (float(m.group(1)), m.group(2))
        for line in re.findall(r"<line[^>]*>(.*?)</line>", xml, re.S)
        if (m := re.search(r'<word xMin="([\d.]+)"[^>]*>([^<]*)</word>', line))
    ]
    for (x, word), (after, _next) in zip(starts, starts[1:]):
        if word == lead:
            return x, after
    raise AssertionError(f"no wrapped paragraph begins with {lead!r}")


@requires_pdf_toolchain
@pytest.mark.layer("integration")
def test_the_paragraphs_after_a_captioned_ledger_keep_their_indent(tmp_path):
    # \PressLedgerCaption ran \captionof* bare, which leaves \noindent and
    # \sloppy in force: every paragraph after the first captioned ledger lost
    # the 1.1em house indent for the rest of the book (the #292 class, found
    # on the v4 build of a real book). The caption is grouped now, so the
    # second paragraph after the ledger, and one pages later, each begin a
    # house indent (well over 6pt) right of their own second lines.
    from press import booklib, registry

    chapter = (
        LEDGER
        + "\n"
        + _wrapped("Firstafter")
        + "\n"
        + _wrapped("Afterledger")
        + "\n"
        + _PROSE
        + "\n\n"
        + _wrapped("Laterpage")
    )
    handle = _book_with(tmp_path, chapter)
    with handle.use():
        registry.build("pdf")
        pdf = booklib.root() / "dist" / f"{booklib.slug()}.pdf"
        pages = _pages(pdf)
        near = _line_starts(pdf, "Afterledger")
        later = _line_starts(pdf, "Laterpage")

    ledger_page = _first_page_with(pages, "humanizer")
    assert _first_page_with(pages, "Laterpage") > ledger_page, "the later paragraph is not later"
    for name, (first, second) in (("Afterledger", near), ("Laterpage", later)):
        assert first - second > 6, (
            f"{name}: the paragraph after a captioned ledger lost its indent: first "
            f"line at x={first}, second at x={second}"
        )


# Two 76-column lines, one in an untagged fence and one tagged ``text``:
# about twelve columns past the house measure (64 columns of Source Code Pro
# at 0.86 on the 6x9 trim), so neither fits without wrapping. The chapter
# carries no other code, so the only reason the PDF embeds the mono face is
# the fences themselves.
UNTAGGED_LINE = "# pinned for the print edition; see docs/PRINT-FORMATS.md for the rationales"
TEXT_LINE = "pip install --require-hashes --requirement requirements-lock.txt --no-deps ."
TRIM_WIDTH_IN, INNER_IN, OUTER_IN = 6.0, 0.78, 0.68  # book-header.tex geometry
RENDER_DPI = 120
# microtype hangs punctuation a hair past the text edge; a wrapped line never
# reaches further than this, an unwrapped 76-column line reaches the page edge.
PROTRUSION_PX = 6


def _code_book(root):
    return (
        factories.BookFactory(slug="int-code")
        .with_sentinels(
            "first witness of the code runner",
            "second witness of the code runner",
        )
        .with_chapter(
            "00-code.md",
            "# Code\n\nHere the first witness of the code runner stands in a "
            "plain sentence long enough to survive typesetting.\n\n"
            f"```\n{UNTAGGED_LINE}\n```\n\n"
            "A second block, tagged as plain text, follows.\n\n"
            f"```text\n{TEXT_LINE}\n```\n\n"
            "Here the second witness of the code runner stands in "
            "another plain sentence long enough to survive typesetting.\n",
        )
        .build(root)
    )


def _page_text(pdf, page: int) -> str:
    from press import verify_pdf

    return verify_pdf.run_capture(
        ["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(pdf), "-"]
    )


def _find_page(pdf, needle: str, page_count: int) -> int:
    for page in range(1, page_count + 1):
        if needle in _page_text(pdf, page):
            return page
    raise AssertionError(f"no page carries {needle!r}")


def _rightmost_ink_px(pdf, page: int, out_dir) -> int:
    from PIL import Image

    from press import verify_pdf

    verify_pdf.run_capture(
        [
            "pdftoppm",
            "-png",
            "-r",
            str(RENDER_DPI),
            "-f",
            str(page),
            "-l",
            str(page),
            str(pdf),
            str(out_dir / "p"),
        ]
    )
    (png,) = sorted(out_dir.glob("p*.png"))
    with Image.open(png) as image:
        bbox = verify_pdf.ink_bbox(image)
    assert bbox is not None, f"page {page} rendered with no ink"
    return bbox[2]


def _text_block_right_px(dpi: int = RENDER_DPI) -> int:
    # The reading edition is set ``oneside`` (pdf.yaml), so geometry's inner
    # margin is the left and the outer the right on every page; only the
    # print profile mirrors them.
    return round((TRIM_WIDTH_IN - OUTER_IN) * dpi)


@requires_pdf_toolchain
@pytest.mark.layer("integration")
@pytest.mark.invariant("INV-pdf-ink")
@pytest.mark.proof("positive")
def test_untagged_code_fence_wraps_inside_the_measure(tmp_path):
    """A fence with no language tag wraps like a tagged one (#279): no ink
    past the text block, every column of the line still in the text, and
    the block set in the house mono face."""

    from press import booklib, registry, verify_pdf

    assert len(UNTAGGED_LINE) == len(TEXT_LINE) == 76
    handle = _code_book(tmp_path)
    evidence = Evidence(
        family="pdf",
        required_tools=REQUIRED,
        tool_versions=tool_versions(REQUIRED),
        input_manifest_digest=source_manifest_digest(handle.root),
    )
    with handle.use():
        slug = booklib.slug()
        pdf = booklib.root() / "dist" / f"{slug}.pdf"
        registry.build("pdf")
        rc = verify_pdf.main([str(pdf)])
        evidence.record_verifier("verify_pdf.main")
        evidence.record_invariant("INV-pdf-ink")
        evidence.outputs = digest_outputs(pdf.parent, [pdf.name])
        pages = int(verify_pdf.run_capture(["pdfinfo", str(pdf)]).split("Pages:")[1].split()[0])
        page = _find_page(pdf, "pinned for the print edition", pages)
        page_text = _page_text(pdf, page)
        fonts = verify_pdf.run_capture(["pdffonts", str(pdf)])
        rightmost = _rightmost_ink_px(pdf, page, tmp_path)
    evidence.write(tmp_path)

    assert rc == 0, "verify_pdf refused the code-fence PDF"
    # The whole line survives, wrapped: compare with whitespace and the
    # continuation mark folded away, since a wrap breaks at a space.
    squashed = "".join(page_text.replace("↪", "").split())
    for line in (UNTAGGED_LINE, TEXT_LINE):
        assert "".join(line.split()) in squashed, f"a column of {line!r} ran off the page"
    limit = _text_block_right_px() + PROTRUSION_PX
    assert rightmost <= limit, (
        f"ink reaches {rightmost}px on page {page}; the text block ends at {limit}px "
        f"(page width {TRIM_WIDTH_IN * RENDER_DPI:.0f}px), so a code line overran the measure"
    )
    assert "SourceCodePro" in fonts, "the untagged fence was not set in Source Code Pro"


# --- The house listing: a new frame around an unchanged inside --------------
#
# v4 gives every code block the house listing design (#293): \small between
# two hairline rules. That is a design change, so the #279 pixel-identity
# proof against the kernel verbatim cannot hold any longer; what #279
# promised was that rebinding verbatim to fvextra moved nothing inside a
# block, and that promise is kept and proven here. One book renders twice:
# under the house header, and with the kernel verbatim restored at the same
# \small through the book's own tex/title-page.tex (the last include, so it
# wins). The code lines must sit at the same positions relative to the
# block's first line in both (the pitch, the indentation, the blank line),
# while the frame is new: a rule just above each block's first line and just
# below its last, and none at a page break inside a block. The control is
# live: on the last page it still lets the overlong line overrun.
KERNEL_VERBATIM_TEX = r"""
% Restore LaTeX's own verbatim, as the header left it before #279, at the
% listing's \small. These are the kernel's definitions (latex.ltx) with the
% size switch in front, so the control is what a bare verbatim of the same
% size would set: no frame, no fvextra.
\makeatletter
\renewcommand\verbatim{\small\@verbatim \frenchspacing\@vobeyspaces \@xverbatim}
\renewcommand\endverbatim{\if@newlist \leavevmode\fi\endtrivlist}
\makeatother
% And the 3em emergency stretch v3 set: under v4's 10em the kernel verbatim
% line finds a last-resort break at its own hyphen, and the control would no
% longer show the overrun the rebind exists to prevent.
\AtBeginDocument{\setlength{\emergencystretch}{3em}}
"""
FITTING_FENCE = (
    "alpha = 1\n"
    "beta = alpha + 2\n"
    "\n"
    "    gamma(beta)  # indented, with a blank line above\n"
    "delta = 'fits within sixty columns'\n"
)
# Longer than a page of lines, so a page foot falls inside the block and the
# page-break behaviour (club and widow penalties, the strut at a page head)
# is exercised, not just the pitch between lines.
SPANNING_FENCE = "".join(f"line {i:02d} of a block that crosses a page foot\n" for i in range(60))
IDENTITY_PROSE = (
    "The quick brown fox jumps over the lazy dog and keeps on running "
    "through the paragraph until it fills a few lines of the measure. "
) * 3
IDENTITY_DPI = 300


def _identity_book(root, title_tex: str):
    body = (
        "# Code\n\n"
        "Here the first witness of the code runner stands in a plain sentence.\n\n"
        f"{IDENTITY_PROSE}\n\n```\n{FITTING_FENCE}```\n\n"
        f"{IDENTITY_PROSE}\n\n```text\n{FITTING_FENCE}```\n\n"
        f"{IDENTITY_PROSE}\n\n"
        "Here the second witness of the code runner stands in a plain sentence.\n\n"
        + "\n\n".join([IDENTITY_PROSE] * 6)
        + f"\n\n```\n{SPANNING_FENCE}```\n\n{IDENTITY_PROSE}\n\n"
        # The one overlong line, last in the book: the only page allowed to
        # differ is the one it lands on.
        f"```\n{UNTAGGED_LINE}\n```\n"
    )
    return (
        factories.BookFactory(slug="int-fence")
        .with_sentinels(
            "first witness of the code runner",
            "second witness of the code runner",
        )
        .with_chapter("00-code.md", body)
        .with_title_tex(title_tex)
        .build(root)
    )


def _render_pages(root, title_tex: str):
    """Build the identity book under ``title_tex`` and rasterise every page."""

    from press import booklib, registry, verify_pdf

    handle = _identity_book(root, title_tex)
    with handle.use():
        registry.build("pdf")
        pdf = booklib.root() / "dist" / f"{booklib.slug()}.pdf"
        out = root / "png"
        out.mkdir()
        verify_pdf.run_capture(
            ["pdftoppm", "-png", "-r", str(IDENTITY_DPI), str(pdf), str(out / "p")]
        )
        digest = digest_outputs(pdf.parent, [pdf.name])
    return sorted(out.glob("p*.png")), digest


def _code_lines(pdf: Path) -> list[tuple[int, str, float, float, float]]:
    """Every code line of the identity book, in reading order, as
    (page, text, xMin, yMin, yMax) in PDF points from pdftotext's layout."""

    import xml.etree.ElementTree as ET

    out = subprocess.run(
        ["pdftotext", "-bbox-layout", str(pdf), "-"], capture_output=True, text=True, check=True
    ).stdout
    root = ET.fromstring(out)
    lines = []
    for number, page in enumerate(root.iter("{http://www.w3.org/1999/xhtml}page"), start=1):
        for line in page.iter("{http://www.w3.org/1999/xhtml}line"):
            words = [w.text or "" for w in line.iter("{http://www.w3.org/1999/xhtml}word")]
            text = " ".join(words)
            if re.match(r"(alpha =|beta =|gamma\(beta\)|delta =|line \d\d of a block)", text):
                lines.append(
                    (
                        number,
                        text,
                        float(line.get("xMin")),
                        float(line.get("yMin")),
                        float(line.get("yMax")),
                    )
                )
    return lines


def _blocks(lines):
    """The code lines split into their blocks (each starts at alpha or line 00)."""

    blocks: list[list] = []
    for entry in lines:
        if entry[1].startswith(("alpha =", "line 00 ")):
            blocks.append([])
        blocks[-1].append(entry)
    return blocks


def _rules_px(png: Path, dpi: int) -> list[float]:
    """The vertical centres (in points) of every hairline across the text
    block on a rendered page: a run of rows inked across nearly the whole
    measure, which no line of type ever is."""

    left = round(INNER_IN * dpi)
    right = round((TRIM_WIDTH_IN - OUTER_IN) * dpi)
    need = 0.97 * (right - left)
    with Image.open(png) as image:
        grey = image.convert("L")
        width, height = grey.size
        pixels = grey.load()
        rows = [
            y
            for y in range(height)
            if sum(1 for x in range(left, right) if pixels[x, y] < 160) >= need
        ]
    rules: list[list[int]] = []
    for y in rows:
        if rules and y - rules[-1][-1] <= 1:
            rules[-1].append(y)
        else:
            rules.append([y])
    return [(sum(r) / len(r) + 0.5) * 72 / dpi for r in rules]


@requires_pdf_toolchain
@pytest.mark.layer("integration")
@pytest.mark.invariant("INV-design-layout-stable")
@pytest.mark.proof("positive")
def test_listing_frame_is_new_and_the_inside_of_the_block_is_unchanged(tmp_path):
    """The house listing frames every block with a hairline above and below
    while the code inside sets exactly as a bare \\small verbatim would: the
    same line positions relative to the block's first line. A page break
    inside a block draws no rule, and the overlong line still wraps where the
    kernel control lets it overrun."""

    evidence = Evidence(
        family="pdf-listing-frame",
        required_tools=REQUIRED,
        tool_versions=tool_versions(REQUIRED),
    )
    house, house_digest = _render_pages(tmp_path / "house", "% house header, unmodified\n")
    kernel, kernel_digest = _render_pages(tmp_path / "kernel", KERNEL_VERBATIM_TEX)
    evidence.outputs = {"house": house_digest, "kernel": kernel_digest}
    evidence.record_invariant("INV-design-layout-stable")
    evidence.record_invariant("INV-pdf-ink")
    house_pdf = next((tmp_path / "house").rglob("dist/int-fence.pdf"))
    kernel_pdf = next((tmp_path / "kernel").rglob("dist/int-fence.pdf"))
    house_lines, kernel_lines = _code_lines(house_pdf), _code_lines(kernel_pdf)

    # The inside: the same code lines in the same order, and within every
    # block fragment that sits on one page in both renders, the same offsets
    # from the fragment's first line, across and down.
    assert [t for _, t, *_ in house_lines] == [t for _, t, *_ in kernel_lines], (
        "the house and the control set different code lines: a block was rebroken"
    )
    assert len(house_lines) == 2 * 4 + 60
    compared = 0
    for h_block, k_block in zip(_blocks(house_lines), _blocks(kernel_lines), strict=True):
        for i in range(1, len(h_block)):
            (hp0, _, _, hy0, _), (hp, text, hx, hy, _) = h_block[i - 1], h_block[i]
            (kp0, _, _, ky0, _), (kp, _, kx, ky, _) = k_block[i - 1], k_block[i]
            if hp0 != hp or kp0 != kp:
                continue  # a page break between these two lines in one render
            assert abs((hy - hy0) - (ky - ky0)) < 0.05, (
                f"{text!r} sits {hy - hy0:.2f}pt below the line above it in the house listing "
                f"and {ky - ky0:.2f}pt in the bare \\small verbatim: the frame moved the inside"
            )
            assert abs((hx - h_block[0][2]) - (kx - k_block[0][2])) < 0.05, (
                f"{text!r} moved across inside its block"
            )
            compared += 1
    evidence.notes["line_pairs_compared"] = str(compared)
    assert compared >= 60, f"only {compared} line pairs shared a page in both renders"

    # The frame: a rule within 8pt above each block's first line and below
    # its last, on the page each sits on; none below a fragment that a page
    # break ends, and none in the control around the bare verbatim.
    def rules_on(pngs, page):
        return _rules_px(pngs[page - 1], IDENTITY_DPI)

    for block in _blocks(house_lines):
        first, last = block[0], block[-1]
        above = [r for r in rules_on(house, first[0]) if first[3] - 8 < r < first[3]]
        below = [r for r in rules_on(house, last[0]) if last[4] < r < last[4] + 8]
        assert above, f"no hairline above the block opening {first[1]!r}"
        assert below, f"no hairline below the block closing {last[1]!r}"
        for prev, nxt in zip(block, block[1:]):
            if prev[0] != nxt[0]:
                stray = [r for r in rules_on(house, prev[0]) if prev[4] < r < prev[4] + 8]
                assert not stray, f"a rule closes the page under {prev[1]!r} mid-block"
    spanning = _blocks(kernel_lines)[-1]
    bare = [r for r in rules_on(kernel, spanning[0][0]) if spanning[0][3] - 8 < r < spanning[0][3]]
    assert not bare, "the control drew a rule: the kernel restore is dead"
    evidence.write(tmp_path)

    # The control is live and the fix bites: on the last page the kernel
    # verbatim ran the overlong line to the page edge, the rebind wraps it.
    from press import verify_pdf

    with Image.open(kernel[-1]) as image:
        kernel_right = verify_pdf.ink_bbox(image)[2]
    with Image.open(house[-1]) as image:
        house_right = verify_pdf.ink_bbox(image)[2]
    limit = _text_block_right_px(IDENTITY_DPI) + PROTRUSION_PX * IDENTITY_DPI // RENDER_DPI
    assert kernel_right > limit, "the kernel verbatim control did not overrun: the restore is dead"
    assert house_right <= limit, (
        f"the rebound verbatim still overruns ({house_right}px > {limit}px)"
    )


# --- An example caption never strands at a page foot (#293) ---------------
#
# The listings filter turns **Example C.N. Title** before a fence into
# \PressExampleCaption, which asks for room for itself, the rule, and two
# lines of code. The book below walks a captioned listing down the page one
# line at a time (each section adds a line of prose before it), so some
# caption lands at every height, including the last lines of a page. The
# control replaces the macro with a bare bold paragraph, the v3 rendering,
# and must strand at least once, or the book proves nothing.
BARE_CAPTION_TEX = r"""
\def\PressExampleCaption#1#2{\par\noindent\textbf{#1} \emph{#2}\par}
"""
CAPTION_FILLER = "This sentence is filler that walks the listing down the page by one line. "


def _caption_book(root, title_tex: str):
    parts = ["# Examples\n\nHere the witness of the caption runner stands in a plain sentence.\n"]
    for n in range(1, 31):
        prose = CAPTION_FILLER * (n % 9 + 1)
        code = "".join(f"listing {n:02d} code line {i}\n" for i in range(1, 5))
        parts.append(f"{prose}\n\n**Example 1.{n}. The listing numbered {n}**\n\n```\n{code}```\n")
    # One long captioned listing, longer than a page, so a break falls inside.
    long_code = "".join(f"listing 99 code line {i}\n" for i in range(1, 71))
    parts.append(f"**Example 1.99. A listing longer than a page**\n\n```\n{long_code}```\n")
    parts.append("The book ends here.\n")
    return (
        factories.BookFactory(slug="int-caption")
        .with_sentinels("witness of the caption runner")
        .with_chapter("00-examples.md", "\n".join(parts))
        .with_title_tex(title_tex)
        .build(root)
    )


def _stranded_captions(pages: list[str]) -> list[str]:
    """Captions that end a page while their listing begins on the next."""

    stranded = []
    for number, (page, nxt) in enumerate(zip(pages, pages[1:]), start=1):
        body = [ln.strip() for ln in page.splitlines() if ln.strip()]
        if body and re.fullmatch(r"\d+|[ivxlc]+", body[-1]):
            body = body[:-1]  # the folio
        if body and body[-1].startswith("Example 1."):
            following = [ln.strip() for ln in nxt.splitlines() if ln.strip()]
            if any(ln.startswith("listing ") for ln in following[:3]):
                stranded.append(f"page {number}: {body[-1]}")
    return stranded


@requires_pdf_toolchain
@pytest.mark.layer("integration")
@pytest.mark.invariant("INV-pdf-ink")
@pytest.mark.proof("positive")
def test_example_caption_stays_with_its_listing(tmp_path):
    from press import booklib, registry, verify_pdf

    results = {}
    for name, tex in (("house", "% house header, unmodified\n"), ("bare", BARE_CAPTION_TEX)):
        handle = _caption_book(tmp_path / name, tex)
        with handle.use():
            registry.build("pdf")
            pdf = booklib.root() / "dist" / f"{booklib.slug()}.pdf"
            rc = verify_pdf.main([str(pdf)]) if name == "house" else 0
            results[name] = (rc, _pages(pdf))
    rc, house_pages = results["house"]
    assert rc == 0, "verify_pdf refused the captioned-listing PDF"
    text = "\n".join(house_pages)
    # every caption and every code line made it, the long listing included,
    # and the long listing really crossed a page
    for n in range(1, 31):
        assert f"Example 1.{n}. The listing numbered {n}" in text
    assert all(f"listing 99 code line {i}" in text for i in range(1, 71))
    spans = [i for i, p in enumerate(house_pages) if "listing 99 code line" in p]
    assert len(spans) >= 2, "the long listing never crossed a page break"
    assert _stranded_captions(house_pages) == [], "a caption stranded at a page foot"
    assert _stranded_captions(results["bare"][1]), (
        "the bare-caption control never stranded a caption: the book does not reach the page foot"
    )


# ---- layout corrections (the v3 correction wave) ----------------------------
#
# These read the built PDF the way a proofreader does: page by page through
# Poppler's pdftotext, the running head at the top of a page and the folio at
# its foot. Each builds the smallest book that reproduces the fault its issue
# names, and asserts the corrected layout, not merely that a PDF came out.

_ROMAN = re.compile(r"^[ivxlc]+$")


def _plate(path: Path, *, size: tuple[int, int] = (600, 400)) -> None:
    """A small engraving-like plate: ink rules on a light ground, enough
    variation that no detector reads it as blank."""

    image = Image.new("L", size, 250)
    draw = ImageDraw.Draw(image)
    for i in range(0, size[1], 12):
        draw.line([(0, i), (size[0], i + size[1] // 3)], fill=40, width=3)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG")


def _pages(pdf: Path) -> list[str]:
    """Each page's text, in reading order (pdftotext -layout, split at the
    form feed it ends every page with)."""

    out = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True
    ).stdout
    pages = out.split("\f")
    return pages[:-1] if pages and not pages[-1].strip() else pages


def _lines(page: str) -> list[str]:
    return [line.strip() for line in page.splitlines() if line.strip()]


def _folio(page: str) -> str:
    """The folio is the last line of ink on a page (the house sets it centred
    in the foot on every page style)."""

    lines = _lines(page)
    return lines[-1] if lines else ""


def _first_page_with(pages: list[str], needle: str) -> int:
    return next(i for i, page in enumerate(pages) if needle in page)


def _build_pdf(handle, target: str = "pdf") -> Path:
    from press import booklib, registry

    with handle.use():
        registry.build(target)
        slug = booklib.slug()
        name = f"{slug}.pdf" if target == "pdf" else f"{slug}-interior.pdf"
        return booklib.root() / "dist" / name


def _lists_book(root):
    handle = (
        factories.BookFactory(slug="int-lists")
        .with_sentinels("the preface witness of the lists book")
        .with_chapter(
            "00-preface.md",
            "# Preface {.unnumbered}\n\nHere the preface witness of the lists book "
            "opens the book in a plain sentence.\n",
        )
        .with_chapter(
            "01-one.md",
            "# One\n\nA plain paragraph before the plate.\n\n"
            "![A woodcut plate](assets/woodcuts/plate.png)\n\n"
            "A paragraph between the plate and the figure.\n\n"
            "![A numbered figure](assets/figures/fig.png){#fig:one .figure}\n\n"
            "A closing paragraph after the figure.\n",
        )
        .build(root)
    )
    _plate(handle.root / "assets" / "woodcuts" / "plate.png")
    _plate(handle.root / "assets" / "figures" / "fig.png")
    return handle


@requires_pdf_toolchain
@pytest.mark.layer("integration")
def test_illustration_lists_sit_in_the_roman_front_matter(tmp_path):
    """#289: the List of Plates and the List of Figures are front matter. Both
    take roman folios, the arabic sequence starts at 1 on the Preface, and
    both headings share the case of "Contents"."""

    pages = _pages(_build_pdf(_lists_book(tmp_path)))
    plates = _first_page_with(pages, "List of Plates")
    figures = _first_page_with(pages, "List of Figures")
    preface = _first_page_with(pages, "the preface witness")
    assert _ROMAN.match(_folio(pages[plates])), _folio(pages[plates])
    assert _ROMAN.match(_folio(pages[figures])), _folio(pages[figures])
    assert plates < figures < preface
    assert _folio(pages[preface]) == "1"
    # every page before the Preface is roman (or unfolioed), none arabic
    assert not any(_folio(p).isdigit() for p in pages[:preface])
    assert not any("List of plates" in p for p in pages)


def _filler(words: str, paragraphs: int) -> str:
    """Enough plain prose to run a part over several pages."""

    sentence = (
        f"This paragraph about {words} runs on in plain words so that the part "
        "fills its page and turns over onto the next one, as a real part would. "
    )
    return "\n\n".join(sentence * 4 for _ in range(paragraphs)) + "\n"


@requires_pdf_toolchain
@pytest.mark.layer("integration")
def test_unnumbered_chapter_sets_its_own_running_head(tmp_path):
    """#282: an unnumbered chapter (here an appendix after Chapter 1) carries
    its own title in the running head, not the last numbered chapter's."""

    handle = (
        factories.BookFactory(slug="int-heads")
        .with_sentinels("the first witness of the heads book")
        .with_chapter(
            "01-one.md",
            "# The opening chapter\n\nHere the first witness of the heads book stands.\n\n"
            + _filler("the opening chapter", 12),
        )
        .with_appendix(
            "a-extra.md",
            "# Appendix A: Extra matter {.unnumbered}\n\n" + _filler("the appendix", 16),
        )
        .build(tmp_path)
    )
    pages = _pages(_build_pdf(handle))
    opening = _first_page_with(pages, "about the appendix")
    assert "Appendix A: Extra matter" in pages[opening]
    second = _lines(pages[opening + 1])
    assert "about the appendix" in pages[opening + 1]
    assert "Appendix A: Extra matter" in second[0], second[0]
    assert "The opening chapter" not in second[0], second[0]


@requires_pdf_toolchain
@pytest.mark.layer("integration")
def test_unnumbered_chapter_plate_lists_without_a_chapter_number(tmp_path):
    """#288: a plate in a colophon after Chapter 1 listed as "1.2", counted
    into the last numbered chapter. It lists by its caption alone, and the
    numbered chapter's plate keeps its number."""

    handle = (
        factories.BookFactory(slug="int-colophon")
        .with_sentinels("the witness of the colophon book")
        .with_chapter(
            "01-one.md",
            "# One\n\nHere the witness of the colophon book stands.\n\n"
            "![The chapter plate](assets/woodcuts/one.png)\n\nAfter the plate.\n",
        )
        .with_appendix(
            "z-colophon.md",
            "# Colophon {.unnumbered}\n\n![The colophon plate](assets/woodcuts/two.png)\n\n"
            "Set in a plain face.\n",
        )
        .build(tmp_path)
    )
    _plate(handle.root / "assets" / "woodcuts" / "one.png")
    _plate(handle.root / "assets" / "woodcuts" / "two.png")
    pages = _pages(_build_pdf(handle))
    plates = _lines(pages[_first_page_with(pages, "List of Plates")])
    chapter_line = next(line for line in plates if "The chapter plate" in line)
    colophon_line = next(line for line in plates if "The colophon plate" in line)
    assert chapter_line.startswith("1.1"), chapter_line
    assert colophon_line.startswith("The colophon plate"), colophon_line


def _page_of(pages: list[str], needle: str, start: int = 0) -> int:
    return next(i for i in range(start, len(pages)) if needle in pages[i])


_KEEPS = 45

# A definition list nested inside a definition: pandoc emits a description
# environment inside a description environment.
_NESTED_DEFINITIONS = (
    "\nouterterm\n:   The outer definition holds a list of its own.\n\n"
    "    innerterm\n    :   The inner definition of the nested list.\n"
)


@requires_pdf_toolchain
@pytest.mark.layer("integration")
def test_table_head_and_definition_term_keep_with_what_follows(tmp_path):
    """#286: a longtable head stranded at a page foot with its rows overleaf,
    and a definition term stranded with its definition overleaf. Forty-five
    tables and as many terms, each after a lead-in of varying length, walk
    the page foot through every offset; every table head shares its page
    with its first two rows, and every term with the first line under it.
    Under v4 a key-plus-prose table is a ledger: the even tables are forced
    to grids (longtables, the head kept with two rows), the odd ones stay
    ledgers (the caption and legend kept with the first entry)."""

    tables = []
    for k in range(_KEEPS):
        lead = "A lead-in line of plain prose before the table. " * (1 + k % 5)
        # wide rows: pandoc sets relative p-columns, so each row wraps to two
        # or three lines, the shape of a real reference table
        cell = "a cell long enough to wrap onto a second line in its column " * 2
        rows = "\n".join(f"| row{k}x{r} | {cell}|" for r in range(5))
        table = (
            f"| head{k}col | Meaning |\n|------------------|{'-' * 50}|\n"
            f"{rows}\n\nTable: Table {k}. A caption over the table\n"
        )
        if k % 2 == 0:
            table = f"::: {{.grid}}\n{table}:::\n"
        tables.append(f"{lead}\n\n{table}")
    terms = []
    for k in range(_KEEPS):
        lead = "A lead-in line of plain prose before the term. " * (1 + k % 4)
        terms.append(
            f"{lead}\n\nterm{k}word\n:   Press prints:\n\n    ```\n    code{k}first\n"
            f"    code{k}second\n    ```\n"
        )
    handle = (
        factories.BookFactory(slug="int-keeps")
        .with_sentinels("the witness of the keeps book")
        .with_chapter(
            "01-tables.md",
            "# Tables\n\nHere the witness of the keeps book stands.\n\n" + "\n".join(tables),
        )
        .with_chapter(
            "02-terms.md",
            "# Terms\n\nTerms follow.\n\n" + "\n".join(terms) + _NESTED_DEFINITIONS,
        )
        .build(tmp_path)
    )
    with handle.use():
        from press import booklib

        root = booklib.root()
        # A subprocess with a deadline, so a TeX loop (a nested description
        # list once made \item call itself forever) fails the test, not hangs it.
        subprocess.run([sys.executable, "-m", "press", "pdf"], cwd=root, check=True, timeout=600)
        pages = _pages(root / "dist" / f"{booklib.slug()}.pdf")
    assert "inner definition of the nested list" in "".join(pages)
    body = _page_of(pages, "Here the witness")
    stranded = [
        k
        for k in range(_KEEPS)
        if len(
            {
                _page_of(pages, f"Table {k}. A caption", body),
                _page_of(pages, f"head{k}col", body),
                _page_of(pages, f"row{k}x{1 if k % 2 == 0 else 0}", body),
            }
        )
        != 1
    ]
    assert not stranded, f"table heads stranded from their first rows: {stranded}"
    terms_at = _page_of(pages, "Terms follow.", body)
    split = [
        k
        for k in range(_KEEPS)
        if _page_of(pages, f"term{k}word", terms_at) != _page_of(pages, f"code{k}first", terms_at)
    ]
    assert not split, f"definition terms stranded from their definition: {split}"


_CODE_PARAS = 54


@requires_pdf_toolchain
@pytest.mark.layer("integration")
def test_code_spans_never_hyphenate(tmp_path):
    """#287: constant-width text hyphenated at line ends (`SUP-/PORTED`), and a
    span holding a real hyphen broke right after it (`--paper-/warm`), so the
    real character vanished into the break. Fifty-four paragraphs walk three
    spans across the line end a character at a time; each comes out whole."""

    tokens = ("--paper-warm", "SUPPORTED_CONTRACT_MAJORS", "round(255*(225-v)/180)")
    paragraphs = []
    for k in range(_CODE_PARAS):
        # the lead grows a character at a time, so the spans sweep the line end
        lead = "Some prose " + "q" * (1 + k % 9) + " " + "word " * (k // 9)
        paragraphs.append(
            f"{lead}then `{tokens[0]}` and `{tokens[1]}` and `{tokens[2]}` close the line."
        )
    handle = (
        factories.BookFactory(slug="int-code")
        .with_sentinels("the witness of the code book")
        .with_chapter(
            "01-code.md",
            "# Code\n\nHere the witness of the code book stands.\n\n" + "\n\n".join(paragraphs),
        )
        .build(tmp_path)
    )
    text = "".join(_pages(_build_pdf(handle)))
    # a span may break after "_", "/", or "." with nothing added (the
    # character stays at the line end); rejoin those, and every token is
    # whole: no inserted hyphen, no real hyphen lost into a break, no token
    # pushed into the margin and cut off
    joined = re.sub(r"([_/.])\n\s*", r"\1", text)
    for token in tokens:
        assert joined.count(token) == _CODE_PARAS, (token, joined.count(token))
    ends = [line.rstrip() for line in text.splitlines()]
    assert not [e for e in ends if re.search(r"(-|\(225-|--paper-)$", e)], (
        "a span broke at a hyphen"
    )


# Spans with no "/", "_", or "." to break at: the first two are the shapes of
# the two pages of Publishing with Press the text-block verifier refused under
# v3's rule.
_PUNCTUATED = (
    'FileNotFoundError("no such file in the manuscript directory")',
    "\\widowpenalty,\\clubpenalty,\\displaywidowpenalty,\\brokenpenalty",
    # wider than the measure, with no space, "/", "_", or "." in it: only the
    # new break points can keep it inside the text block
    "\\widowpenalty=10000;\\clubpenalty=10000;\\displaywidowpenalty=10000:(\\brokenpenalty)",
)
_PUNCT_PARAS = 27


@requires_pdf_toolchain
@pytest.mark.layer("integration")
def test_code_spans_break_after_punctuation_and_stay_in_the_measure(tmp_path):
    """A code span may also break after , ( ) ; = and : at the last-resort
    penalty, adding no glyph. Twenty-seven paragraphs walk the spans across
    the line end; no body page inks past the text block, and every span reads
    whole once its breaks are rejoined: no hyphen invented."""
    from press import verify_text_block as text_block

    paragraphs = []
    for k in range(_PUNCT_PARAS):
        lead = "If neither directory yields a file " + "q" * (1 + k % 9) + " " + "so " * (k // 9)
        paragraphs.append(
            f"{lead}the press refuses with `{_PUNCTUATED[0]}`, and the header sets "
            f"`{_PUNCTUATED[1]}` to ten thousand, written `{_PUNCTUATED[2]}` in full."
        )
    handle = (
        factories.BookFactory(slug="int-punct")
        .with_sentinels("the witness of the punctuation book")
        .with_chapter(
            "01-punct.md",
            "# Punctuation\n\nHere the witness of the punctuation book stands.\n\n"
            + "\n\n".join(paragraphs),
        )
        .build(tmp_path)
    )
    pdf = _build_pdf(handle)
    text = "".join(_pages(pdf))
    out = tmp_path / "render"
    out.mkdir()
    subprocess.run(["pdftoppm", "-png", "-r", "120", str(pdf), str(out / "page")], check=True)
    images = sorted(out.glob("page*.png"))
    with handle.use():
        overruns = text_block.text_block_overruns(
            images, "reading", text_block.first_body_index(pdf)
        )
    past = [(page, px) for page, px in overruns if px > text_block.TEXT_BLOCK_SLACK]
    assert past == [], f"code ran past the text block: {past}"
    # A break after punctuation leaves the character at the line end and adds
    # nothing; rejoin those and every span is whole. The spans hold no hyphen,
    # so one invented at a line end ("FileNot-") would fail the count.
    joined = re.sub(r"([,(=;:/_.)])\s+", r"\1", " ".join(text.split()))
    for token in _PUNCTUATED:
        assert joined.count(token) == _PUNCT_PARAS, (token, joined.count(token))
    assert not re.search(r"(FileNot|Error|penalty|widow|club|broken)\w*-\s", text), (
        "a span gained a hyphen"
    )


# Six hyphenated identifiers, each in its own code span, as a comma list too
# long for one line (the shape of the folio-279 overrun in Publishing with
# Press: "INV-provider-contract, INV-release-receipt-chain, and
# INV-release-tag-grammar" had no break point and ran off the page).
_HYPHENATED = (
    "INV-extension-conformance-ledger",
    "INV-release-receipt-chain-of-custody",
    "INV-release-tag-grammar-is-strict",
    "INV-provider-contract-qualification",
    "INV-archive-source-policy-holds",
    "INV-migration-safe-and-reversible",
)


@requires_pdf_toolchain
@pytest.mark.layer("integration")
def test_hyphenated_code_spans_break_at_a_real_hyphen_not_the_page_edge(tmp_path):
    """#287 follow-up: with every real hyphen boxed, a run of hyphenated
    identifiers had no break point at all, and the line ran past the trim.
    An existing hyphen is now a last-resort break that adds no glyph, so the
    ink stays inside the text block and no identifier gains a hyphen."""

    spans = ", ".join(f"`{name}`" for name in _HYPHENATED[:-1])
    paragraph = (
        f"The ledger names {spans}, and `{_HYPHENATED[-1]}` among its critical "
        "entries, each enforced by a real callable."
    )
    handle = (
        factories.BookFactory(slug="int-hyph")
        .with_sentinels("the witness of the hyphen book")
        .with_chapter(
            "01-hyph.md",
            "# Hyphens\n\nHere the witness of the hyphen book stands in a plain "
            "sentence long enough to survive typesetting.\n\n" + paragraph + "\n",
        )
        .build(tmp_path)
    )
    pdf = _build_pdf(handle)
    pages = _pages(pdf)
    page = _first_page_with(pages, "The ledger names") + 1
    # A break after a real hyphen leaves that hyphen at the line end; rejoin
    # it (and the "/" "_" "." breaks) and every identifier reads whole, once.
    joined = re.sub(r"([-_/.])\n\s*", r"\1", pages[page - 1])
    for name in _HYPHENATED:
        assert joined.count(name) == 1, (name, joined.count(name))
    rightmost = _rightmost_ink_px(pdf, page, tmp_path)
    limit = _text_block_right_px() + PROTRUSION_PX
    assert rightmost <= limit, (
        f"ink reaches {rightmost}px on page {page}; the text block ends at {limit}px, "
        "so a run of hyphenated code spans overran the measure"
    )


@requires_pdf_toolchain
@pytest.mark.layer("integration")
def test_contents_never_strands_a_lone_entry(tmp_path):
    """#291: with 24 entries the Contents held 23 and set the last alone on a
    page under a running head and a folio. The last two entries now carry
    over together, so no Contents page holds exactly one entry."""

    factory = factories.BookFactory(slug="int-toc").with_sentinels("the witness of the toc book")
    factory.with_chapter(
        "00-preface.md",
        "# Preface {.unnumbered}\n\nHere the witness of the toc book stands.\n",
    )
    for k in range(1, 23):
        factory.with_chapter(f"{k:02d}-part.md", f"# Chapter entry {k}\n\nA line of chapter {k}.\n")
    factory.with_appendix("z-colophon.md", "# Colophon {.unnumbered}\n\nThe colophon line.\n")
    pages = _pages(_build_pdf(factory.build(tmp_path)))
    body = _first_page_with(pages, "Here the witness")
    entry = re.compile(r"(Preface|Chapter entry \d+|Colophon)\s.*\d+$")
    toc = [
        n for n in (sum(1 for line in _lines(p) if entry.search(line)) for p in pages[:body]) if n
    ]
    assert sum(toc) == 24, toc
    assert 1 not in toc, f"a Contents page holds a lone entry: {toc}"
