"""press branding for the terminal: the palette, the banner, and the status
glyphs.

Color is emitted only to a real terminal that has not set ``NO_COLOR`` (and is
forced on by ``FORCE_COLOR``), so piped or captured output stays plain and
scriptable. The accent is the house vermilion (xterm-256 203, bright form of
``#A53326``); paper is 250, dim/caption 242, and the verify glyph green is 108.
The pilcrow is the press mark.
"""

from __future__ import annotations

import sys
from typing import TextIO

# xterm-256 slots for the house palette (ink #16130F, vermilion #A53326 ->
# #E0503F on dark, paper #FBF8F2).
VERMILION = "203"
PAPER = "250"
DIM = "242"
GREEN = "108"

PILCROW = "¶"   # the press mark
CHECK = "✓"


def use_color(stream: TextIO | None = None) -> bool:
    """True when we should emit ANSI: a TTY, no NO_COLOR, or forced."""

    from . import adapters

    if adapters.environment.get("NO_COLOR"):
        return False
    if adapters.environment.get("FORCE_COLOR"):
        return True
    stream = stream if stream is not None else sys.stdout
    return bool(getattr(stream, "isatty", lambda: False)())


def paint(text: str, color: str, stream: TextIO | None = None) -> str:
    """Wrap text in an xterm-256 foreground color, or return it unchanged when
    color is off."""

    if not use_color(stream):
        return text
    return f"\033[38;5;{color}m{text}\033[0m"


_BANNER = (
    "██████  █████   ██████  ██████  ██████\n"  # noqa: E501
    "██  ██  ██  ██  ██      ██      ██\n"
    "██████  █████   █████   ██████  ██████\n"  # noqa: E501
    "██      ██ ██   ██          ██      ██\n"
    "██      ██  ██  ██████  ██████  ██████"  # noqa: E501
)


def banner(version: str, stream: TextIO | None = None) -> str:
    """The block banner with the tagline and version line."""

    art = "\n".join(paint(line, VERMILION, stream) for line in _BANNER.splitlines())
    tagline = paint("  markdown → a finished book", PAPER, stream)
    meta = paint(f"  v{version} · MIT · run press all", DIM, stream)
    return f"{art}\n\n{tagline}\n{meta}\n"


def phase(name: str, detail: str, stream: TextIO | None = None) -> str:
    """One status line: a vermilion pilcrow, the phase name, a green tick and
    what it produced."""

    mark = paint(PILCROW, VERMILION, stream)
    done = paint(f"{CHECK} {detail}", GREEN, stream)
    return f"  {mark} {name:<10} {done}"


def ready(destination: str, stream: TextIO | None = None) -> str:
    """The completion line: ``press. your book is ready -> dist/``."""

    return f"\n  {paint('press.', VERMILION, stream)} your book is ready → {destination}\n"
