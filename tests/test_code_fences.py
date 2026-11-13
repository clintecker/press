"""Both kinds of code fence wrap in the PDF (#279) and wear the house
listing design (#293), and the inside of a block sets as the kernel
verbatim would at the same size.

pandoc sets a fence with a recognised language tag in the ``Highlighting``
environment and an untagged fence in plain ``verbatim``. The TeX header
rebinds ``verbatim`` to fvextra's ``Verbatim`` with the line-break options
Highlighting carries, so a long line wraps whether or not the fence names a
language. fvextra's Verbatim does not space lines the way the kernel's
verbatim does, so the rebind also carries the options that restore the
kernel's spacing: without them a fence that already fit would move by half
a point a line. v4 (#293) frames every block, tagged or not, with the same
listing options, so both environments now carry the identity options and
the listing options alike. The rendered proof is the PDF-family integration
runner (two builds, line positions compared and the frame found); this is
the fast, toolchain-free guard on the header text.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

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
#   listparameters={...}            also zeroes \partopsep, so the space
#                                   above a block is the listing's 9pt, and
#                                   keeps a one-line lead-in with the block.
IDENTITY_OPTIONS = {
    "backgroundcolorboxoverlap=0pt",
    "tabsize=1",
    r"listparameters={\partopsep=0pt \clubpenalty=0 \widowpenalty=0 \PressListingLeadIn}",
}
BREAK_OPTIONS = {"breaklines", "breakanywhere"}
# The house listing (#293): \small between two 0.4pt hairlines, 4pt of air
# inside each, 9pt plus 2pt outside.
LISTING_OPTIONS = {
    r"fontsize=\small",
    "frame=lines",
    "framerule=0.4pt",
    "framesep=4pt",
    "vspace=9pt plus 2pt",
}


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
        f"verbatim is missing {sorted(missing)}: without every identity option the "
        "inside of a code block no longer sets as the kernel verbatim would"
    )
    unexpected = verbatim - IDENTITY_OPTIONS - BREAK_OPTIONS - LISTING_OPTIONS
    assert not unexpected, (
        f"verbatim carries {sorted(unexpected)}, which the listing proof "
        "has not covered; prove it with the integration runner before adding it"
    )


@pytest.mark.parametrize(
    ("command", "name"),
    [("DefineVerbatimEnvironment", "Highlighting"), ("RecustomVerbatimEnvironment", "verbatim")],
)
def test_every_code_block_wears_the_house_listing(command, name):
    """A tagged fence and an untagged one are the same listing: \\small
    between hairlines, with the same air (#293)."""

    options = _options(command, name) or set()
    missing = LISTING_OPTIONS - options
    assert not missing, f"{name} lacks the listing options {sorted(missing)}"


def test_tagged_and_untagged_fences_set_alike():
    """Apart from pandoc's escape characters, the two environments carry the
    same options, so a tagged block pitches, wraps, and frames exactly like
    an untagged one."""

    highlighting = _options("DefineVerbatimEnvironment", "Highlighting") or set()
    verbatim = _options("RecustomVerbatimEnvironment", "verbatim") or set()
    assert {o for o in highlighting if not o.startswith("commandchars")} == verbatim


def test_an_older_fvextra_gets_the_rebind_without_the_overlap_key():
    """backgroundcolorboxoverlap is unknown to the pinned toolchain image's
    fvextra (1.6.1), and xkeyval stops the build on an unknown key, so every
    PDF died in the container gauntlet. Both environments are guarded on the
    key existing; the fallback keeps every other option, so a fence still
    wraps and wears the listing there."""

    text = HEADER.read_text("utf-8")
    guard = re.search(
        r"^\\ifcsname KV@FV@backgroundcolorboxoverlap\\endcsname\n(.*?)\n\\else\n(.*?)\n\\fi$",
        text,
        re.M | re.S,
    )
    assert guard is not None, "the overlap option is passed without checking fvextra defines it"
    branches = []
    for body in guard.groups():
        lines = body.split("\n")
        assert len(lines) == 2, f"guard branch is not the two environment definitions: {body!r}"
        high = re.fullmatch(
            _ENV.format(command="DefineVerbatimEnvironment", name="Highlighting"), lines[0]
        )
        plain = re.fullmatch(
            _ENV.format(command="RecustomVerbatimEnvironment", name="verbatim"), lines[1]
        )
        assert high is not None and plain is not None, f"unexpected guard branch: {body!r}"
        branches.append(
            (
                {o.strip() for o in high.group(1).split(",") if o.strip()},
                {o.strip() for o in plain.group(1).split(",") if o.strip()},
            )
        )
    (high_key, plain_key), (high_nokey, plain_nokey) = branches
    assert plain_key == IDENTITY_OPTIONS | BREAK_OPTIONS | LISTING_OPTIONS
    assert plain_nokey == plain_key - {"backgroundcolorboxoverlap=0pt"}
    assert high_nokey == high_key - {"backgroundcolorboxoverlap=0pt"}
