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

    def spine(
        self, pages: int, paper: str | None = None, *, override: float | None = None
    ) -> float:
        """Spine width in inches for ``pages`` on ``paper``. An explicit
        per-page ``override`` (from ``print.page-thickness``) wins over the
        spec's stock table; otherwise the spec's shape decides."""

        spec = self.data["spine"]
        allowance = float(spec.get("paperback-allowance", 0.0))
        if override is not None:
            return pages * float(override) + allowance

        shape = spec["shape"]
        paper = paper or spec.get("default-paper", "cream")
        if shape == "constant":
            return pages * self._stock(spec["calipers"], paper) + allowance
        if shape == "divisor":
            return pages / float(spec["divisor"]) + allowance
        if shape == "ppi-table":
            return pages / self._stock(spec["ppi"], paper)
        if shape == "lookup":
            for low, high, width in spec["table"]:
                if int(low) <= pages <= int(high):
                    return float(width)
            raise SystemExit(
                f"provider {self.id}: no spine band covers {pages} pages"
            )
        raise SystemExit(f"provider {self.id}: unknown spine shape {shape!r}")

    def _stock(self, table: dict, paper: str) -> float:
        if paper not in table:
            known = ", ".join(sorted(table))
            raise SystemExit(
                f"provider {self.id}: unknown paper stock {paper!r}; known: {known}"
            )
        return float(table[paper])


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
