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
        # A real print ISBN, so the wrap draws a real EAN-13 (not the
        # placeholder) and verify_coverwrap runs the quiet-zone check -- the
        # guard for the node-padding regression that let the first guard bar
        # read as ink in the left quiet zone (#210).
        .with_metadata(
            publisher="Integration Press",
            **{"publisher-place": "Nowhere"},
            registrations={"isbn": {"print": "9781960780010"}},
        )
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
        # Tagged fences: skylighting's default style coloured them and
        # verify_black_ink refused the interior (#273); the print profile now
        # highlights with the packaged monochrome theme, and this chapter is
        # the fixture that proves a tagged fence builds and prints black.
        .with_chapter(
            "02-listing.md",
            "# Listing\n\nA short example in each tag the issue named.\n\n"
            "```python\n# a comment\ndef f(x):\n    return 'string' + str(1)\n```\n\n"
            "```yaml\nkey: value\nlist:\n  - 1\n```\n\n"
            "```sh\nexport NAME=value && press all\n```\n",
        )
        .build(root)
    )


# The imprint logo's ink: pure blue, a colour nothing else on the wrap
# carries, so the render can find the logo by it.
_LOGO_INK = (0, 0, 255)


def _make_logo(path: Path) -> None:
    """An imprint logo the way the art desk keeps one: ink on transparency.
    A blue square sits in the middle fifth; the rest is transparent ground."""

    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle([40, 40, 59, 59], fill=(*_LOGO_INK, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


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
    _make_logo(handle.root / "assets" / "press-logo.png")
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
        evidence.outputs = digest_outputs(dist, [f"{slug}-interior.pdf", f"{slug}-coverwrap.pdf"])
        yield PrintPack(root=handle.root, dist=dist, slug=slug, evidence=evidence)
    evidence.write(root)


@requires_pdf_toolchain
@pytest.mark.layer("integration")
@pytest.mark.invariant("INV-pdf-ink")
@pytest.mark.proof("positive")
def test_print_interior_carries_ink(print_pack):
    from press import verify_pdf

    rc = verify_pdf.main(
        [
            str(print_pack.dist / f"{print_pack.slug}-interior.pdf"),
            "--profile",
            "print",
        ]
    )
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
    assert all(print_pack.evidence.tool_versions[tool] != "absent" for tool in REQUIRED)


@requires_pdf_toolchain
@pytest.mark.layer("integration")
@pytest.mark.proof("positive")
def test_logo_ground_is_the_field_colour(print_pack, tmp_path):
    # The logo is flattened onto the cloth field colour so its ground
    # vanishes; the field is painted from a raster of that same value so a
    # colour-managed viewer cannot render the two through different paths
    # and box the logo. Sample both from the real render: one colour.
    import subprocess

    from PIL import Image

    from press import gen_coverwrap

    wrap = print_pack.dist / f"{print_pack.slug}-coverwrap.pdf"
    dpi = 100
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi), str(wrap), str(tmp_path / "wrap")], check=True
    )
    image = Image.open(next(tmp_path.glob("wrap*.png"))).convert("RGB")
    ink = [
        (x, y)
        for y in range(image.height)
        for x in range(image.width // 2)  # the back panel holds the logo
        if (lambda p: p[2] > 200 and p[0] < 60 and p[1] < 60)(image.getpixel((x, y)))
    ]
    assert ink, "the imprint logo's ink did not reach the wrap"
    left = min(x for x, _ in ink)
    right = max(x for x, _ in ink)
    mid_y = (min(y for _, y in ink) + max(y for _, y in ink)) // 2
    # One ink-width left of the ink is still inside the logo (the ink is its
    # middle fifth): the flattened ground.
    ground = image.getpixel((left - (right - left + 1), mid_y))
    # A corner of the back panel inside the bleed: only the field is there.
    field = image.getpixel((int(0.3 * dpi), int(0.3 * dpi)))

    assert field == gen_coverwrap._CLOTH_FIELD_RGB
    assert ground == field, f"logo ground {ground} differs from the field {field}"
