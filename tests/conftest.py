"""Shared pytest fixtures for the press test suite.

The suite proves the press against real books, not mocks: fixtures
scaffold actual book repositories and point booklib at them through
the same borrow_book context the selftest uses, so a test and the
`press selftest` CLI exercise identical machinery.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from press import pytest_invariants  # noqa: E402  (needs src on sys.path first)


def pytest_configure(config):
    """Install the collection-time invariant/layer/proof enforcement
    (see press.pytest_invariants)."""

    pytest_invariants._install(config)


@pytest.fixture
def scaffolded_book(tmp_path):
    """A freshly scaffolded book repository, with booklib pointed at it
    for the duration of the test and every cache restored afterward."""

    from press import scaffold, selftest

    book = tmp_path / "fixture-book"
    scaffold.main([str(book), "--author", "Fixture Author"])
    with selftest.borrow_book(book):
        yield book
