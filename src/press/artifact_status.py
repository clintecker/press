"""Artifact evidence states, projected from digests, never mtimes.

The operator desk must never infer "fresh" or "stale" from a timestamp:
a file touched but unchanged is not stale, and a file rebuilt to
identical bytes is not new. Truth comes from content digests and the
verification evidence a build recorded, so an artifact's state is one
of a small honest vocabulary:

- ABSENT: the artifact's output does not exist.
- PRESENT_UNVERIFIED: it exists, but no evidence records a digest that
  was verified, so its bytes are unproven.
- VERIFIED_CURRENT: it exists and its current digest matches the digest
  the evidence recorded as verified.
- CHANGED_SINCE_PROOF: it exists but its current digest differs from the
  verified digest, so the proof is stale relative to the bytes.
- INCOMPLETE: some of a multi-output artifact's outputs are missing.

Evidence is a mapping from output path (relative to the dist base, the
directory every artifact lands in) to the digest that was verified; a
build's verifiers write it against the same base the desk reads. Both
sides pass the dist directory as ``base``, so the keys agree. Nothing
here consults a clock.
"""

from __future__ import annotations

import enum
import hashlib
from pathlib import Path


class State(enum.Enum):
    ABSENT = "absent"
    PRESENT_UNVERIFIED = "present-unverified"
    VERIFIED_CURRENT = "verified-current"
    CHANGED_SINCE_PROOF = "changed-since-proof"
    INCOMPLETE = "incomplete"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output_paths(base: Path, slug: str, outputs: tuple[str, ...]) -> list[Path]:
    return [base / o.format(slug=slug) for o in outputs]


def artifact_state(base: Path, slug: str, outputs: tuple[str, ...],
                   evidence: dict[str, str]) -> State:
    """The evidence state of one artifact, from the digests of its
    outputs and the recorded verified digests."""

    paths = output_paths(base, slug, outputs)
    existing = [p for p in paths if p.exists()]
    if not existing:
        return State.ABSENT
    if len(existing) < len(paths):
        return State.INCOMPLETE

    # A directory output (like the site) is represented by its own name
    # in the evidence; a file output by its relative path. Any output
    # with no recorded verified digest leaves the artifact unverified.
    verified = True
    changed = False
    for path in paths:
        rel = str(path.relative_to(base))
        recorded = evidence.get(rel)
        if recorded is None:
            verified = False
            continue
        if path.is_file() and _digest(path) != recorded:
            changed = True
    if changed:
        return State.CHANGED_SINCE_PROOF
    if not verified:
        return State.PRESENT_UNVERIFIED
    return State.VERIFIED_CURRENT


def record_evidence(base: Path, slug: str, outputs: tuple[str, ...]) -> dict[str, str]:
    """The digests to record as verified after a verifier passes: the
    current digest of every file output that exists."""

    evidence: dict[str, str] = {}
    for path in output_paths(base, slug, outputs):
        if path.is_file():
            evidence[str(path.relative_to(base))] = _digest(path)
    return evidence
