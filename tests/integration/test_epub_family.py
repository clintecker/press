"""Real-tool integration runner: the EPUB circulating edition.

Builds a source-only factory book to ``dist/<slug>.epub`` with real
pandoc, then inspects it with the real ``verify_formats`` EPUB verifier
(structural checks plus the manuscript-witness law) and runs the real
``epubcheck`` when it is installed. epubcheck is absent from an authoring
sandbox by design -- the verifier softens it to a warning there and the
CI toolchain image runs it for real -- so this runner records epubcheck's
presence in the evidence but gates only on pandoc, the tool required to
produce the artifact at all.
"""

from __future__ import annotations

import shutil

import pytest

from tests import factories
from tests.integration._harness import (
    Evidence,
    digest_outputs,
    missing_tools,
    skip_reason,
    source_manifest_digest,
    tool_versions,
)

REQUIRED = ("pandoc",)
requires_pandoc = pytest.mark.skipif(
    bool(missing_tools(REQUIRED)), reason=skip_reason(REQUIRED)
)


def _book(root):
    return (
        factories.BookFactory(slug="int-epub")
        .with_sentinels(
            "first witness of the epub runner",
            "second witness of the epub runner",
        )
        .with_chapter(
            "00-intro.md",
            "# Intro\n\nHere the first witness of the epub runner stands in a "
            "plain sentence long enough to serve as a manuscript witness.\n",
        )
        .with_chapter(
            "01-more.md",
            "# More\n\nHere the second witness of the epub runner stands in "
            "another plain sentence long enough to serve as a witness.\n",
        )
        .build(root)
    )


@requires_pandoc
@pytest.mark.layer("integration")
@pytest.mark.invariant("INV-format-witness")
@pytest.mark.proof("positive")
def test_epub_keeps_its_witnesses(tmp_path):
    from press import booklib, registry, verify_formats

    handle = _book(tmp_path)
    evidence = Evidence(
        family="epub",
        required_tools=REQUIRED,
        tool_versions=tool_versions(REQUIRED + ("epubcheck",)),
        input_manifest_digest=source_manifest_digest(handle.root),
    )
    with handle.use():
        slug = booklib.slug()
        dist = booklib.root() / "dist"
        registry.build("epub")
        epub = dist / f"{slug}.epub"
        verify_formats.verify_epub(epub)
        evidence.record_verifier("verify_formats.verify_epub")
        evidence.record_invariant("INV-format-witness")
        # The real retail validator when present; a soft warning when not
        # (authoring sandbox). Either way it must not raise on a valid book.
        verify_formats.epubcheck(epub)
        evidence.record_verifier("verify_formats.epubcheck")
        evidence.notes["epubcheck"] = (
            "present" if shutil.which("epubcheck") else "absent (softened to warning)"
        )
        evidence.outputs = digest_outputs(dist, [f"{slug}.epub"])
    evidence.write(tmp_path)

    assert f"{slug}.epub" in evidence.outputs, "no EPUB was produced"
    assert "verify_formats.verify_epub" in evidence.verifiers
    assert evidence.tool_versions["pandoc"] != "absent"
