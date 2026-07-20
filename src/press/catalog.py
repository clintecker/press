"""The one typed command catalog.

Every press command is declared here once, with its group, a one-line
summary, and an argument grammar. The CLI renders its usage text from
this catalog, dispatch is validated against it, and the operator desk
builds its target picker and command palette from the same list, so the
command-line surface and the desk surface cannot drift apart: a command
the desk offers is a command the CLI runs, spelled the same way.

A command is either dispatched through a named handler in __main__'s
route table, or is a build format handled by the build fallthrough
(build_format=True). Aliases (two names, one behavior) point at the
same canonical command via alias_of.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Command:
    name: str
    group: str
    summary: str
    args: str = ""  # a short grammar hint, e.g. "<directory>" or "kdp|ingram"
    build_format: bool = False  # dispatched by the FORMATS/print fallthrough
    alias_of: str | None = None  # a second spelling of another command
    aliases: tuple[str, ...] = field(default_factory=tuple)


# Order within a group is the order the usage text prints.
COMMANDS: tuple[Command, ...] = (
    # building
    Command("pdf", "building", "Build the reading PDF", build_format=True),
    Command("epub", "building", "Build the EPUB", build_format=True),
    Command("html", "building", "Build the single-file HTML", build_format=True),
    Command("markdown", "building", "Stitch the distributable Markdown", build_format=True),
    Command("site", "building", "Build the per-chapter reader site", build_format=True),
    Command("txt", "building", "Build the plain-text edition", build_format=True),
    Command("docx", "building", "Build the DOCX edition", build_format=True),
    Command("pages", "building", "Assemble and verify the GitHub Pages site"),
    Command("source", "building", "Package the source archive"),
    Command("all", "building", "Build and verify every artifact"),
    # checking
    Command("check", "checking", "Run the editorial law"),
    Command("style", "checking", "Run the prose style audit"),
    Command("verify", "checking", "Rebuild and verify the reading PDF"),
    Command("verify-formats", "checking", "Rebuild and verify every non-PDF format"),
    Command("verify-pages", "checking", "Assemble and verify the Pages site",
            alias_of="pages"),
    # print pack
    Command("print", "print pack", "Build the print-profile interior", build_format=True),
    Command("verify-print", "print pack", "Verify the interior and cover wrap"),
    Command("coverwrap", "print pack", "Build and verify the cover wrap"),
    Command("publish", "print pack", "Emit a retail channel checklist",
            args="kdp|ingram [--report-only]"),
    # utilities
    Command("render", "utilities", "Render the PDF to page PNGs"),
    Command("wordcount", "utilities", "Count the manuscript words"),
    Command("clean", "utilities", "Remove build and dist"),
    Command("new", "utilities", "Scaffold a new book", args="<directory>"),
    Command("config", "utilities", "Read and write book configuration",
            args="get|set|unset|list|validate"),
    Command("selftest", "utilities", "The press checking itself"),
    Command("doctor", "utilities", "Diagnose the toolchain"),
    # instruments
    Command("skills", "instruments", "List the packaged authoring skills"),
    Command("workflows", "instruments", "List the packaged agent workflows"),
    Command("desk", "instruments", "Open the operator desk (needs the tui extra)"),
    # art
    Command("art", "art", "Commission or accept cover and plate art",
            args="commission [targets] | accept <file> --as <target>"),
    # operator
    Command("improve", "operator", "Editorial counsel (report-first)", args="[--apply]"),
    Command("research", "operator", "Build the table of authorities"),
    Command("aesthetic", "operator", "Show or draft the visual identity", args='["<brief>"]'),
)

GROUP_ORDER = (
    "building", "checking", "print pack", "utilities", "instruments",
    "art", "operator",
)


def by_name() -> dict[str, Command]:
    return {c.name: c for c in COMMANDS}


def canonical_targets() -> set[str]:
    """Every command name the CLI must accept: catalog names plus their
    aliases."""

    names = {c.name for c in COMMANDS}
    for command in COMMANDS:
        names.update(command.aliases)
    return names


def render_usage() -> str:
    """The usage text, generated from the catalog so it cannot drift
    from the commands the CLI actually dispatches."""

    lines = ["usage: press <target>", ""]
    label_width = max(len(g) for g in GROUP_ORDER)
    for group in GROUP_ORDER:
        members = [c for c in COMMANDS if c.group == group]
        if not members:
            continue
        words = []
        for command in members:
            token = command.name
            if command.args:
                token += f" {command.args}"
            words.append(token)
        lines.append(f"{group:<{label_width}}  {'  '.join(words)}")
    return "\n".join(lines) + "\n"
