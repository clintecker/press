"""The desk polish: cancellation reaches the child, the picker prompts
for a command's arguments, and a toolchain-blocked command is grayed
out and cannot be launched.
"""

from __future__ import annotations

import importlib.util
import threading

import pytest

from tests import factories

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("textual") is None,
    reason="requires capability: textual (pip install 'press[tui]')",
)


class _BlockingProcess:
    """A fake child that streams one line, then blocks until interrupted,
    so a run is genuinely in progress when cancel fires. No sleep: an
    Event coordinates the worker and the cancelling thread."""

    def __init__(self):
        from press.process_control import OutputChannel
        self._first = (OutputChannel.STDOUT, "building...")
        self._sent = False
        self._interrupted = threading.Event()
        self.returncode = 0
        self.interrupts = 0

    def read_line(self):
        if not self._sent:
            self._sent = True
            return self._first
        # Block until cancel interrupts us, then signal end-of-output.
        self._interrupted.wait(timeout=5)
        return None

    def interrupt(self):
        self.interrupts += 1
        self.returncode = -2  # SIGINT, the OS convention
        self._interrupted.set()

    def terminate(self):
        self._interrupted.set()

    def wait(self):
        return self.returncode


def _report(failing_tools=()):
    from press import doctor
    return doctor.DoctorReport(tuple(
        doctor.Finding(name=t, category="tool", state="missing",
                       detail="x", required=True) for t in failing_tools))


@pytest.mark.layer("integration")
async def test_cancel_reaches_the_child_and_reports_cancelled(tmp_path):
    from press.desk.app import DeskApp, RunScreen

    handle = factories.minimal().build(tmp_path)
    proc = _BlockingProcess()
    with handle.use():
        app = DeskApp(root=handle.root)
        async with app.run_test() as pilot:
            screen = RunScreen(handle.root, "all", spawn=lambda *a, **k: proc)
            await app.push_screen(screen)
            await pilot.pause()
            # The run is in progress (first line streamed, then blocked).
            await pilot.press("c")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert proc.interrupts >= 1
            assert screen.outcome is not None
            assert screen.outcome.cancelled
            assert screen.outcome.returncode == -2


@pytest.mark.layer("integration")
async def test_picker_grays_out_a_blocked_command(tmp_path):
    from press.desk.app import DeskApp, PickerScreen
    from textual.widgets import ListView

    handle = factories.minimal().build(tmp_path)
    with handle.use():
        from press import desk_model
        model = desk_model.build_model(handle.root, report=_report(["lualatex"]))
        app = DeskApp(root=handle.root)
        async with app.run_test() as pilot:
            picker = PickerScreen(handle.root, model)
            await app.push_screen(picker)
            await pilot.pause()
            listing = picker.query_one("#picker-list", ListView)
            by_id = {item.id: item for item in listing.children}
            assert by_id["pick-pdf"].disabled  # pdf needs lualatex
            assert not by_id["pick-wordcount"].disabled


@pytest.mark.layer("integration")
async def test_picker_prompts_for_missing_arguments(tmp_path):
    from press.desk.app import DeskApp, PickerScreen
    from textual.widgets import Label, ListView

    handle = factories.minimal().build(tmp_path)
    with handle.use():
        app = DeskApp(root=handle.root)
        async with app.run_test() as pilot:
            picker = PickerScreen(handle.root)
            await app.push_screen(picker)
            await pilot.pause()
            listing = picker.query_one("#picker-list", ListView)
            # Select an arg-taking command (publish) with no arguments.
            children = list(listing.children)
            publish = next(i for i in children if i.id == "pick-publish")
            index = children.index(publish)
            listing.index = index
            await pilot.pause()
            picker.on_list_view_selected(ListView.Selected(listing, publish, index))
            await pilot.pause()
            # It did not launch; the title now prompts for the arguments.
            title = str(picker.query_one("#picker-title", Label).render())
            assert "needs arguments" in title
            assert isinstance(app.screen, PickerScreen)
