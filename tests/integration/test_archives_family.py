"""Real-tool integration runner: the archives and the sources companion.

Builds the three archive-family artifacts from a source-only factory
book that is a real git repository (so the publication policy has a
tracked-file set to enforce) and carries an authorities ledger (so the
sources companion is generated), then inspects them all with the real
``verify_archives`` verifier:

  - ``dist/<slug>-site.zip`` -- byte-for-byte the verified reader site;
  - ``dist/<slug>-source.zip`` -- tracked files only, no secret, no
    escaping member (built by the real ``package_source`` over
    ``git ls-files``);
  - ``dist/<slug>-sources.md`` -- the table of authorities, every claim
    mapped to its source.

Gates on pandoc (the site) and git (the tracked-file policy); a missing
tool skips the runner naming that capability.
"""

from __future__ import annotations

import os
import subprocess

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

REQUIRED = ("pandoc", "git")
requires_tools = pytest.mark.skipif(
    bool(missing_tools(REQUIRED)), reason=skip_reason(REQUIRED)
)

CLAIM = "movable type reorders the labor of the page"


def _book(root):
    handle = (
        factories.BookFactory(slug="int-archive")
        .with_sentinels(
            "first witness of the archive runner",
            "second witness of the archive runner",
        )
        .with_chapter(
            "00-intro.md",
            "# Intro\n\nHere the first witness of the archive runner stands, "
            f"and {CLAIM}.\n",
        )
        .with_chapter(
            "01-more.md",
            "# More\n\nHere the second witness of the archive runner stands "
            "in another plain sentence.\n",
        )
        .with_authorities([
            {"claim": CLAIM, "file": "book/chapters/00-intro.md",
             "authority": "A Trade History (1900)"},
        ])
        .build(root)
    )
    # A real repository: the source-archive policy is "tracked files
    # only", which needs an actual git index to prove. Run git hermetically
    # -- ambient global/system config ignored, identity supplied inline, no
    # signing -- so the runner uses no ambient credential or config.
    env = {
        "PATH": os.environ.get("PATH", ""),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    }
    identity = [
        "-c", "user.email=runner@press.test",
        "-c", "user.name=runner",
        "-c", "commit.gpgsign=false",
    ]
    subprocess.run(["git", "init", "-q"], cwd=handle.root, check=True, env=env)
    subprocess.run(["git", "add", "-A"], cwd=handle.root, check=True, env=env)
    subprocess.run(
        ["git", *identity, "commit", "-q", "-m", "source-only book"],
        cwd=handle.root, check=True, env=env,
    )
    return handle


@requires_tools
@pytest.mark.layer("integration")
@pytest.mark.invariant("INV-archive-source-policy")
@pytest.mark.proof("positive")
def test_archives_and_sources_companion(tmp_path):
    from press import booklib, package_source, registry, verify_archives

    handle = _book(tmp_path)
    evidence = Evidence(
        family="archives",
        required_tools=REQUIRED,
        tool_versions=tool_versions(REQUIRED),
        input_manifest_digest=source_manifest_digest(handle.root),
    )
    with handle.use():
        slug = booklib.slug()
        dist = booklib.root() / "dist"
        # markdown generates the sources companion; site produces the
        # reader zip; package_source writes the tracked-only source zip.
        registry.build("markdown")
        registry.build("site")
        package_source.main()
        rc = verify_archives.main()
        evidence.record_verifier("package_source.main")
        evidence.record_verifier("verify_archives.main")
        evidence.record_invariant("INV-archive-source-policy")
        evidence.record_invariant("INV-archive-site-bytes")
        evidence.record_invariant("INV-authorities-claims")
        evidence.outputs = digest_outputs(dist, [
            f"{slug}-site.zip", f"{slug}-source.zip", f"{slug}-sources.md",
        ])
    evidence.write(tmp_path)

    assert rc == 0, "verify_archives refused the freshly built archives"
    for name in (f"{slug}-site.zip", f"{slug}-source.zip", f"{slug}-sources.md"):
        assert name in evidence.outputs, f"{name} was not produced"
    assert evidence.tool_versions["git"] != "absent"
