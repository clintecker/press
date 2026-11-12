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


# --- A fence that already fit renders exactly as it did ----------------------
#
# The v3 contract: a fix may correct broken output but must not move a valid
# book's typography or layout. The rebind of plain verbatim to fvextra's
# Verbatim (#279) is proven against that contract by rendering one book
# twice: once with the house header, once with the kernel verbatim restored
# through the book's own tex/title-page.tex (the last include, so it wins).
# Every page before the overlong fence must be pixel-identical; the final
# page, which carries the overlong line, must differ, which proves the
# restore took effect and the fix bites.
KERNEL_VERBATIM_TEX = r"""
% Restore LaTeX's own verbatim, as the header left it before #279. These are
% the kernel's definitions verbatim (latex.ltx), so the control render is
% what a book pinned to v3 saw before the rebind.
\makeatletter
\renewcommand\verbatim{\@verbatim \frenchspacing\@vobeyspaces \@xverbatim}
\renewcommand\endverbatim{\if@newlist \leavevmode\fi\endtrivlist}
\makeatother
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


def _differing_pages(house, kernel) -> list[int]:
    from PIL import Image, ImageChops

    differing = []
    for number, (a, b) in enumerate(zip(house, kernel, strict=True), start=1):
        with Image.open(a) as left, Image.open(b) as right:
            if left.size != right.size:
                differing.append(number)
                continue
            box = ImageChops.difference(left.convert("L"), right.convert("L")).getbbox()
        if box is not None:
            differing.append(number)
    return differing


@requires_pdf_toolchain
@pytest.mark.layer("integration")
@pytest.mark.invariant("INV-design-layout-stable")
@pytest.mark.proof("positive")
def test_fitting_code_fence_is_pixel_identical_to_kernel_verbatim(tmp_path):
    """Every page of a book whose fences fit renders pixel-identical under
    the rebound verbatim and under the kernel verbatim it replaced; only the
    page carrying an overlong line differs, and there the rebind keeps the
    ink inside the measure where the kernel let it reach the page edge."""

    evidence = Evidence(
        family="pdf-fence-identity",
        required_tools=REQUIRED,
        tool_versions=tool_versions(REQUIRED),
    )
    house, house_digest = _render_pages(tmp_path / "house", "% house header, unmodified\n")
    kernel, kernel_digest = _render_pages(tmp_path / "kernel", KERNEL_VERBATIM_TEX)
    evidence.outputs = {"house": house_digest, "kernel": kernel_digest}
    evidence.record_invariant("INV-design-layout-stable")
    evidence.record_invariant("INV-pdf-ink")

    assert len(house) == len(kernel) > 3, (
        f"page counts differ ({len(house)} vs {len(kernel)}): the rebind moved a page break"
    )
    last = len(house)
    differing = _differing_pages(house, kernel)
    evidence.notes["differing_pages"] = ",".join(map(str, differing))
    evidence.write(tmp_path)

    assert differing == [last], (
        f"pages {differing} differ between the rebound verbatim and the kernel verbatim at "
        f"{IDENTITY_DPI} dpi; only page {last}, which carries the overlong line, may differ. "
        "A fence that already fit must not move: that is a design change within v3."
    )
    # The control is live and the fix bites: on the last page the kernel
    # verbatim ran the overlong line to the page edge, the rebind wraps it.
    from PIL import Image

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
    with its first two rows, and every term with the first line under it."""

    tables = []
    for k in range(_KEEPS):
        lead = "A lead-in line of plain prose before the table. " * (1 + k % 5)
        # wide rows: pandoc sets relative p-columns, so each row wraps to two
        # or three lines, the shape of a real reference table
        cell = "a cell long enough to wrap onto a second line in its column " * 2
        rows = "\n".join(f"| row{k}x{r} | {cell}|" for r in range(5))
        tables.append(
            f"{lead}\n\n| head{k}col | Meaning |\n|------------------|{'-' * 50}|\n"
            f"{rows}\n\nTable: Table {k}. A caption over the table\n"
        )
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
        if _page_of(pages, f"head{k}col", body) != _page_of(pages, f"row{k}x1", body)
    ]
    assert not stranded, f"table heads stranded from their first two rows: {stranded}"
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
