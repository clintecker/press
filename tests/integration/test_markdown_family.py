"""Real-tool integration runner: the portable editions (Markdown, text, DOCX).

Builds three source-only artifacts and inspects each with its real
verifier, all of which enforce the manuscript-witness law:

  - ``dist/<slug>.md``  -- the stitched Markdown, checked by
    ``verify_formats.verify_plaintext``;
  - ``dist/<slug>.txt`` -- pandoc's 80-column plain text, same verifier;
  - ``dist/<slug>.docx`` -- pandoc's DOCX, unzipped and flattened by
    ``verify_formats.verify_docx``.

The stitched Markdown is pure-Python, but the text and DOCX editions are
pandoc renders, so the runner gates on pandoc and skips (naming it) when
it is absent.
"""

from __future__ import annotations

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
        factories.BookFactory(slug="int-portable")
        .with_sentinels(
            "first witness of the portable runner",
            "second witness of the portable runner",
        )
        .with_chapter(
            "00-intro.md",
            "# Intro\n\nHere the first witness of the portable runner stands "
            "in a plain sentence long enough to survive every crossing.\n",
        )
        .with_chapter(
            "01-more.md",
            "# More\n\nHere the second witness of the portable runner stands "
            "in another plain sentence long enough to survive.\n",
        )
        .build(root)
    )


@requires_pandoc
@pytest.mark.layer("integration")
@pytest.mark.invariant("INV-format-witness")
@pytest.mark.proof("positive")
def test_portable_editions_keep_witnesses(tmp_path):
    from press import booklib, registry, verify_formats

    handle = _book(tmp_path)
    evidence = Evidence(
        family="portable",
        required_tools=REQUIRED,
        tool_versions=tool_versions(REQUIRED),
        input_manifest_digest=source_manifest_digest(handle.root),
    )
    with handle.use():
        slug = booklib.slug()
        dist = booklib.root() / "dist"
        for target in ("markdown", "txt", "docx"):
            registry.build(target)
        verify_formats.verify_plaintext(dist / f"{slug}.md", "markdown")
        evidence.record_verifier("verify_formats.verify_plaintext[markdown]")
        verify_formats.verify_plaintext(dist / f"{slug}.txt", "text")
        evidence.record_verifier("verify_formats.verify_plaintext[text]")
        verify_formats.verify_docx(dist / f"{slug}.docx")
        evidence.record_verifier("verify_formats.verify_docx")
        evidence.record_invariant("INV-format-witness")
        evidence.outputs = digest_outputs(
            dist, [f"{slug}.md", f"{slug}.txt", f"{slug}.docx"]
        )
    evidence.write(tmp_path)

    for name in (f"{slug}.md", f"{slug}.txt", f"{slug}.docx"):
        assert name in evidence.outputs, f"{name} was not produced"
    assert len(evidence.verifiers) == 3
    assert evidence.tool_versions["pandoc"] != "absent"
