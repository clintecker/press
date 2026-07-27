"""Read the illustrations an author declares in the manuscript, with their
kind, their art-direction description, and how they sit on the page.

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

The same image attributes carry the hardened *placement* vocabulary -- a
relative, parity-aware grammar so one manuscript typesets on any trim::

    ![The press at work](assets/fig/press.jpg){#fig:press .figure
        width=half-measure place=wrap-outer outset=1em fig-alt="A hand press,
        the platen raised, a sheet on the tympan"}

``width`` is measured against the line (``full``/``half``/``third-measure``),
never in inches; ``place`` names the parity-aware side (``wrap-inner`` /
``wrap-outer``, never left/right); ``outset`` is the runaround gap; ``fig-alt``
is the accessible alt text (a fourth field, distinct from the visible caption,
the ``art:`` prompt, and any credit line); ``decorative`` marks an ornament
that takes an empty alt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Kinds an image model may draw, and kinds that route away from it.
GENERATABLE_KINDS = ("plate", "figure", "map", "photo")
DATA_KINDS = ("chart", "diagram")
DEFAULT_KIND = "figure"

# The hardened figure-placement vocabulary (a new major). It rides on the
# image's pandoc attributes and is RELATIVE, never absolute: a book that
# names a placement names it against the measure and the page's parity, never
# in inches or left/right, so the same manuscript typesets on any trim.

# Where a figure sits. ``inline`` runs in the text column; ``wrap-inner`` /
# ``wrap-outer`` run text around it on the parity-aware side (never
# left/right); ``plate`` is the unnumbered woodcut float; ``frontispiece``
# faces a chapter; ``full-bleed`` fills the page; ``margin`` sits in the
# outer margin.
PLACES = (
    "inline",
    "wrap-inner",
    "wrap-outer",
    "plate",
    "frontispiece",
    "full-bleed",
    "margin",
)
# The places that run in the text flow and may therefore carry a width
# measure; a plate/frontispiece/full-bleed owns its own geometry and may not.
INFLOW_PLACES = ("inline", "wrap-inner", "wrap-outer", "margin")
# The relative widths an in-flow figure may take, measured against the line.
MEASURES = ("full-measure", "half-measure", "third-measure")
# The fraction of the measure each names, for the graphics width the writer
# emits (portable across PDF and HTML).
MEASURE_FRACTION = {
    "full-measure": "100%",
    "half-measure": "50%",
    "third-measure": "33%",
}

# The informative kinds that, when a figure DECLARES one explicitly, earn a
# "Figure N" number and a place in the List of Figures. A plate never does
# (the literary woodcut idiom keeps it unnumbered), and a bare image with no
# declared kind stays an unnumbered plate too, so a book that names no
# numbered figure typesets byte-for-byte as before.
NUMBERED_KINDS = ("figure", "chart", "map", "photo", "diagram")

_ABSOLUTE_LENGTH = re.compile(r"^\d+(\.\d+)?(pt|px|in|cm|mm|%)$")
_RELATIVE_OUTSET = re.compile(r"^\d+(\.\d+)?em$")

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

# Pandoc attribute tokens: #id, .class, and key=value (value optionally
# quoted, and free to contain spaces when quoted).
_ATTR_TOKEN = re.compile(
    r"""(?:\#(?P<id>[^\s"']+))
      | (?:\.(?P<cls>[^\s"'.]+))
      | (?P<key>[A-Za-z][\w-]*)\s*=\s*(?:"(?P<qv>[^"]*)"|'(?P<sv>[^']*)'|(?P<uv>[^\s"']+))
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class Figure:
    """One declared illustration: where it lives, what it is captioned, its
    kind, the illustrate style it asks for, the directive that says what to
    draw (or that it must not be drawn at all), and how it sits on the page."""

    src: str
    caption: str
    kind: str
    style: str | None
    directive: str  # "art" | "data" | "source" | ""
    description: str | None  # the directive body, whitespace-normalized
    identifier: str | None = None  # the #id, for a "see Figure N" cross-ref
    width: str | None = None  # full-/half-/third-measure (or a raw length)
    place: str | None = None  # one of PLACES
    outset: str | None = None  # the runaround gap, a relative length in em
    alt: str | None = None  # fig-alt: the accessible alt text
    decorative: bool = False  # an ornament: alt="" / role=presentation
    kind_declared: bool = False  # was .kind spelled, or is this a bare image?

    @property
    def generatable(self) -> bool:
        """True only for a plate/figure/map/photo that carries an explicit
        ``art:`` description. A generatable kind with no ``art:`` is NOT
        generatable: the press must never draw the caption's words in its
        place (#225). A ``chart``/``diagram`` is never generatable here -- it
        renders from data or an author file."""

        return self.kind in GENERATABLE_KINDS and self.directive == "art"

    @property
    def numbered(self) -> bool:
        """True when this figure earns a "Figure N" number and a List of
        Figures entry: an explicitly declared informative kind that is not a
        plate and not decorative. A bare image (no ``.kind``) stays an
        unnumbered plate, so a book that declares no numbered figure is
        unchanged."""

        return self.kind_declared and self.kind in NUMBERED_KINDS and not self.decorative


def _parse_attrs(attrs: str) -> dict[str, object]:
    """The kind, style, identifier, and placement vocabulary out of a pandoc
    attribute string. A bare image with no attributes is a ``figure`` with no
    style and no declared kind."""

    identifier: str | None = None
    kind: str | None = None
    style: str | None = None
    keys: dict[str, str] = {}
    for match in _ATTR_TOKEN.finditer(attrs):
        if match.group("id"):
            identifier = match.group("id")
        elif match.group("cls"):
            if kind is None:  # the first .class is the kind
                kind = match.group("cls")
        else:
            value = match.group("qv")
            if value is None:
                value = match.group("sv")
            if value is None:
                value = match.group("uv") or ""
            keys[match.group("key")] = value
    if "style" in keys:
        style = keys["style"] or None
    decorative = keys.get("decorative", "").lower() in ("true", "yes", "1")
    return {
        "identifier": identifier,
        "kind": kind if kind is not None else DEFAULT_KIND,
        "kind_declared": kind is not None,
        "style": style,
        "width": keys.get("width") or None,
        "place": keys.get("place") or None,
        "outset": keys.get("outset") or None,
        "alt": keys.get("fig-alt") or None,
        "decorative": decorative,
    }


def parse(markdown: str) -> list[Figure]:
    """Every figure declared in a manuscript, in source order, with its kind,
    style, art-direction description, and placement. All of the attributes are
    optional -- a bare ``![…](…)`` is an unnumbered ``figure`` with no
    directive and no placement."""

    figures: list[Figure] = []
    for match in _FIGURE_RE.finditer(markdown):
        attrs = _parse_attrs(match.group("attrs") or "")
        body = match.group("body")
        figures.append(
            Figure(
                src=match.group("src").strip(),
                caption=match.group("caption").strip(),
                kind=str(attrs["kind"]),
                style=attrs["style"],  # type: ignore[arg-type]
                directive=match.group("key") or "",
                description=" ".join(body.split()) if body else None,
                identifier=attrs["identifier"],  # type: ignore[arg-type]
                width=attrs["width"],  # type: ignore[arg-type]
                place=attrs["place"],  # type: ignore[arg-type]
                outset=attrs["outset"],  # type: ignore[arg-type]
                alt=attrs["alt"],  # type: ignore[arg-type]
                decorative=bool(attrs["decorative"]),
                kind_declared=bool(attrs["kind_declared"]),
            )
        )
    return figures


def validate(figures: list[Figure]) -> list[str]:
    """Every way a figure's placement vocabulary is malformed, as located
    messages. The vocabulary is relative and parity-aware by law: a ``place``
    outside the grammar, a left/right side, an absolute width where a measure
    belongs, an ``outset`` that is not a relative em gap, a measure on a
    plate, or a decorative image that still carries alt text are all
    refused here, before pandoc or TeX ever runs."""

    problems: list[str] = []
    for fig in figures:
        where = fig.src
        place = fig.place
        if place is not None and place not in PLACES:
            if place in ("left", "right", "inner", "outer", "wrap-left", "wrap-right"):
                problems.append(
                    f"{where}: place={place} is not parity-aware; use "
                    "wrap-inner or wrap-outer, never left/right"
                )
            else:
                problems.append(f"{where}: unknown place={place} (use one of {', '.join(PLACES)})")
        width = fig.width
        if width is not None:
            if width.endswith("-measure") and width not in MEASURES:
                problems.append(
                    f"{where}: unknown width measure {width} (use one of {', '.join(MEASURES)})"
                )
            elif width in MEASURES and place is not None and place not in INFLOW_PLACES:
                problems.append(
                    f"{where}: a width measure applies to an in-flow figure, "
                    f"not place={place}; a {place} owns its own geometry"
                )
            elif _ABSOLUTE_LENGTH.match(width) and place in INFLOW_PLACES:
                problems.append(
                    f"{where}: width={width} is absolute; an in-flow figure "
                    "takes a relative measure (full-/half-/third-measure)"
                )
        if fig.outset is not None and not _RELATIVE_OUTSET.match(fig.outset):
            problems.append(
                f"{where}: outset={fig.outset} is not a relative gap; the "
                "runaround gap is a length in em (e.g. 1em)"
            )
        if fig.decorative and fig.alt:
            problems.append(
                f"{where}: a decorative image takes an empty alt; drop either "
                "fig-alt or decorative=true, not both"
            )
    return problems


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
        "identifier": fig.identifier,
        "width": fig.width,
        "place": fig.place,
        "outset": fig.outset,
        "alt": fig.alt,
        "decorative": fig.decorative,
        "numbered": fig.numbered,
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
