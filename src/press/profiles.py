"""Print profiles: the versioned bundle that defines a book's physical form.

A profile carries the trim, interior geometry, paper and spine laws, and
cover grammar that v1 sealed inline in its TeX header and cover generator.
Modelling them as named, versioned data is the v2 move (#172): selecting a
profile selects its verification contract, and appearance cannot change
without a profile identity or design-major change.

The v1 house profile (``house-6x9-paperback``) reproduces the sealed v1
output exactly and is the baseline every other profile is diffed against.
This module loads a profile and projects its interior geometry into a small
TeX fragment the reading and print builds include after the house header, so
a profile's trim and margins override the header defaults with no change to
a valid v1 book (whose profile carries the same numbers).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import booklib, yamlio

HOUSE = "house-6x9-paperback"


@dataclass(frozen=True)
class Profile:
    """One resolved print profile: its id and the validated document."""

    id: str
    data: dict[str, Any]

    @property
    def trim(self) -> tuple[float, float]:
        trim = self.data["trim"]
        return float(trim["width"]), float(trim["height"])

    @property
    def binding(self) -> str:
        return str(self.data["binding"])

    @property
    def figure_cap(self) -> float:
        return float(self.data["interior"]["figure-cap"])

    @property
    def margins(self) -> dict[str, float]:
        return {k: float(v) for k, v in self.data["interior"]["margins"].items()}


def profiles_dir() -> Path:
    return booklib.DATA / "profiles"


def load(name: str | None = None) -> Profile:
    """Resolve a profile by id, defaulting to the house profile. An unknown
    id is refused before any expensive rendering (#172)."""

    name = name or HOUSE
    path = profiles_dir() / f"{name}.yaml"
    if not path.is_file():
        available = ", ".join(sorted(p.stem for p in profiles_dir().glob("*.yaml")))
        raise SystemExit(f"unknown print profile {name!r}; available: {available}")
    return Profile(name, yamlio.load(path))


def active() -> Profile:
    """The profile a book selects (``print.profile``), or the house profile."""

    meta = booklib.metadata()
    print_cfg = meta.get("print") or {}
    return load(print_cfg.get("profile"))


def geometry_tex(profile: Profile) -> str:
    """The interior geometry fragment for a profile: a ``\\geometry`` override
    and the figure-cap macro. Included after the house header, so the house
    profile's identical values are a no-op and any other profile changes the
    page. Values render with %g so an integer trim reads ``6in``, not
    ``6.0in`` -- byte-for-byte what the v1 header carried."""

    width, height = profile.trim
    m = profile.margins
    return (
        f"\\geometry{{paperwidth={width:g}in,paperheight={height:g}in,"
        f"inner={m['inner']:g}in,outer={m['outer']:g}in,"
        f"top={m['top']:g}in,bottom={m['bottom']:g}in,"
        f"headsep={m['headsep']:g}in,footskip={m['footskip']:g}in}}\n"
        f"\\renewcommand{{\\PressFigureCap}}{{{profile.figure_cap:g}in}}\n"
    )


def write_geometry_tex(profile: Profile, out: Path) -> Path:
    """Materialize the geometry fragment for a build into ``out``."""

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(geometry_tex(profile), encoding="utf-8")
    return out
