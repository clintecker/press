"""The command catalog is the single source of the CLI and desk surface.

These prove the parity the selftest check enforces, plus the catalog's
own shape, so the desk (which reads this catalog) offers exactly what
the CLI runs.
"""

from __future__ import annotations

from press import __main__ as cli
from press import catalog


def test_every_catalog_command_is_dispatchable():
    routes = set(cli.ROUTES)
    formats = set(cli.FORMATS) | {"print"}
    for command in catalog.COMMANDS:
        target = command.alias_of or command.name
        assert (command.name in routes or command.name in formats
                or target in routes or target in formats), command.name


def test_every_route_is_a_catalog_command():
    known = catalog.canonical_targets()
    for route in cli.ROUTES:
        assert route in known, route


def test_usage_is_generated_from_the_catalog():
    assert cli.USAGE == catalog.render_usage()


def test_every_command_has_a_known_group():
    for command in catalog.COMMANDS:
        assert command.group in catalog.GROUP_ORDER, command.name


def test_names_are_unique():
    names = [c.name for c in catalog.COMMANDS]
    assert len(names) == len(set(names))


def test_aliases_point_at_real_commands():
    names = {c.name for c in catalog.COMMANDS}
    for command in catalog.COMMANDS:
        if command.alias_of:
            assert command.alias_of in names, command.name


def test_usage_names_every_command():
    usage = catalog.render_usage()
    for command in catalog.COMMANDS:
        assert command.name in usage, command.name
