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
    )
