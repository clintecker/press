"""The Textual application shell and the DESK dashboard.

The shell is thin: it builds the read model from the authoritative
registries and renders it. Every fact shown comes from
desk_model.build_model, so the desk cannot invent or omit an artifact,
misname a command, or disagree with the CLI. The house theme gives the
desk the press's warm two-ink identity without embedding any book's
design.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Label, Static

from .. import catalog, desk_model
from ..artifact_status import State

# The evidence vocabulary, shown as a glyph plus word so the state reads
# at a glance and never implies freshness from a clock.
STATE_GLYPH = {
    State.ABSENT: ("-", "not built"),
    State.PRESENT_UNVERIFIED: ("o", "present, unverified"),
    State.VERIFIED_CURRENT: ("*", "verified"),
    State.CHANGED_SINCE_PROOF: ("!", "changed since proof"),
    State.INCOMPLETE: ("/", "incomplete"),
}


class DeskApp(App):
    """The operator desk. One screen for now: DESK, the home dashboard."""

    CSS = """
    Screen { background: $surface; }
    #identity { padding: 1 2; border-bottom: solid $primary; }
    #title { text-style: bold; color: $text; }
    #byline { color: $text-muted; }
    #capabilities { padding: 1 2; }
    DataTable { height: auto; }
    .ok { color: $success; }
    .warn { color: $warning; }
    """

    BINDINGS = [
        ("q", "quit", "quit"),
        ("r", "refresh", "refresh"),
    ]

    def __init__(self, root: Path | None = None) -> None:
        super().__init__()
        self._root = root
        self._error: str | None = None

    def _model(self) -> desk_model.DeskModel | None:
        from .. import booklib

        try:
            root = self._root or booklib.root()
            return desk_model.build_model(root)
        except SystemExit as exc:
            self._error = str(exc)
            return None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        model = self._model()
        if model is None:
            yield Static(f"press desk: {self._error}", id="identity")
            yield Footer()
            return
        with Vertical():
            with Vertical(id="identity"):
                yield Label(model.identity.title, id="title")
                yield Label(
                    f"{', '.join(model.identity.authors)}   {model.identity.trim}   "
                    f"{model.identity.slug}",
                    id="byline",
                )
            with Horizontal():
                table: DataTable = DataTable(id="artifacts")
                table.add_columns("artifact", "state", "published")
                for row in model.artifacts:
                    glyph, word = STATE_GLYPH[row.state]
                    table.add_row(row.name, f"{glyph} {word}",
                                  "yes" if row.published else "-")
                yield table
            summary = self._capability_summary(model)
            yield Static(summary, id="capabilities",
                         classes="ok" if model.ready else "warn")
        yield Footer()

    def _capability_summary(self, model: desk_model.DeskModel) -> str:
        if model.ready:
            return "toolchain ready: this machine can build every artifact"
        failing = ", ".join(model.capabilities.failing)
        return f"not ready: {failing} (press doctor names each cost)"

    def action_refresh(self) -> None:
        # Recompose from a fresh model: the desk never caches facts a
        # rebuild would change.
        self.refresh(recompose=True)


def command_names() -> list[str]:
    """The commands the desk offers, from the one catalog (used by the
    picker and palette, and proven equal to the CLI surface)."""

    return [c.name for c in catalog.COMMANDS]
