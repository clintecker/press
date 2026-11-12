"""Both kinds of code fence wrap in the PDF, and a fence that fit still
renders exactly as it did (#279).

pandoc sets a fence with a recognised language tag in the ``Highlighting``
environment and an untagged fence in plain ``verbatim``. The TeX header
rebinds ``verbatim`` to fvextra's ``Verbatim`` with the line-break options
Highlighting carries, so a long line wraps whether or not the fence names a
language. fvextra's Verbatim does not space lines the way the kernel's
verbatim does, so the rebind also carries the options that restore the
kernel's spacing: without them a fence that already fit would move by half
a point a line, which is a design change the v3 contract forbids. The
rendered proof is the PDF-family integration runner (two builds, pixel
compared); this is the fast, toolchain-free guard on the header text.
"""

from __future__ import annotations

import re
from pathlib import Path

import press

HEADER = Path(press.__file__).resolve().parent / "data" / "tex" / "book-header.tex"
_ENV = r"^\\{command}\{{{name}\}}\{{Verbatim\}}\{{(.*)\}}$"

# The options that make fvextra's Verbatim lay a fitting block out exactly
# as the kernel verbatim did. Each one answers a measured difference:
#   backgroundcolorboxoverlap=0pt   fvextra's -0.25pt \vspace after every
#                                   line (emitted even with no background);
#   tabsize=1                       fancyvrb sets a tab 8 spaces wide, the
#                                   kernel sets it as one space;
#   listparameters={...}            fancyvrb's club/widow penalties around
#                                   a block's first and last line, which
#                                   the kernel's one-line paragraphs lack.
IDENTITY_OPTIONS = {
    "backgroundcolorboxoverlap=0pt",
    "tabsize=1",
    r"listparameters={\clubpenalty=0 \widowpenalty=0 }",
}
BREAK_OPTIONS = {"breaklines", "breakanywhere"}


def _options(command: str, name: str) -> set[str] | None:
    match = re.search(_ENV.format(command=command, name=name), HEADER.read_text("utf-8"), re.M)
    if match is None:
        return None
    return {opt.strip() for opt in match.group(1).split(",") if opt.strip()}


def test_highlighting_breaks_lines():
    options = _options("DefineVerbatimEnvironment", "Highlighting")
    assert options is not None, "Highlighting is no longer defined on fvextra's Verbatim"
    assert BREAK_OPTIONS <= options


def test_plain_verbatim_breaks_lines_like_highlighting():
    verbatim = _options("RecustomVerbatimEnvironment", "verbatim")
    assert verbatim is not None, (
        "plain verbatim is not rebound to fvextra's Verbatim; "
        "an untagged fence would run off the page edge (#279)"
    )
    highlighting = _options("DefineVerbatimEnvironment", "Highlighting") or set()
    # commandchars is pandoc's escape hatch for colour tokens, meaningless in
    # plain verbatim; every break option must match so the two wrap alike.
    breaks = {opt for opt in highlighting if not opt.startswith("commandchars")}
    assert breaks <= verbatim, f"verbatim {sorted(verbatim)} lacks {sorted(breaks - verbatim)}"


def test_plain_verbatim_keeps_the_kernel_spacing():
    verbatim = _options("RecustomVerbatimEnvironment", "verbatim") or set()
    missing = IDENTITY_OPTIONS - verbatim
    assert not missing, (
        f"verbatim is missing {sorted(missing)}: without every identity option a "
        "code block that already fit moves on the page, a design change within v3"
    )
    unexpected = verbatim - IDENTITY_OPTIONS - BREAK_OPTIONS
    assert not unexpected, (
        f"verbatim carries {sorted(unexpected)}, which the pixel-identity proof "
        "has not covered; prove it with the integration runner before adding it"
    )


def test_highlighting_spacing_is_untouched():
    """Tagged fences keep fvextra's default spacing: changing it would move
    every highlighted block in every valid book, which needs a new major."""

    highlighting = _options("DefineVerbatimEnvironment", "Highlighting") or set()
    assert not (IDENTITY_OPTIONS & highlighting), (
        "the kernel-spacing options belong to the plain verbatim rebind only; "
        "applying them to Highlighting restyles tagged fences"
    )
