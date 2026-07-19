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

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    DataTable, Footer, Header, Input, Label, ListItem, ListView, RichLog, Static,
)

from .. import catalog, desk_model, process_control
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
        ("p", "pick", "run a target"),
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

    def action_pick(self) -> None:
        from .. import booklib

        try:
            root = self._root or booklib.root()
        except SystemExit:
            return
        # Pass the model so the picker can gray out commands a missing
        # toolchain blocks.
        model = self._model()
        self.push_screen(PickerScreen(root, model))


def command_names() -> list[str]:
    """The commands the desk offers, from the one catalog (used by the
    picker and palette, and proven equal to the CLI surface)."""

    return [c.name for c in catalog.COMMANDS]


class RunScreen(Screen):
    """A streamed run of one press child. The controller owns the
    process; this screen streams its lines and shows the child's exact
    verdict, never reinterpreting it. The spawn is injected so the
    headless harness drives a fake process, never a real child."""

    BINDINGS = [
        ("c", "cancel", "cancel"),
        ("escape", "leave", "back"),
    ]

    def __init__(self, root: Path, target: str, args: tuple[str, ...] = (),
                 *, spawn=None) -> None:
        super().__init__()
        self._root = root
        self._target = target
        self._args = args
        self._spawn = spawn
        self._controller: process_control.ProcessController | None = None
        self.outcome: process_control.Outcome | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        shown = " ".join([self._target, *self._args])
        yield Label(f"$ press {shown}", id="run-command")
        yield RichLog(id="run-log", highlight=False, markup=False)
        yield Label("running... (c to cancel)", id="run-status")
        yield Footer()

    def on_mount(self) -> None:
        self.run_child()

    @work(thread=True)
    def run_child(self) -> None:
        controller = process_control.ProcessController(self._root, spawn=self._spawn)
        self._controller = controller
        invocation = process_control.Invocation.of(self._target, *self._args)

        def sink(channel, line: str) -> None:
            self.app.call_from_thread(self.query_one("#run-log", RichLog).write, line)

        controller.start(invocation)
        while controller.poll(sink):
            pass
        outcome = controller.finish()
        self.outcome = outcome
        if outcome.cancelled:
            verdict = f"cancelled (exit {outcome.returncode})"
        elif outcome.succeeded:
            verdict = "done"
        else:
            verdict = f"failed (exit {outcome.returncode})"
        self.app.call_from_thread(
            self.query_one("#run-status", Label).update,
            f"{verdict}; the exit code is the verdict",
        )

    def action_cancel(self) -> None:
        # Signal the child's process group; the run loop then drains and
        # finish() reports the cancelled verdict. Guarded so cancel is a
        # no-op once the child has stopped.
        controller = self._controller
        if controller is not None and controller.is_running:
            controller.cancel()

    def action_leave(self) -> None:
        # Leaving a live run cancels it rather than orphaning the child.
        self.action_cancel()
        self.app.pop_screen()


class PickerScreen(Screen):
    """The target picker, generated from the catalog so it offers exactly
    the CLI's commands. A command a missing toolchain blocks shows its
    reason and cannot be launched into a guaranteed failure; a command
    that takes arguments prompts for them before running."""

    BINDINGS = [("escape", "app.pop_screen", "back")]

    def __init__(self, root: Path, model: desk_model.DeskModel | None = None) -> None:
        super().__init__()
        self._root = root
        self._model = model

    def _blocked_reason(self, name: str) -> str | None:
        return self._model.blocked_reason(name) if self._model is not None else None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Label("run a target", id="picker-title")
        items = []
        for command in catalog.COMMANDS:
            if command.name == "desk":
                continue
            blocked = self._blocked_reason(command.name)
            hint = command.args or ""
            if blocked:
                label = f"{command.name}  (blocked: {blocked})"
            elif hint:
                label = f"{command.name}  [{hint}]"
            else:
                label = command.name
            item = ListItem(Label(label), id=f"pick-{command.name}")
            item.disabled = blocked is not None
            items.append(item)
        yield ListView(*items, id="picker-list")
        yield Input(placeholder="arguments (optional)", id="picker-args")
        yield Footer()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item is None or event.item.id is None or event.item.disabled:
            return
        target = event.item.id.removeprefix("pick-")
        command = catalog.by_name().get(target)
        raw = self.query_one("#picker-args", Input).value.strip()
        args = tuple(raw.split()) if raw else ()
        # A command that needs arguments and got none stays on the picker
        # with a prompt rather than running straight into a usage error.
        if command is not None and command.args and not args:
            self.query_one("#picker-title", Label).update(
                f"{target} needs arguments: {command.args}")
            self.query_one("#picker-args", Input).focus()
            return
        self.app.pop_screen()
        self.app.push_screen(RunScreen(self._root, target, args))
