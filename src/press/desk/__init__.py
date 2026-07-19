"""The operator desk: an optional Textual interface over the press CLI.

This package is imported only when `press desk` runs, and only its
entry touches Textual, so a bare install (no tui extra) builds books
from the command line untouched. The desk reads facts in-process from
the authoritative registries (desk_model, catalog, doctor.examine) and
runs every mutation as a `press <target>` child through the process
controller, so it cannot bless a stale artifact or reinterpret a
child's verdict.
"""

from __future__ import annotations


def run(argv: list[str] | None = None) -> int:
    """Launch the desk, or refuse with the install hint when the optional
    Textual dependency is absent, the way doctor names a missing tool."""

    try:
        import textual  # noqa: F401
    except ImportError:
        print("press desk needs the optional interface: pip install 'press[tui]'")
        return 2

    import sys

    if not sys.stdout.isatty():
        print("press desk needs a terminal; every action it runs is a "
              "`press` target, so use the CLI in a non-interactive context")
        return 2

    from .app import DeskApp

    app = DeskApp()
    app.run()
    return app.return_code or 0
