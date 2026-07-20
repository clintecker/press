"""The RUN view streams a child's output and shows its exact verdict,
and the picker offers exactly the catalog's commands. Driven headlessly
with a fake process, so no real child runs.
"""

from __future__ import annotations

import importlib.util
from collections import deque

import pytest

from tests import factories

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("textual") is None,
    reason="requires capability: textual (pip install 'press[tui]')",
)


class _FakeProcess:
    def __init__(self, lines, returncode):
        from press.process_control import OutputChannel
        self._lines = deque((OutputChannel.STDOUT, ln) for ln in lines)
        self.returncode = returncode

    def read_line(self):
        return self._lines.popleft() if self._lines else None

    def interrupt(self):
        pass

    def terminate(self):
        pass

    def wait(self):
        return self.returncode


def _spawn_returning(lines, returncode):
    def spawn(argv, cwd, env=None):
        return _FakeProcess(lines, returncode)
    return spawn


async def _drain(app):
    await app.workers.wait_for_complete()
    await app.animator.wait_until_complete()


@pytest.mark.layer("integration")
async def test_run_view_streams_output_and_reports_success(tmp_path):
    from press.desk.app import DeskApp, RunScreen
    from textual.widgets import RichLog, Label

    handle = factories.minimal().build(tmp_path)
    with handle.use():
        app = DeskApp(root=handle.root)
        async with app.run_test() as pilot:
            screen = RunScreen(handle.root, "wordcount",
                               spawn=_spawn_returning(["61,204 words"], 0))
            await app.push_screen(screen)
            await pilot.pause()
            await _drain(app)
            await pilot.pause()
            log = screen.query_one("#run-log", RichLog)
            assert any("61,204 words" in str(line) for line in log.lines)
            assert screen.outcome is not None and screen.outcome.succeeded
            status = str(screen.query_one("#run-status", Label).render())
            assert "done" in status


@pytest.mark.layer("integration")
async def test_run_view_reports_the_exact_failing_exit_code(tmp_path):
    from press.desk.app import DeskApp, RunScreen
    from textual.widgets import Label

    handle = factories.minimal().build(tmp_path)
    with handle.use():
        app = DeskApp(root=handle.root)
        async with app.run_test() as pilot:
            screen = RunScreen(handle.root, "check",
                               spawn=_spawn_returning(["a violation"], 43))
            await app.push_screen(screen)
            await pilot.pause()
            await _drain(app)
            await pilot.pause()
            assert screen.outcome is not None
            assert screen.outcome.returncode == 43
            assert not screen.outcome.succeeded
            status = str(screen.query_one("#run-status", Label).render())
            assert "exit 43" in status


@pytest.mark.layer("integration")
async def test_picker_offers_the_catalog_targets(tmp_path):
    from press import catalog
    from press.desk.app import DeskApp, PickerScreen
    from textual.widgets import ListView

    handle = factories.minimal().build(tmp_path)
    with handle.use():
        app = DeskApp(root=handle.root)
        async with app.run_test() as pilot:
            picker = PickerScreen(handle.root)
            await app.push_screen(picker)
            await pilot.pause()
            listing = picker.query_one("#picker-list", ListView)
            offered = {item.id.removeprefix("pick-") for item in listing.children}
            catalog_targets = {c.name for c in catalog.COMMANDS if c.name != "desk"}
            assert offered == catalog_targets
