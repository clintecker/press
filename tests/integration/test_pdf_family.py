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


def _text_block_right_px(page: int) -> int:
    # A recto (odd) page binds on its left, so its right margin is the outer one.
    margin = OUTER_IN if page % 2 else INNER_IN
    return round((TRIM_WIDTH_IN - margin) * RENDER_DPI)


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
    limit = _text_block_right_px(page) + PROTRUSION_PX
    assert rightmost <= limit, (
        f"ink reaches {rightmost}px on page {page}; the text block ends at {limit}px "
        f"(page width {TRIM_WIDTH_IN * RENDER_DPI:.0f}px), so a code line overran the measure"
    )
    assert "SourceCodePro" in fonts, "the untagged fence was not set in Source Code Pro"
