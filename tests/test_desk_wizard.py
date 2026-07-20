"""The guided configuration wizard, driven headlessly (#166).

Every scenario runs against a real scaffolded book with active signals (no
screenshots): the wizard's promise is that it writes only through the #155
boundary and only on a confirmed clean preview, so the tests assert the
file on disk, not the pixels.
"""

from __future__ import annotations

import importlib.util

import pytest

from press import config_store as store
from tests import factories

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("textual") is None,
    reason="requires capability: textual (pip install 'press[tui]')",
)


def _title(root):
    return store.load(root / "config" / "metadata.yaml").get("title")


@pytest.mark.layer("integration")
async def test_wizard_opens_prefilled_with_current_identity(tmp_path):
    from textual.widgets import Input

    from press.desk.app import DeskApp

    handle = factories.minimal().build(tmp_path)
    with handle.use():
        app = DeskApp(root=handle.root)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.action_wizard()
            await pilot.pause()
            assert app.screen.query_one("#input-title", Input).value == handle.metadata["title"]


@pytest.mark.layer("integration")
async def test_editing_and_applying_writes_through_the_boundary(tmp_path):
    from textual.widgets import Input

    from press.desk.app import DeskApp

    handle = factories.minimal().build(tmp_path)
    with handle.use():
        app = DeskApp(root=handle.root)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.action_wizard()
            await pilot.pause()
            app.screen.query_one("#input-title", Input).value = "A Brand New Title"
            app.screen.action_review()
            await pilot.pause()
            # The review screen shows a clean, applyable verdict.
            assert "ok" in app.screen.query_one("#review-verdict").classes
            app.screen.action_apply()
            await pilot.pause()
        assert _title(handle.root) == "A Brand New Title"
        assert app.wizard_result and "press check" in app.wizard_result


@pytest.mark.layer("integration")
async def test_an_invalid_edit_is_previewed_but_never_written(tmp_path):
    from textual.widgets import Input

    from press.desk.app import DeskApp

    handle = factories.minimal().build(tmp_path)
    with handle.use():
        before = (handle.root / "config" / "metadata.yaml").read_bytes()
        app = DeskApp(root=handle.root)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.action_wizard()
            await pilot.pause()
            app.screen.query_one("#input-title", Input).value = ""  # title is required
            app.screen.action_review()
            await pilot.pause()
            verdict = str(app.screen.query_one("#review-verdict").render())
            assert "validation failed" in verdict and "title" in verdict
            app.screen.action_apply()  # must be a no-op
            await pilot.pause()
        assert (handle.root / "config" / "metadata.yaml").read_bytes() == before


@pytest.mark.layer("integration")
async def test_cancel_leaves_the_file_unchanged(tmp_path):
    from textual.widgets import Input

    from press.desk.app import DeskApp

    handle = factories.minimal().build(tmp_path)
    with handle.use():
        before = (handle.root / "config" / "metadata.yaml").read_bytes()
        app = DeskApp(root=handle.root)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.action_wizard()
            await pilot.pause()
            app.screen.query_one("#input-title", Input).value = "Discarded"
            app.screen.action_cancel()
            await pilot.pause()
        assert (handle.root / "config" / "metadata.yaml").read_bytes() == before


@pytest.mark.layer("integration")
async def test_a_secret_value_is_refused_without_leaving_the_wizard(tmp_path):
    from textual.widgets import Input, Label

    from press.desk.app import DeskApp

    handle = factories.minimal().build(tmp_path)
    with handle.use():
        before = (handle.root / "config" / "metadata.yaml").read_bytes()
        app = DeskApp(root=handle.root)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.action_wizard()
            await pilot.pause()
            app.screen.query_one("#input-description", Input).value = "token=sk-abcdef0123456789xyz"
            app.screen.action_review()
            await pilot.pause()
            # Still on the wizard (no review pushed), status names the refusal.
            status = str(app.screen.query_one("#wizard-status", Label).render())
            assert "secret" in status
        assert (handle.root / "config" / "metadata.yaml").read_bytes() == before
