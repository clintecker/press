"""The operator desk, driven headlessly.

The desk is proven the way the press proves everything: against a real
scaffolded book, with active signals, no screenshots-as-truth. Textual's
run_test drives the app at a fixed terminal size with no real terminal,
so these run in CI wherever the tui extra is installed and skip cleanly
where it is not. The desk's facts must equal the read model's, because
the desk renders the model and nothing else.
"""

from __future__ import annotations

import importlib.util

import pytest

from tests import factories

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("textual") is None,
    reason="requires capability: textual (pip install 'press[tui]')",
)


@pytest.mark.layer("integration")
async def test_desk_shows_the_book_identity(tmp_path):
    from press.desk.app import DeskApp

    handle = factories.minimal().build(tmp_path)
    with handle.use():
        app = DeskApp(root=handle.root)
        async with app.run_test() as pilot:
            await pilot.pause()
            title = app.query_one("#title").render()
            assert handle.metadata["title"] in str(title)


@pytest.mark.layer("integration")
async def test_desk_lists_every_registry_artifact(tmp_path):
    from press import desk_model
    from press.desk.app import DeskApp
    from textual.widgets import DataTable

    handle = factories.minimal().build(tmp_path)
    with handle.use():
        model = desk_model.build_model(handle.root)
        app = DeskApp(root=handle.root)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one("#artifacts", DataTable)
            assert table.row_count == len(model.artifacts)


@pytest.mark.layer("integration")
async def test_desk_refuses_outside_a_book(tmp_path):
    from press.desk.app import DeskApp

    # A directory that is not a book: the desk shows a refusal, not a
    # traceback.
    app = DeskApp(root=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app._error is not None


@pytest.mark.layer("integration")
async def test_desk_commands_equal_the_catalog():
    from press import catalog
    from press.desk.app import command_names

    assert command_names() == [c.name for c in catalog.COMMANDS]


def test_desk_entry_refuses_without_a_tty(monkeypatch, capsys):
    """The entry degrades to a clear message on a non-terminal instead
    of trying to draw."""

    import sys
    from press import desk

    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    code = desk.run([])
    assert code == 2
    assert "terminal" in capsys.readouterr().out
