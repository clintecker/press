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
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

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
