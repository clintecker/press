"""Real-tool integration runner: the web surfaces (HTML, reader site, Pages).

Three real artifacts, three real verifiers:

  - the single-leaf ``dist/<slug>.html`` built by pandoc, inspected by
    ``verify_formats.verify_html`` (the manuscript-witness law);
  - the chunked reader ``dist/site`` built by pandoc's chunkedhtml
    writer, inspected by ``verify_formats.verify_site`` (each chapter's
    witness present exactly once);
  - the assembled ``dist/pages`` GitHub Pages site, inspected by the
    real ``verify_pages`` crawler (every local reference and stylesheet
    url resolves, every declared download present and linked).

HTML and the site need only pandoc. Pages depends on every published
download -- including the reading PDF -- so it gates on the full PDF
toolchain and skips (naming those capabilities) when they are absent,
which keeps a missing LuaLaTeX from masquerading as a broken site.
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

PANDOC = ("pandoc",)
requires_pandoc = pytest.mark.skipif(
    bool(missing_tools(PANDOC)), reason=skip_reason(PANDOC)
)
requires_pages_toolchain = pytest.mark.skipif(
    bool(missing_tools(PDF_TOOLCHAIN)), reason=skip_reason(PDF_TOOLCHAIN)
)


def _book(root):
    return (
        factories.BookFactory(slug="int-web")
        .with_sentinels(
            "alpha witness of the web runner",
            "beta witness of the web runner",
        )
        .with_chapter(
            "00-intro.md",
            "# Intro\n\nHere the alpha witness of the web runner stands in a "
            "plain sentence long enough to read as a chapter.\n",
        )
        .with_chapter(
            "01-more.md",
            "# More\n\nHere the beta witness of the web runner stands in "
            "another plain sentence long enough to read as a chapter.\n",
        )
        .build(root)
    )


@requires_pandoc
@pytest.mark.layer("integration")
@pytest.mark.invariant("INV-format-witness")
@pytest.mark.proof("positive")
def test_single_leaf_html_keeps_witness(tmp_path):
    from press import booklib, registry, verify_formats

    handle = _book(tmp_path)
    evidence = Evidence(
        family="html",
        required_tools=PANDOC,
        tool_versions=tool_versions(PANDOC),
        input_manifest_digest=source_manifest_digest(handle.root),
    )
    with handle.use():
        slug = booklib.slug()
        dist = booklib.root() / "dist"
        registry.build("html")
        verify_formats.verify_html(dist / f"{slug}.html")
        evidence.record_verifier("verify_formats.verify_html")
        evidence.record_invariant("INV-format-witness")
        evidence.outputs = digest_outputs(dist, [f"{slug}.html"])
    evidence.write(tmp_path)

    assert f"{slug}.html" in evidence.outputs
    assert "verify_formats.verify_html" in evidence.verifiers


@requires_pandoc
@pytest.mark.layer("integration")
@pytest.mark.invariant("INV-format-site-identity")
@pytest.mark.proof("positive")
def test_reader_site_chapter_identity(tmp_path):
    from press import booklib, registry, verify_formats

    handle = _book(tmp_path)
    evidence = Evidence(
        family="site",
        required_tools=PANDOC,
        tool_versions=tool_versions(PANDOC),
        input_manifest_digest=source_manifest_digest(handle.root),
    )
    with handle.use():
        slug = booklib.slug()
        dist = booklib.root() / "dist"
        registry.build("site")
        verify_formats.verify_site(dist / "site")
        evidence.record_verifier("verify_formats.verify_site")
        evidence.record_invariant("INV-format-site-identity")
        evidence.outputs = digest_outputs(dist, ["site", f"{slug}-site.zip"])
    evidence.write(tmp_path)

    assert "site/" in evidence.outputs, "no reader site directory was produced"
    assert "verify_formats.verify_site" in evidence.verifiers


@requires_pages_toolchain
@pytest.mark.layer("integration")
@pytest.mark.invariant("INV-pages-refs")
@pytest.mark.proof("positive")
def test_pages_references_resolve(tmp_path):
    from press import booklib, registry, verify_pages

    handle = _book(tmp_path)
    evidence = Evidence(
        family="pages",
        required_tools=PDF_TOOLCHAIN,
        tool_versions=tool_versions(PDF_TOOLCHAIN),
        input_manifest_digest=source_manifest_digest(handle.root),
    )
    with handle.use():
        booklib.slug()
        dist = booklib.root() / "dist"
        # pages stands on every published download, PDF included; the
        # registry builds the whole prerequisite graph first.
        registry.build("pages")
        rc = verify_pages.main()
        evidence.record_verifier("verify_pages.main")
        evidence.record_invariant("INV-pages-refs")
        evidence.outputs = digest_outputs(dist, ["pages"])
    evidence.write(tmp_path)

    assert rc == 0, "verify_pages found an unresolved reference on the built site"
    assert "pages/" in evidence.outputs, "no pages site directory was produced"
    assert all(
        evidence.tool_versions[tool] != "absent" for tool in PDF_TOOLCHAIN
    )
