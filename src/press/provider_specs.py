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
        *, override: float | None = None, ink: str = "single",
        color_grade: str | None = None,
    ) -> float:
        """Spine width in inches for ``pages`` on ``paper`` in ``binding``. A
        hardcover binding uses the spec's ``spine.hardcover`` sub-model when it
        has one (e.g. Lulu's stepped lookup table); a soft cover uses the main
        shape plus the paperback allowance. An explicit per-page ``override``
        (``print.page-thickness``) wins over the stock table.

        A ``color`` interior (the design profile's ink, #211) resolves the
        caliper from the spec's declared color stock -- ``spine.color-default``,
        or a ``print.color-grade`` override -- because color stock is a
        different weight; a provider that declares no color caliper does not
        print a color interior and is refused."""

        spec = self.data["spine"]
        hardcover = binding in self._HARDCOVER
        if hardcover and "hardcover" in spec:
            return self._shape_width(spec["hardcover"], pages, paper, ink, color_grade)
        allowance = 0.0 if hardcover else float(spec.get("paperback-allowance", 0.0))
        if override is not None:
            return pages * float(override) + allowance
        return self._shape_width(spec, pages, paper, ink, color_grade) + allowance

    def _shape_width(self, shape: dict, pages: int, paper: str | None,
                     ink: str = "single", color_grade: str | None = None) -> float:
        kind = shape["shape"]
        if ink == "color":
            stock = color_grade or shape.get("color-default")
            if stock is None:
                raise SystemExit(
                    f"provider {self.id}: no color-interior caliper "
                    "(spine.color-default); it does not print a color interior. "
                    "Select a color-capable provider or a single-ink profile.")
            if kind == "constant":
                return pages * self._stock(shape["calipers"], stock)
            if kind == "ppi-table":
                return pages / self._stock(shape["ppi"], stock)
            raise SystemExit(
                f"provider {self.id}: a {kind!r} spine has no color caliper model")
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

    def supports_color(self, binding: str = "perfect-bound") -> bool:
        """Whether this provider declares a color-interior caliper for the
        spine shape this binding uses -- i.e. whether it prints a color
        interior at all (#213)."""

        spec = self.data["spine"]
        hardcover = binding in self._HARDCOVER
        shape = spec["hardcover"] if (hardcover and "hardcover" in spec) else spec
        return (shape.get("shape") in {"constant", "ppi-table"}
                and shape.get("color-default") is not None)

    def supported_inks(self, binding: str = "perfect-bound") -> tuple[str, ...]:
        """The interior inks this provider prints for this binding: always
        ``single`` (black), plus ``color`` when it declares a color caliper
        for the spine shape the binding uses (#222). This is the ink axis of
        the trim/ink support matrix; the trim axis is ``trims``."""

        return ("single", "color") if self.supports_color(binding) else ("single",)

    def support_matrix(self) -> list[dict[str, Any]]:
        """The trim/ink support view: one row per offered trim, each naming
        the bindings the provider cuts it in and the inks it prints across
        those bindings (#222). A spec with no ``trims`` table (the house spec)
        declares no catalog and returns an empty view, imposing no limits."""

        rows: list[dict[str, Any]] = []
        for trim in self.data.get("trims") or []:
            bindings = list(trim.get("bindings") or [])
            inks = sorted({
                ink for binding in bindings for ink in self.supported_inks(binding)
            })
            rows.append({
                "width": float(trim["width"]),
                "height": float(trim["height"]),
                "bindings": bindings,
                "inks": inks,
            })
        return rows

    def check_selection(
        self, trim_w: float, trim_h: float, binding: str, pages: int | None = None,
        *, ink: str = "single",
    ) -> list[str]:
        """Every reason this provider cannot make this book, or an empty list.
        A spec with no ``trims`` or ``pages`` tables (the house spec) imposes no
        limits; a real vendor spec refuses a trim it does not cut, a binding it
        does not offer for that trim, a page count outside the binding's range,
        and a color interior it does not print -- all before any expensive
        rendering (#172, #213)."""

        problems: list[str] = []
        if ink == "color" and not self.supports_color(binding):
            problems.append(
                f"provider {self.id!r} does not print a color interior")
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
