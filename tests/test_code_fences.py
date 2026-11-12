"""Both kinds of code fence wrap in the PDF (#279).

pandoc sets a fence with a recognised language tag in the ``Highlighting``
environment and an untagged fence in plain ``verbatim``. The TeX header
rebinds ``verbatim`` to fvextra's ``Verbatim`` with the same line-break
options Highlighting carries, so the two cannot drift apart: a long line
wraps the same way whether or not the fence names a language. The rendered
proof is the PDF-family integration runner; this is the fast, toolchain-free
guard on the header text itself.
"""

from __future__ import annotations

import re
from pathlib import Path

import press

HEADER = Path(press.__file__).resolve().parent / "data" / "tex" / "book-header.tex"
_ENV = r"^\\{command}\{{{name}\}}\{{Verbatim\}}\{{(.*)\}}$"


def _options(command: str, name: str) -> set[str] | None:
    match = re.search(_ENV.format(command=command, name=name), HEADER.read_text("utf-8"), re.M)
    if match is None:
        return None
    return {opt.strip() for opt in match.group(1).split(",") if opt.strip()}


def test_highlighting_breaks_lines():
    options = _options("DefineVerbatimEnvironment", "Highlighting")
    assert options is not None, "Highlighting is no longer defined on fvextra's Verbatim"
    assert {"breaklines", "breakanywhere"} <= options


def test_plain_verbatim_breaks_lines_like_highlighting():
    verbatim = _options("RecustomVerbatimEnvironment", "verbatim")
    assert verbatim is not None, (
        "plain verbatim is not rebound to fvextra's Verbatim; "
        "an untagged fence would run off the page edge (#279)"
    )
    highlighting = _options("DefineVerbatimEnvironment", "Highlighting") or set()
    # commandchars is pandoc's escape hatch for colour tokens, meaningless in
    # plain verbatim; every other option must match so the two wrap alike.
    breaks = {opt for opt in highlighting if not opt.startswith("commandchars")}
    assert verbatim == breaks, f"verbatim {sorted(verbatim)} != Highlighting {sorted(breaks)}"
