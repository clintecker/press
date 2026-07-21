"""Provider manufacturing specs: the per-vendor numbers that turn a book's
page count and paper stock into a spine width and a cover-wrap geometry.

The spine is not one formula across vendors -- it is one of several shapes,
because the printers do not run the same stocks or round the same way:

- ``constant``  -- ``pages * caliper[stock] + allowance`` (KDP).
- ``divisor``   -- ``pages / divisor + allowance`` (Lulu paperback,
  stock-independent).
- ``ppi-table`` -- ``pages / ppi[stock]`` (IngramSpark).
- ``lookup``    -- a stepped table keyed by a page-count band (Lulu hardcover).

The house spec reproduces v1's coverwrap exactly and is the compatibility
baseline; Lulu, KDP, and IngramSpark specs (added in later stages) carry each
vendor's own calipers, allowances, and wrap geometry. Selecting a provider
selects its verification contract (#172). See docs/PRINT-PROFILES-PLAN.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import booklib, yamlio

HOUSE = "house"


@dataclass(frozen=True)
class ProviderSpec:
    """One resolved provider spec: its id and validated document."""

    id: str
    data: dict[str, Any]

    @property
    def bleed(self) -> float:
        return float(self.data["cover"]["bleed"])

    _HARDCOVER = frozenset({"casewrap", "dust-jacket"})

    def spine(
        self, pages: int, paper: str | None = None, binding: str = "perfect-bound",
        *, override: float | None = None,
    ) -> float:
        """Spine width in inches for ``pages`` on ``paper`` in ``binding``. A
        hardcover binding uses the spec's ``spine.hardcover`` sub-model when it
        has one (e.g. Lulu's stepped lookup table); a soft cover uses the main
        shape plus the paperback allowance. An explicit per-page ``override``
        (``print.page-thickness``) wins over the stock table."""

        spec = self.data["spine"]
        hardcover = binding in self._HARDCOVER
        if hardcover and "hardcover" in spec:
            return self._shape_width(spec["hardcover"], pages, paper)
        allowance = 0.0 if hardcover else float(spec.get("paperback-allowance", 0.0))
        if override is not None:
            return pages * float(override) + allowance
        return self._shape_width(spec, pages, paper) + allowance

    def _shape_width(self, shape: dict, pages: int, paper: str | None) -> float:
        kind = shape["shape"]
        paper = paper or shape.get("default-paper", "cream")
        if kind == "constant":
            return pages * self._stock(shape["calipers"], paper)
        if kind == "divisor":
            return pages / float(shape["divisor"])
        if kind == "ppi-table":
            return pages / self._stock(shape["ppi"], paper)
        if kind == "lookup":
            for low, high, width in shape["table"]:
                if int(low) <= pages <= int(high):
                    return float(width)
            raise SystemExit(f"provider {self.id}: no spine band covers {pages} pages")
        raise SystemExit(f"provider {self.id}: unknown spine shape {kind!r}")

    def _stock(self, table: dict, paper: str) -> float:
        if paper not in table:
            known = ", ".join(sorted(table))
            raise SystemExit(
                f"provider {self.id}: unknown paper stock {paper!r}; known: {known}"
            )
        return float(table[paper])

    def check_selection(
        self, trim_w: float, trim_h: float, binding: str, pages: int | None = None
    ) -> list[str]:
        """Every reason this provider cannot make this book, or an empty list.
        A spec with no ``trims`` or ``pages`` tables (the house spec) imposes no
        limits; a real vendor spec refuses a trim it does not cut, a binding it
        does not offer for that trim, and a page count outside the binding's
        range -- all before any expensive rendering (#172)."""

        problems: list[str] = []
        trims = self.data.get("trims")
        if trims is not None:
            match = next(
                (t for t in trims
                 if abs(float(t["width"]) - trim_w) < 0.01
                 and abs(float(t["height"]) - trim_h) < 0.01),
                None,
            )
            if match is None:
                problems.append(
                    f"provider {self.id!r} does not offer a {trim_w:g} x {trim_h:g} trim"
                )
            elif binding not in (match.get("bindings") or []):
                offered = ", ".join(match.get("bindings") or [])
                problems.append(
                    f"provider {self.id!r} does not offer {trim_w:g} x {trim_h:g} "
                    f"in {binding!r} (offers: {offered})"
                )
        if pages is not None:
            bounds = (self.data.get("pages") or {}).get(binding)
            if bounds:
                low, high = bounds.get("min"), bounds.get("max")
                if low is not None and pages < int(low):
                    problems.append(
                        f"provider {self.id!r}: {binding} needs at least {low} pages "
                        f"({pages} is too few)"
                    )
                if high is not None and pages > int(high):
                    problems.append(
                        f"provider {self.id!r}: {binding} allows at most {high} pages "
                        f"({pages} is too many)"
                    )
        return problems


def specs_dir() -> Path:
    return booklib.DATA / "provider-specs"


def load(name: str | None = None) -> ProviderSpec:
    """Resolve a provider spec by id, defaulting to the house spec. An unknown
    id is refused before rendering, naming what is available."""

    name = name or HOUSE
    path = specs_dir() / f"{name}.yaml"
    if not path.is_file():
        available = ", ".join(sorted(p.stem for p in specs_dir().glob("*.yaml")))
        raise SystemExit(f"unknown provider spec {name!r}; available: {available}")
    return ProviderSpec(name, yamlio.load(path))


def active() -> ProviderSpec:
    """The provider spec a book selects (``print.provider``), or the house."""

    meta = booklib.metadata()
    return load((meta.get("print") or {}).get("provider"))
