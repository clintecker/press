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

import pytest

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
