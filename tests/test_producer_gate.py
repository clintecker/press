"""The producer gate: every producer must name the rejection its verifier turns
on. This is the check whose absence let gen_front_matter ship a blind verifier.
Proven by rejecting an unregistered producer and an overlapping one."""

from __future__ import annotations

import pytest

from press import selftest, surfaces


@pytest.mark.layer("unit")
def test_every_current_producer_is_registered():
    # The real config passes: all producers are proven or explicitly pending.
    assert selftest.check_producers_are_verified() is None


@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_new_producer_without_a_proof_is_rejected(monkeypatch):
    base = surfaces.load_config()["modules"]
    monkeypatch.setattr(surfaces, "load_config",
                        lambda *a, **k: {"modules": {**base, "brand_new": "producer"}})
    with pytest.raises(SystemExit, match="no registered rejection proof"):
        selftest.check_producers_are_verified()


@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_producer_cannot_be_both_proven_and_pending(monkeypatch):
    someone = next(iter(selftest.PRODUCER_REJECTION_PROOFS))
    monkeypatch.setitem(selftest.PRODUCERS_PENDING_REJECTION_PROOF, someone, "double-listed")
    with pytest.raises(SystemExit, match="both proven and pending"):
        selftest.check_producers_are_verified()
