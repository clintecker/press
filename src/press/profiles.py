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

HOUSE = "house-6x9"


@dataclass(frozen=True)
class Profile:
    """One resolved design profile: its id and the validated document. A
    design profile is the interior look only (trim, geometry, typography);
    binding, material, and provider are separate selections that compose with
    it, so a design is not tied to one manufacturer (see
    docs/PRINT-PROFILES-PLAN.md)."""

    id: str
    data: dict[str, Any]

    @property
    def trim(self) -> tuple[float, float]:
        trim = self.data["trim"]
        return float(trim["width"]), float(trim["height"])

    @property
    def figure_cap(self) -> float:
        return float(self.data["interior"]["figure-cap"])

    @property
    def margins(self) -> dict[str, float]:
        return {k: float(v) for k, v in self.data["interior"]["margins"].items()}

    @property
    def typography(self) -> dict[str, Any]:
        """The interior's structural type treatment -- paragraph indent and
        leading. This is design, sealed by the profile's major; the font
        *family* and colours are the book's own identity, carried by the
        aesthetic, which overrides this fragment (it is included after)."""

        return self.data["interior"]["typography"]

    @property
    def web(self) -> dict[str, Any]:
        """The web reading measure and scale: the max line length, base font
        size, and line height. Palette and font family stay with the
        aesthetic; this is the structural web design the profile seals."""

        return self.data["web"]

    @property
    def chapter_opening(self) -> dict[str, Any]:
        """The chapter-opening treatment (a drop or raised initial), or the
        ``none`` default. Design, sealed by the profile major; a book may
        override it for its own chapters. Absent, the feature is off and the
        book renders unchanged."""

        return self.data.get("chapter-opening") or {"style": "none"}


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
    t = profile.typography
    return (
        f"\\geometry{{paperwidth={width:g}in,paperheight={height:g}in,"
        f"inner={m['inner']:g}in,outer={m['outer']:g}in,"
        f"top={m['top']:g}in,bottom={m['bottom']:g}in,"
        f"headsep={m['headsep']:g}in,footskip={m['footskip']:g}in}}\n"
        f"\\renewcommand{{\\PressFigureCap}}{{{profile.figure_cap:g}in}}\n"
        f"\\setlength{{\\parindent}}{{{t['indent']}}}\n"
        f"\\linespread{{{float(t['leading']):g}}}\n"
    )


def web_css(profile: Profile) -> str:
    """The web reading measure for a profile, as a ``body`` override appended
    after the house reader stylesheet. The house profile's values match the
    stylesheet, so it -- and any profile that shares them -- appends nothing
    and the CSS is byte-for-byte unchanged; a profile with a different measure
    overrides the three properties and nothing else, so the palette and font
    the aesthetic controls are untouched."""

    house = load(HOUSE).web
    web = profile.web
    if all(web.get(k) == house.get(k) for k in ("measure", "base-size", "line-height")):
        return ""
    return (
        "\n/* print profile: reading measure */\n"
        "body {\n"
        f"  max-width: {web['measure']};\n"
        f"  font-size: {web['base-size']}; line-height: {float(web['line-height']):g};\n"
        "}\n"
    )


def digest(profile: Profile) -> str:
    """A stable short hash over a profile's design-affecting data. Two loads
    of the same profile produce the same digest; changing any sealed value --
    a margin, the leading, the web measure -- changes it. A visual baseline is
    keyed by this digest and the design major, so a design cannot change under
    a book's feet without the key moving and the baseline being renewed."""

    import hashlib
    import json

    payload = {
        "id": profile.id,
        "design-major": profile.data.get("design-major"),
        "trim": profile.data.get("trim"),
        "interior": profile.data.get("interior"),
        "web": profile.data.get("web"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def write_geometry_tex(profile: Profile, out: Path) -> Path:
    """Materialize the geometry fragment for a build into ``out``."""

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(geometry_tex(profile), encoding="utf-8")
    return out
