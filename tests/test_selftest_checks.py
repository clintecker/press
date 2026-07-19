"""The selftest's invariant checks, run as individual pytest cases.

Facts once: each test calls the same check_* function the `press
selftest` CLI runs, so the two runners cannot disagree. A check that
fails raises SystemExit or AssertionError; pytest reports which
invariant broke by name instead of the CLI's first-failure exit.
"""

from __future__ import annotations

import pytest

from press import selftest

# Every zero-argument invariant check the selftest orchestrates. The
# list is the same order main() runs them; a new check_* added to the
# module must be added here too (the meta-test below proves it).
INVARIANT_CHECKS = [
    selftest.check_imports,
    selftest.check_arithmetic,
    selftest.check_slug_invariant,
    selftest.check_source_policy,
    selftest.check_pages_verifier,
    selftest.check_scaffold_neutrality,
    selftest.check_book_model,
    selftest.check_registry,
    selftest.check_format_witnesses,
    selftest.check_site_identity,
    selftest.check_authorities_ledger,
    selftest.check_honest_refusals,
    selftest.check_release_grammar,
    selftest.check_coverwrap_detectors,
    selftest.check_aesthetic_schema,
    selftest.check_contract_mirror,
    selftest.check_docs,
]


@pytest.mark.parametrize("check", INVARIANT_CHECKS, ids=lambda c: c.__name__)
def test_invariant_check_passes(check):
    check()


def test_every_check_is_covered():
    """No check_* function in the selftest may escape the pytest suite:
    the parametrized list above must name every one the module defines,
    so a new invariant cannot ship untested here."""

    defined = {
        name for name in dir(selftest)
        if name.startswith("check_") and callable(getattr(selftest, name))
    }
    covered = {check.__name__ for check in INVARIANT_CHECKS}
    missing = sorted(defined - covered)
    assert not missing, f"selftest checks not in the pytest suite: {missing}"


@pytest.mark.parametrize("slug", selftest.GOOD_SLUGS)
def test_slug_invariant_accepts_good(slug):
    from press import booklib

    assert booklib.validate_slug(slug) == slug


@pytest.mark.parametrize("slug", selftest.BAD_SLUGS)
def test_slug_invariant_rejects_bad(slug):
    from press import booklib

    with pytest.raises(SystemExit):
        booklib.validate_slug(slug)
