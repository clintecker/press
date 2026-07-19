"""Real-tool integration runner: the print interior and the retail cover wrap.

Builds the print pack from a source-only factory book carrying real
cover art, with the actual pandoc -> LuaLaTeX -> latexmk toolchain, then
inspects both artifacts with their real verifiers:

  - ``dist/<slug>-interior.pdf`` -- the print-profile interior, inspected
    by ``verify_pdf`` in the print profile (ink on every page, mirrored
    margins, black ink only);
  - ``dist/<slug>-coverwrap.pdf`` -- the one-page wrap sized at trim plus
    bleed plus a spine recomputed from the built interior, inspected by
    the real ``verify_coverwrap`` (geometry, embedded fonts, front art
    present, title survives, structural barcode panel).

The wrap stands on the interior, so both come from a single build shared
across the two proofs. Gates on the full PDF toolchain; skips naming
those capabilities when any is absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from tests import factories
from tests.integration._harness import (
    PDF_TOOLCHAIN,
    Evidence,
    digest_outputs,
    make_cover,
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
        factories.BookFactory(slug="int-coverwrap")
        .with_sentinels(
            "first witness of the coverwrap runner",
            "second witness of the coverwrap runner",
        )
        .with_metadata(publisher="Integration Press", **{"publisher-place": "Nowhere"})
        .with_chapter(
            "00-intro.md",
            "# Intro\n\nHere the first witness of the coverwrap runner stands "
            "in a plain sentence long enough to typeset for print.\n",
        )
        .with_chapter(
            "01-more.md",
            "# More\n\nHere the second witness of the coverwrap runner stands "
            "in another plain sentence long enough to typeset for print.\n",
        )
        .build(root)
    )


@dataclass
class PrintPack:
    root: Path
    dist: Path
    slug: str
    evidence: Evidence


@pytest.fixture(scope="module")
def print_pack(tmp_path_factory):
    from press import booklib, registry

    root = tmp_path_factory.mktemp("coverwrap")
    handle = _book(root)
    make_cover(handle.root / "assets" / "cover.jpg")
    evidence = Evidence(
        family="coverwrap",
        required_tools=REQUIRED,
        tool_versions=tool_versions(REQUIRED),
        input_manifest_digest=source_manifest_digest(handle.root),
    )
    with handle.use():
        slug = booklib.slug()
        dist = booklib.root() / "dist"
        # coverwrap stands on the print interior; the registry builds it
        # first, so one toolchain run serves both proofs.
        registry.build("coverwrap")
        evidence.outputs = digest_outputs(
            dist, [f"{slug}-interior.pdf", f"{slug}-coverwrap.pdf"]
        )
        yield PrintPack(root=handle.root, dist=dist, slug=slug, evidence=evidence)
    evidence.write(root)


@requires_pdf_toolchain
@pytest.mark.layer("integration")
@pytest.mark.invariant("INV-pdf-ink")
@pytest.mark.proof("positive")
def test_print_interior_carries_ink(print_pack):
    from press import verify_pdf

    rc = verify_pdf.main([
        str(print_pack.dist / f"{print_pack.slug}-interior.pdf"),
        "--profile", "print",
    ])
    print_pack.evidence.record_verifier("verify_pdf.main[--profile print]")
    print_pack.evidence.record_invariant("INV-pdf-ink")

    assert rc == 0, "verify_pdf refused the print interior"
    assert f"{print_pack.slug}-interior.pdf" in print_pack.evidence.outputs


@requires_pdf_toolchain
@pytest.mark.layer("integration")
@pytest.mark.invariant("INV-coverwrap-geometry")
@pytest.mark.proof("positive")
def test_coverwrap_geometry_and_barcode(print_pack):
    from press import verify_coverwrap

    rc = verify_coverwrap.main()
    print_pack.evidence.record_verifier("verify_coverwrap.main")
    print_pack.evidence.record_invariant("INV-coverwrap-geometry")
    print_pack.evidence.record_invariant("INV-coverwrap-barcode")

    assert rc == 0, "verify_coverwrap refused the freshly built wrap"
    assert f"{print_pack.slug}-coverwrap.pdf" in print_pack.evidence.outputs
    assert all(
        print_pack.evidence.tool_versions[tool] != "absent" for tool in REQUIRED
    )
