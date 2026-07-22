"""The semantic layer of a chapter-opening drop cap.

A drop cap is a design decision, not markup an author writes: the manuscript
stays ordinary prose, and the pipeline decides the initial. The decision has
two halves. This module is the renderer-independent half -- given the text of
a chapter's opening paragraph, it splits off the piece a drop cap acts on:
any leading punctuation the initial should keep (an opening quote, a dash),
the initial itself as a Unicode *grapheme cluster* (a base letter with its
combining marks, never a bare code point that would strand an accent), the
remainder of the first word (which a design may set in small caps), and the
rest of the paragraph that flows beside and below the initial.

The other half -- finding the first eligible paragraph after a chapter
heading and emitting ``\\lettrine`` or a ``<span>`` -- is the Lua filter
``data/lua/chapter-dropcap.lua``, which mirrors ``split_initial`` on the
pandoc AST. This module is the specification that mirror is tested against.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

# Leading characters a drop cap keeps in front of its initial: quotation
# marks, dashes, and the inverted marks that open a sentence in some
# languages. Kept as a set of the ones that actually occur so a stray symbol
# does not get swept into the cap.
_LEAD = set("\"'`‘’“”«»‹›"
            "—–‒‐-¿¡")


# The chapter-opening styles a profile may request. "none" is the default and
# a no-op: a book that does not opt in renders byte-for-byte as before.
STYLES = ("none", "drop-cap", "raised-cap")


@dataclass(frozen=True)
class Settings:
    """The resolved chapter-opening treatment: the style, how many text lines
    the initial spans, extra depth for a descender, and whether the rest of
    the first word is set in small caps. ``none`` disables the feature."""

    style: str = "none"
    lines: int = 3
    depth: int = 0
    small_caps_remainder: bool = True

    @property
    def enabled(self) -> bool:
        return self.style != "none"


def settings(
    profile_opening: dict | None, book_override: dict | None = None
) -> Settings:
    """Resolve the effective chapter-opening settings: the profile carries the
    design default; a book may override it (the design-major seals the profile,
    but a book opts its own chapters in or out). An unknown style is refused
    before any rendering, the same way an unknown profile is."""

    merged = {**(profile_opening or {}), **(book_override or {})}
    style = str(merged.get("style", "none"))
    if style not in STYLES:
        raise SystemExit(
            f"unknown chapter-opening style {style!r}; one of: {', '.join(STYLES)}"
        )
    return Settings(
        style=style,
        lines=int(merged.get("lines", 3)),
        depth=int(merged.get("depth", 0)),
        small_caps_remainder=bool(merged.get("small-caps-remainder", True)),
    )


def tex_setup(settings: Settings) -> str:
    """The centralized LaTeX style layer for the drop cap, or an empty string
    when the feature is off. Loading and macro live here, not scattered
    through the document: the Lua filter emits only ``\\PressDropCap{I}{he}``,
    and this defines what that means -- the line span, the descender depth, the
    small-cap remainder, and a needspace guard so a chapter opening is never
    stranded at the foot of a page with no room for the initial."""

    if not settings.enabled:
        return ""
    remainder_font = r"\scshape" if settings.small_caps_remainder else ""
    reserve = settings.lines + settings.depth + 1
    return (
        "\\usepackage{lettrine}\n"
        f"\\newcommand{{\\PressDropCap}}[2]{{%\n"
        f"  \\Needspace*{{{reserve}\\baselineskip}}%\n"
        f"  \\lettrine[lines={settings.lines},depth={settings.depth},"
        "findent=2pt,nindent=0pt]{#1}{" + remainder_font + " #2}}\n"
    )


@dataclass(frozen=True)
class Opening:
    """A chapter opening split for the renderer. ``initial`` is a grapheme
    cluster; ``lead`` is the punctuation before it; ``word_remainder`` is the
    rest of the first word; ``rest`` is everything after the first word,
    including the leading space."""

    lead: str
    initial: str
    word_remainder: str
    rest: str

    @property
    def is_empty(self) -> bool:
        return self.initial == ""


def _grapheme_at(text: str, start: int) -> int:
    """The index one past the grapheme cluster beginning at ``start``: the
    base character plus any trailing combining marks. This is the narrow slice
    of grapheme segmentation a drop-cap initial needs -- a letter and its
    accents -- without a full ICU dependency."""

    end = start + 1
    while end < len(text) and unicodedata.combining(text[end]):
        end += 1
    return end


def split_initial(text: str) -> Opening:
    """Split the opening text into (lead, initial grapheme, word remainder,
    rest). Leading whitespace is dropped; leading punctuation is kept with the
    initial; an accented initial stays whole; text with no letter to cap
    returns an empty opening the caller renders unchanged."""

    stripped = text.lstrip()
    n = len(stripped)

    i = 0
    while i < n and stripped[i] in _LEAD:
        i += 1
    lead = stripped[:i]

    if i >= n or not stripped[i].isalnum():
        # Nothing but punctuation (or the first real character is itself
        # punctuation, like an ellipsis): there is no letter to drop.
        return Opening(lead="", initial="", word_remainder="", rest=text)

    end = _grapheme_at(stripped, i)
    initial = stripped[i:end]

    j = end
    while j < n and not stripped[j].isspace():
        j += 1
    word_remainder = stripped[end:j]
    rest = stripped[j:]
    return Opening(lead=lead, initial=initial, word_remainder=word_remainder, rest=rest)
