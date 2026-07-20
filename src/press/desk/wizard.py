"""The guided configuration wizard (#166): a keyboard-driven "set up your
book" flow that projects the typed configuration boundary (#155) onto the
desk. It reads and writes nothing except through `config_cli`/`config_store`
- the same door CLI automation uses - so it cannot validate or preserve a
book's YAML differently than `press config` does.

The contract every screen keeps: an edit is collected in memory, previewed
as an exact diff with the real validator's verdict, and written only on an
explicit confirm of a clean preview. Cancel, back, or a validation failure
leaves the file byte-for-byte unchanged.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Label, RichLog, Static

from .. import config_cli, config_schema as schema, config_store as store

# The section the wizard guides: the minimum identity a book cannot build
# without. Each is a field in the config registry, so their types, help,
# and validation come from the one schema, not a second copy here.
IDENTITY_FIELDS = ("title", "subtitle", "author", "description")

METADATA = "config/metadata.yaml"


def _display(value) -> str:
    """A field's current value as one editable line."""

    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def _typed(field: schema.Field, text: str):
    """The typed value a line becomes for this field, refusing a secret or
    a bad shape exactly as the CLI would. Raises store.ConfigError / the
    CLI refusal on a bad value."""

    if field.type == "list[str]":
        value = [text] if text else []
        if config_cli.is_secretish(value):
            raise store.ConfigError(f"{field.path}: the value looks like a secret")
        return value
    return config_cli.check_value(field, text)


class WizardScreen(Screen):
    """Collect the identity fields, each pre-filled with its current value
    and labelled with its help. Nothing is written here; `review` builds a
    preview and hands off to the review screen."""

    BINDINGS = [
        ("escape", "cancel", "cancel"),
        ("ctrl+r", "review", "review changes"),
    ]

    def __init__(self, root: Path) -> None:
        super().__init__()
        self._root = root
        self._current = store.load(root / METADATA)
        self._fields = [f for f in (schema.field_for(p) for p in IDENTITY_FIELDS) if f]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Label("Set up your book: identity", id="wizard-title")
        with Vertical(id="wizard-fields"):
            for field in self._fields:
                current = self._current.get(field.path.split(".")[0])
                required = " (required)" if field.required else ""
                yield Label(f"{field.path}{required} - {field.help}",
                            id=f"label-{field.path}")
                yield Input(value=_display(current), id=f"input-{field.path}",
                            classes="wizard-input")
        yield Label("Ctrl+R to review changes, Esc to cancel (nothing written yet)",
                    id="wizard-status")
        yield Footer()

    def action_cancel(self) -> None:
        # Back with no write: the file is untouched because nothing was
        # written in the first place.
        self.app.pop_screen()

    def action_review(self) -> None:
        edits: list[tuple[str, object]] = []
        for field in self._fields:
            line = self.query_one(f"#input-{field.path}", Input).value.strip()
            if line == _display(self._current.get(field.path.split(".")[0])):
                continue  # unchanged; do not rewrite it
            try:
                edits.append((field.path, _typed(field, line)))
            except store.ConfigError as exc:
                self.query_one("#wizard-status", Label).update(f"{exc}")
                self.query_one(f"#input-{field.path}", Input).focus()
                return
        preview = config_cli.preview_edits(self._root, METADATA, edits)
        self.app.push_screen(ReviewScreen(preview))


class ReviewScreen(Screen):
    """The exact deterministic diff and the validator's verdict before a
    byte is written. `apply` writes only a clean preview; anything else
    leaves the file unchanged."""

    BINDINGS = [
        ("escape", "back", "back (discard)"),
        ("ctrl+a", "apply", "apply"),
    ]

    def __init__(self, preview: config_cli.Preview) -> None:
        super().__init__()
        self._preview = preview

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Label(f"Review changes to {self._preview.file}", id="review-title")
        log = RichLog(id="review-diff", highlight=False, markup=False)
        yield log
        if self._preview.problems:
            yield Static(
                "validation failed - nothing will be written:\n"
                + "\n".join(f"  - {p}" for p in self._preview.problems),
                id="review-verdict", classes="warn")
        elif not self._preview.diff:
            yield Static("no changes to apply", id="review-verdict")
        else:
            yield Static("Ctrl+A to write this diff; Esc to discard",
                         id="review-verdict", classes="ok")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#review-diff", RichLog)
        log.write(self._preview.diff or "(no change)")

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_apply(self) -> None:
        if self._preview.problems or not self._preview.diff:
            return  # nothing valid to write; the verdict already says so
        try:
            config_cli.commit(self._preview)
        except OSError as exc:
            self.query_one("#review-verdict", Static).update(f"could not write: {exc}")
            return
        # Hand back to the desk with a runnable next step, not a readiness
        # claim: the wizard wrote config; `press check` proves the book.
        message = "identity written; next: press check"
        setattr(self.app, "wizard_result", message)
        self.app.pop_screen()  # review
        self.app.pop_screen()  # wizard
        self.app.notify(message)
        self.app.refresh(recompose=True)
