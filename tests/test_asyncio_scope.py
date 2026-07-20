"""The async fixture loop scope is function, and proven so, not left to
pytest-asyncio's shifting default (#169).

Function scope means each async test runs on its own event loop, so no task,
timer, or loop-bound fixture can outlive the test that created it — the
suite's isolation law. These tests fail if the scope ever widens (a shared
loop would make the loop identities match, and a leaked task would survive).
"""

from __future__ import annotations

import asyncio

import pytest

_loops: set[int] = set()


@pytest.mark.asyncio
async def test_each_async_test_gets_its_own_loop_first():
    _loops.add(id(asyncio.get_running_loop()))


@pytest.mark.asyncio
async def test_each_async_test_gets_its_own_loop_second():
    # A distinct loop object from the first test proves function scope; a
    # shared (wider-scoped) loop would collide.
    loop_id = id(asyncio.get_running_loop())
    assert loop_id not in _loops, "async tests shared an event loop (scope widened)"


@pytest.mark.asyncio
async def test_no_task_leaks_past_a_test():
    # Any task this test spawns must be gone by the time the next test's
    # fresh loop starts; assert the loop begins with only this coroutine.
    others = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    assert others == [], f"a task leaked into this test's loop: {others}"
