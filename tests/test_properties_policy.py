"""Property-based proofs for the source-publication policy.

package_source.publication_members is the single statement of what a
public source archive may contain. It reads a directory but needs no
book: these properties build throwaway trees under the system tempdir
(never a git repository, so the tracked-file gate stands down and the
pattern policy is what is under test) and prove the safety law that
matters -- a file whose name matches a secret pattern is never admitted.

Each example builds and tears down its own tree by hand rather than
through a pytest fixture, so hypothesis drives it without a
function-scoped-fixture health-check violation. The example count is
bounded low because the policy shells out to git once per call.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from press import package_source

DETERMINISTIC = settings(derandomize=True, deadline=None, max_examples=40)

_TOKEN = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", max_size=8)


@st.composite
def _secret_names(draw):
    """A filename that matches one of the fixed secret patterns."""

    pattern = draw(st.sampled_from(package_source.SECRET_PATTERNS))
    name = "".join(part if part != "*" else draw(_TOKEN) for part in _split_star(pattern))
    # A leading-dot-only name (e.g. an empty token before ".pem") is still
    # a legal, secret-matching filename; guard only against the empty string.
    if not name:
        name = "secret"
    return name


def _split_star(pattern):
    """Yield the pattern in alternating literal / '*' pieces."""

    for i, chunk in enumerate(pattern.split("*")):
        if i:
            yield "*"
        if chunk:
            yield chunk


@pytest.mark.invariant("INV-archive-source-policy")
@pytest.mark.layer("property")
@pytest.mark.proof("negative")
@DETERMINISTIC
@given(name=_secret_names())
def test_secret_named_file_is_never_admitted(name):
    """A file matching any secret pattern aborts the whole archive; the
    policy raises rather than returning it among the members."""

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / name).write_bytes(b"KEY MATERIAL")
        with pytest.raises(SystemExit):
            package_source.publication_members(root)


@pytest.mark.invariant("INV-archive-source-policy")
@pytest.mark.layer("property")
@pytest.mark.proof("positive")
@DETERMINISTIC
@given(token=_TOKEN)
def test_benign_file_is_admitted(token):
    """Outside a git repository a plain, non-secret, non-junk file is
    admitted as a member -- the policy is a gate, not a wall."""

    name = f"chapter-{token}.md"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / name).write_bytes(b"# body\n")
        members, _ = package_source.publication_members(root)
        assert name in [relative for _, relative in members]
