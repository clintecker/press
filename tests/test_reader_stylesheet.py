"""Invariants of the house reading stylesheet (src/press/data/web/reader.css).

A book's reader page is CSS the press ships, so a defect here distorts every
book at once. These guard the specific regressions that have bitten: a plate
forced to a fixed shape.
"""

from __future__ import annotations

import re
from pathlib import Path

READER_CSS = (Path(__file__).resolve().parent.parent
              / "src" / "press" / "data" / "web" / "reader.css")


def _rule_body(css: str, selector: str) -> str:
    """The declaration block for the first rule whose selector matches, with
    comments stripped so a property named in a comment does not count."""

    no_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", no_comments)
    assert match, f"reader.css has no `{selector}` rule"
    return match.group(1)


def test_plates_are_not_forced_to_a_fixed_aspect_ratio():
    """A plate must render at its own intrinsic ratio. The sheet once set
    `aspect-ratio: 2/3` on every `figure img` -- a portrait cover shape -- and
    with no object-fit that stretched any plate that was not 2:3: make-ready's
    landscape engravings (2528x1696) were crushed into a tall box. `height:
    auto` against the natural width is the true ratio; a fixed aspect-ratio
    here reintroduces the distortion for any non-matching plate."""

    body = _rule_body(READER_CSS.read_text(encoding="utf-8"), "figure img")
    assert "aspect-ratio" not in body, (
        "figure img pins an aspect-ratio; a plate that is not that ratio will "
        "be stretched. Let height:auto give each plate its intrinsic ratio."
    )


def test_plate_images_stay_within_the_column():
    """Whatever else changes, a plate never overflows the reading column."""

    body = _rule_body(READER_CSS.read_text(encoding="utf-8"), "figure img")
    assert "max-width" in body and "100%" in body, \
        "figure img must cap at max-width:100% so a wide plate cannot overflow"
