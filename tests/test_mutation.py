"""The deterministic mutation engine that feeds celebrimbor's ratchet.

``press.mutation`` enumerates the mutable operators in a pure policy module
and applies exactly one edit per mutant. These are the machinery
``survivors()`` stands on; if enumeration misses an operator or ``_apply``
mutates the wrong node, a real logic change would go untested and the
ratchet would silently weaken. The whole-module ``survivors()`` run is
exercised by the mutation ratchet itself (it shells out per mutant); this
pins the enumeration and single-edit contract without that cost.
"""

from __future__ import annotations

import ast

from press import mutation


def test_enumerate_finds_each_operator_class_and_dedupes():
    src = "def f(a, b):\n    return a < b and a + 1\n"
    sites = mutation._enumerate(ast.parse(src))
    kinds = {s.kind for s in sites}
    assert {"compare", "arith", "bool", "intconst"} <= kinds
    # Every site is enumerated exactly once (left-nested BinOps share a
    # position and must not double-count).
    ids = [mutation._site_id(s) for s in sites]
    assert len(ids) == len(set(ids))


def test_apply_mutates_exactly_one_site_and_leaves_the_rest():
    tree = ast.parse("def f(a, b):\n    return a < b and a + 1\n")
    sites = mutation._enumerate(tree)
    compare = next(s for s in sites if s.kind == "compare")
    mutated = ast.unparse(mutation._apply(tree, compare))
    assert "a <= b" in mutated  # < flipped to <=
    assert "a + 1" in mutated  # the arithmetic operator is untouched
