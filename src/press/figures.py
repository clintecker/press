"""Read the illustrations an author declares in the manuscript, with their
kind and their art-direction description.

A figure is a reader-facing image, but the words that caption it and the words
that *direct* it are different things: a caption is a label, an art-direction
description says what the picture depicts and how (#225). So the manuscript
carries both, separately. The kind rides on the image's pandoc attributes and
the description rides in the comment that follows it::

    ![A compositor at the case](assets/fig/compositor.jpg){.plate style=wood-engraving}
    <!-- art: a compositor's left hand holding a brass composing stick, thumb
         setting the measure; type in the case behind; 19th-c workshop, high
         contrast line, no lettering -->

The *kind* decides the treatment. ``plate``/``figure``/``map``/``photo`` are
drawn by an image model from their ``art:`` description; ``chart``/``diagram``
are rendered from ``data:`` or an author ``source:`` file and are **never**
handed to a model. A generatable kind that carries no ``art:`` description is
deliberately not generatable -- the press must never fall back to drawing the
caption's own words, which is exactly the mistake that produced literal, silly
plates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Kinds an image model may draw, and kinds that route away from it.
GENERATABLE_KINDS = ("plate", "figure", "map", "photo")
DATA_KINDS = ("chart", "diagram")
DEFAULT_KIND = "figure"

# An image, its optional {.kind style=…} attributes, and the optional
# art:/data:/source: directive comment that immediately follows it (one blank
# line tolerated). The directive body runs to the first ``-->``.
_FIGURE_RE = re.compile(
    r"!\[(?P<caption>[^\]]*)\]\((?P<src>[^)]+)\)"
    r"(?:\{(?P<attrs>[^}]*)\})?"
    r"(?:(?:[ \t]*\r?\n){1,2}[ \t]*<!--[ \t]*"
    r"(?P<key>art|data|source)[ \t]*:(?P<body>.*?)-->)?",
    re.DOTALL,
)


@dataclass(frozen=True)
class Figure:
    """One declared illustration: where it lives, what it is captioned, its
    kind, the illustrate style it asks for, and the directive that says what to
    draw (or that it must not be drawn at all)."""

    src: str
    caption: str
    kind: str
    style: str | None
    directive: str            # "art" | "data" | "source" | ""
    description: str | None   # the directive body, whitespace-normalized

    @property
    def generatable(self) -> bool:
        """True only for a plate/figure/map/photo that carries an explicit
        ``art:`` description. A generatable kind with no ``art:`` is NOT
        generatable: the press must never draw the caption's words in its
        place (#225). A ``chart``/``diagram`` is never generatable here -- it
        renders from data or an author file."""

        return self.kind in GENERATABLE_KINDS and self.directive == "art"


def _parse_attrs(attrs: str) -> tuple[str, str | None]:
    """The kind (from the first ``.class``) and the illustrate style (from
    ``style=…``) out of a pandoc attribute string. A bare image with no
    attributes is a ``figure`` with no style."""

    kind, style = DEFAULT_KIND, None
    for token in attrs.split():
        if token.startswith(".") and len(token) > 1:
            kind = token[1:]
        elif token.startswith("style="):
            style = token[len("style="):].strip("\"'") or None
    return kind, style


def parse(markdown: str) -> list[Figure]:
    """Every figure declared in a manuscript, in source order, with its kind,
    style, and art-direction description. Kind and style come from the image's
    pandoc attributes; the description comes from the ``art:``/``data:``/
    ``source:`` comment that follows it. Both are optional -- a bare ``![…](…)``
    is a ``figure`` with no directive."""

    figures: list[Figure] = []
    for match in _FIGURE_RE.finditer(markdown):
        kind, style = _parse_attrs(match.group("attrs") or "")
        body = match.group("body")
        figures.append(Figure(
            src=match.group("src").strip(),
            caption=match.group("caption").strip(),
            kind=kind,
            style=style,
            directive=match.group("key") or "",
            description=" ".join(body.split()) if body else None,
        ))
    return figures


def as_dict(fig: Figure) -> dict[str, object]:
    """One figure as a plain mapping, for JSON hand-off to a workflow that reads
    the author's ``art:`` descriptions instead of re-parsing markdown by eye."""

    return {
        "src": fig.src,
        "caption": fig.caption,
        "kind": fig.kind,
        "style": fig.style,
        "directive": fig.directive,
        "description": fig.description,
        "generatable": fig.generatable,
    }


def main(argv: list[str]) -> int:
    """Print every figure declared across the manuscript as JSON: the one
    authoritative reading of what the author asked to be drawn (kind, style, and
    ``art:`` description), so a tool never has to guess it from a caption (#225)."""

    import json

    from . import booklib

    root = booklib.root()
    records: list[dict[str, object]] = []
    for path in booklib.chapter_files():
        rel = str(path.relative_to(root))
        for fig in parse(path.read_text(encoding="utf-8")):
            records.append({"file": rel, **as_dict(fig)})
    print(json.dumps(records, indent=2))
    return 0
