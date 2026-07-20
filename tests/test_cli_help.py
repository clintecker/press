"""Conventional help and version discovery (#175).

`--help`/`-h` and `--version` must answer and exit 0 without executing a
handler, building, mutating, or needing a book, a TTY, or the toolchain.
Every command is reachable from the catalog, so help cannot describe a
command the CLI does not dispatch, or omit one it does.
"""

from __future__ import annotations

import press
from press import __main__ as cli
from press import catalog


# ---- global help and version ----------------------------------------

def test_global_help_exits_zero_and_lists_commands(capsys):
    assert cli.main(["--help"]) == 0
    out = capsys.readouterr().out
    assert "usage: press <command>" in out
    # Every non-alias command appears by name.
    for command in catalog.COMMANDS:
        if not command.alias_of:
            assert command.name in out, command.name


def test_dash_h_is_the_same_as_help(capsys):
    assert cli.main(["-h"]) == 0
    assert "usage: press <command>" in capsys.readouterr().out


def test_version_reports_the_installed_distribution(capsys):
    assert cli.main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"press {press.version()}"


def test_dash_capital_v_is_version(capsys):
    assert cli.main(["-V"]) == 0
    assert capsys.readouterr().out.strip() == f"press {press.version()}"


def test_help_and_version_need_no_book(monkeypatch, tmp_path, capsys):
    # Point at a directory that is not a book; discovery must still answer.
    monkeypatch.setenv("BOOK_ROOT", str(tmp_path))
    assert cli.main(["--help"]) == 0
    assert cli.main(["--version"]) == 0


# ---- per-command help ------------------------------------------------

def test_command_help_does_not_execute_the_handler(capsys):
    # doctor --help must show help, not run the diagnostic (which would
    # print a findings table); publish/desk likewise must not act.
    for name in ["doctor", "publish", "desk", "pdf", "config"]:
        assert cli.main([name, "--help"]) == 0, name
        out = capsys.readouterr().out
        assert name in out
        assert "show this help" in out


def test_every_command_has_renderable_help():
    # A snapshot-style guard: help exists for every catalog command and
    # names it, so a new command cannot ship undocumented.
    for command in catalog.COMMANDS:
        text = catalog.render_command_help(command.name)
        assert command.name in text
        assert "Reference:" in text


def test_an_alias_command_renders_its_own_help():
    # verify-pages is a spelling of pages with its own catalog entry.
    text = catalog.render_command_help("verify-pages")
    assert "press verify-pages" in text and "Reference:" in text


def test_help_for_an_unknown_command_falls_back_to_global():
    text = catalog.render_command_help("no-such-command")
    assert "usage: press <command>" in text


def test_a_build_command_help_notes_the_artifact_and_toolchain():
    text = catalog.render_command_help("pdf")
    assert "dist/" in text and "toolchain" in text


def test_suggest_returns_none_for_gibberish():
    assert catalog.suggest("zzzzzzzz") is None


# ---- unknown commands ------------------------------------------------

def test_unknown_command_exits_two_with_a_pointer(capsys):
    assert cli.main(["nonsense"]) == 2
    out = capsys.readouterr().out
    assert "unknown target: nonsense" in out
    assert "press --help" in out


def test_a_near_miss_suggests_the_nearest_command(capsys):
    assert cli.main(["chekc"]) == 2
    assert "did you mean `press check`" in capsys.readouterr().out
