"""Artifact evidence states come from digests, never mtimes: a touched
but unchanged file is not stale, and a rebuilt-identical file is not
new.
"""

from __future__ import annotations

import os

from press import artifact_status
from press.artifact_status import State


def test_absent_when_no_output(tmp_path):
    state = artifact_status.artifact_state(tmp_path, "book", ("{slug}.pdf",), {})
    assert state == State.ABSENT


def test_present_unverified_without_evidence(tmp_path):
    (tmp_path / "book.pdf").write_bytes(b"PDF")
    state = artifact_status.artifact_state(tmp_path, "book", ("{slug}.pdf",), {})
    assert state == State.PRESENT_UNVERIFIED


def test_verified_current_when_digest_matches(tmp_path):
    (tmp_path / "book.pdf").write_bytes(b"PDF")
    evidence = artifact_status.record_evidence(tmp_path, "book", ("{slug}.pdf",))
    state = artifact_status.artifact_state(tmp_path, "book", ("{slug}.pdf",), evidence)
    assert state == State.VERIFIED_CURRENT


def test_touch_without_change_stays_verified(tmp_path):
    """The mtime-free guarantee: touching the file does not make it
    stale, because its digest is unchanged."""

    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"PDF")
    evidence = artifact_status.record_evidence(tmp_path, "book", ("{slug}.pdf",))
    os.utime(pdf, (0, 0))  # move the mtime far into the past
    state = artifact_status.artifact_state(tmp_path, "book", ("{slug}.pdf",), evidence)
    assert state == State.VERIFIED_CURRENT


def test_changed_since_proof_when_bytes_differ(tmp_path):
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"PDF")
    evidence = artifact_status.record_evidence(tmp_path, "book", ("{slug}.pdf",))
    pdf.write_bytes(b"DIFFERENT")
    state = artifact_status.artifact_state(tmp_path, "book", ("{slug}.pdf",), evidence)
    assert state == State.CHANGED_SINCE_PROOF


def test_rebuild_to_identical_bytes_is_current(tmp_path):
    """A rebuild that produces the same bytes is not 'new' work to
    redo: the digest matches, so the state stays verified."""

    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"PDF")
    evidence = artifact_status.record_evidence(tmp_path, "book", ("{slug}.pdf",))
    pdf.write_bytes(b"PDF")  # rebuilt, identical
    state = artifact_status.artifact_state(tmp_path, "book", ("{slug}.pdf",), evidence)
    assert state == State.VERIFIED_CURRENT


def test_incomplete_when_some_outputs_missing(tmp_path):
    (tmp_path / "book-site.zip").write_bytes(b"zip")
    state = artifact_status.artifact_state(
        tmp_path, "book", ("site", "{slug}-site.zip"), {})
    assert state == State.INCOMPLETE
