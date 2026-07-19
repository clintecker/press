"""Deterministic retry over an injected finite state sequence.

The press has no wall-clock polling loop in Python today (the only
retry/poll pattern lives in ``scripts/release.sh``, which is bash). This
module is the seam for when it does: a retry decision is driven by a
``RetrySource`` and a finite attempt budget, never by ``time.sleep`` and a
deadline. A test drives it with a scripted sequence of states and asserts
on the transitions and the budget, so nothing depends on elapsed time.

``resolve`` polls the source until ``is_terminal`` accepts a state or the
budget is spent; a spent budget is a ``PolicyError``, not a hang.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..results import PolicyError
from .protocols import RetrySource


@dataclass(frozen=True)
class RetryBudget:
    """A finite attempt budget. ``max_attempts`` polls are permitted before
    the loop gives up; there is no time component by construction."""

    max_attempts: int

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise PolicyError("a retry budget must permit at least one attempt")


def resolve(
    source: RetrySource,
    budget: RetryBudget,
    is_terminal: Callable[[Any], bool],
) -> Any:
    """Poll ``source`` until ``is_terminal`` accepts a state, at most
    ``budget.max_attempts`` times. Returns the terminal state; raises
    ``PolicyError`` when the budget is spent with no terminal state.

    Deterministic: given the same source sequence and budget, the outcome
    is fixed. No sleeping, no clock."""

    last: Any = None
    for _ in range(budget.max_attempts):
        last = source.poll()
        if is_terminal(last):
            return last
    raise PolicyError(
        f"retry budget of {budget.max_attempts} attempt(s) spent without a "
        f"terminal state (last: {last!r})"
    )
