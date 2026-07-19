"""The selftest's invariant checks, run as individual pytest cases.

Facts once: each test calls the same check_* function the `press
selftest` CLI runs, so the two runners cannot disagree. A check that
fails raises SystemExit or AssertionError; pytest reports which
invariant broke by name instead of the CLI's first-failure exit.
"""

from __future__ import annotations

import pytest

from press import selftest


@pytest.mark.parametrize("check", selftest.CHECKS, ids=lambda c: c.__name__)
def test_invariant_check_passes(check):
    check()


def test_every_check_is_orchestrated():
    """No check_* function may escape the ordered CHECKS list that both
    the CLI and this suite run: a new invariant added to the module but
    not wired into CHECKS would prove nothing anywhere, so it fails
    here."""

    defined = {
        name for name in dir(selftest)
        if name.startswith("check_") and callable(getattr(selftest, name))
    }
    orchestrated = {check.__name__ for check in selftest.CHECKS}
    missing = sorted(defined - orchestrated)
    assert not missing, f"selftest checks not in CHECKS: {missing}"


@pytest.mark.parametrize("slug", selftest.GOOD_SLUGS)
def test_slug_invariant_accepts_good(slug):
    from press import booklib

    assert booklib.validate_slug(slug) == slug


@pytest.mark.parametrize("slug", selftest.BAD_SLUGS)
def test_slug_invariant_rejects_bad(slug):
    from press import booklib

    with pytest.raises(SystemExit):
        booklib.validate_slug(slug)
