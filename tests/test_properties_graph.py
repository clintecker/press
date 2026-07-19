"""Property-based proofs for the artifact dependency graph.

registry.build_order is pure over the static ARTIFACTS table: given a
set of requested targets it must return a topological order of their
transitive closure. These properties prove the graph laws the selftest
asserts only for the whole-graph case, across arbitrary target subsets.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from press import registry

DETERMINISTIC = settings(derandomize=True, deadline=None, max_examples=200)

_NAMES = sorted(registry.ARTIFACTS)
_TARGETS = st.lists(st.sampled_from(_NAMES), min_size=1, max_size=len(_NAMES), unique=True)


def _closure(targets):
    """The requested targets plus every transitive prerequisite, as a set."""

    seen: set[str] = set()
    stack = list(targets)
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        stack.extend(registry.ARTIFACTS[name].prerequisites)
    return seen


@pytest.mark.invariant("INV-graph-acyclic")
@pytest.mark.layer("property")
@pytest.mark.proof("positive")
@DETERMINISTIC
@given(targets=_TARGETS)
def test_build_order_is_a_topological_order_of_the_closure(targets):
    """Every prerequisite precedes its dependent, the output is exactly
    the transitive closure with no duplicates, and each requested target
    is present."""

    order = registry.build_order(targets)

    # No duplicates, and every emitted name is a real artifact.
    assert len(order) == len(set(order))
    assert set(order) <= set(_NAMES)

    # Exactly the transitive closure of the requested targets.
    assert set(order) == _closure(targets)
    for target in targets:
        assert target in order

    # Dependency-first: a prerequisite always appears before its dependent.
    position = {name: i for i, name in enumerate(order)}
    for name in order:
        for prerequisite in registry.ARTIFACTS[name].prerequisites:
            assert position[prerequisite] < position[name]


@pytest.mark.invariant("INV-graph-acyclic")
@pytest.mark.layer("property")
@pytest.mark.proof("positive")
@DETERMINISTIC
@given(targets=_TARGETS)
def test_build_order_is_deterministic(targets):
    """The same request yields byte-identical ordering every time: build
    dispatch cannot depend on iteration luck."""

    assert registry.build_order(targets) == registry.build_order(targets)


@pytest.mark.invariant("INV-graph-acyclic")
@pytest.mark.layer("property")
@pytest.mark.proof("negative")
@DETERMINISTIC
@given(name=st.text(min_size=1, max_size=20).filter(lambda s: s not in registry.ARTIFACTS))
def test_build_order_refuses_unknown_target(name):
    """An unknown target name is a named refusal, never a KeyError."""

    with pytest.raises(SystemExit):
        registry.build_order([name])
