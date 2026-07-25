"""The print-profile lifecycle: scaffold, prove, seal.

Adding a trim or an ink to the press is adding a *profile* (``profiles.py``),
not editing the pipeline. This module makes that one path repeatable and
stamped, so every new physical form is a proven artifact rather than an ad
hoc edit (#221):

1. **Scaffold** a new profile YAML from an existing one, overriding only the
   trim (and optionally the ink), so a new profile starts from proven
   geometry instead of a blank file. ``scaffold`` produces the text;
   ``write_scaffold`` lays it into ``data/profiles/`` without clobbering.
2. **Prove** it with a golden-copy inspection: the toolchain renders the
   profile and its own declared numbers are the oracle (the geometry proof in
   ``tests/test_profiles.py`` parametrizes over every shipped profile, so a
   newly-scaffolded one is covered the moment it exists).
3. **Seal** it under the design contract: ``seal`` records the profile's
   design-affecting digest (``profiles.digest``) and its design-major in the
   ledger. From then on the selftest gate (``validate``) turns red if the
   profile's geometry drifts from its sealed digest -- appearance cannot
   change without a deliberate re-seal, exactly the design-major law the
   contract states.

The ledger is package data (``data/profile-seals.yaml``), one copy, shipped
in the wheel so the gate holds from an installed press too. The document
side of the lifecycle is ``docs/PROFILE-LIFECYCLE.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import booklib, profiles, yamlio

SEALS = booklib.DATA / "profile-seals.yaml"
SCHEMA_VERSION = 1

_HEADER = (
    "# The print-profile seal ledger: the design-contract record that each\n"
    "# shipped profile's interior geometry was proven and sealed under a\n"
    "# design major. A seal binds a profile id to the design-affecting digest\n"
    "# (press.profiles.digest) it was qualified at; the selftest\n"
    "# (check_profile_seals) fails when a profile's geometry drifts from its\n"
    "# sealed digest, so appearance cannot change without a deliberate\n"
    "# re-seal. Maintain it through the lifecycle, never by hand: run\n"
    "#   python3 -m press.profile_lifecycle seal <profile-id>\n"
    "# after proving a new or changed profile. See docs/PROFILE-LIFECYCLE.md.\n"
)


@dataclass(frozen=True)
class Seal:
    """One profile's design-contract seal: the digest and design major it was
    qualified at, plus when and why. A profile whose current digest no longer
    matches its seal has changed appearance and must be re-sealed."""

    profile_id: str
    design_major: int
    digest: str
    qualified_on: str
    note: str = ""


def load_seals(path: Path | None = None) -> dict[str, Seal]:
    """The seal ledger as ``profile_id -> Seal``. Empty when the file is
    absent (an install that ships no ledger cannot check, and says so through
    ``validate`` rather than crashing)."""

    selected = path if path is not None else SEALS
    if not selected.is_file():
        return {}
    data = yamlio.loads(selected.read_text(encoding="utf-8")) or {}
    out: dict[str, Seal] = {}
    for name, raw in (data.get("seals") or {}).items():
        raw = raw or {}
        out[name] = Seal(
            profile_id=name,
            design_major=int(raw.get("design-major", 0)),
            digest=str(raw.get("digest", "")),
            qualified_on=str(raw.get("qualified-on", "")),
            note=str(raw.get("note", "")),
        )
    return out


def render_seals(seals: dict[str, Seal]) -> str:
    """The ledger's canonical text: the fixed banner, then the schema version
    and one block per seal in id order. Deterministic, so scaffolding and
    sealing reproduce a byte-stable file."""

    payload = {
        "schema-version": SCHEMA_VERSION,
        "seals": {
            seal.profile_id: {
                "design-major": seal.design_major,
                "digest": seal.digest,
                "qualified-on": seal.qualified_on,
                "note": seal.note,
            }
            for seal in sorted(seals.values(), key=lambda s: s.profile_id)
        },
    }
    return _HEADER + yamlio.dump(payload)


def _shipped_profile_ids() -> list[str]:
    return sorted(p.stem for p in profiles.profiles_dir().glob("*.yaml"))


def _current_seal(profile_id: str, note: str, on: str) -> Seal:
    """The seal a profile qualifies at *right now*: its live digest and
    design-major, read from the profile itself so a seal can never record a
    digest the profile does not actually have."""

    profile = profiles.load(profile_id)
    return Seal(
        profile_id=profile_id,
        design_major=int(profile.data.get("design-major", 0)),
        digest=profiles.digest(profile),
        qualified_on=on,
        note=note,
    )


def validate(seals: dict[str, Seal] | None = None,
             profile_ids: list[str] | None = None) -> list[str]:
    """Every way the seal ledger fails the design contract: a shipped profile
    with no seal, a seal whose recorded digest no longer matches the profile's
    live geometry (appearance drifted without a re-seal), a design-major
    disagreement, or a seal for a profile that no longer exists. An empty
    ledger (an install without one) reports nothing -- there is nothing to
    check against."""

    seals = load_seals() if seals is None else seals
    if not seals:
        return []
    ids = _shipped_profile_ids() if profile_ids is None else profile_ids
    problems: list[str] = []
    known = set(ids)
    for profile_id in ids:
        seal = seals.get(profile_id)
        if seal is None:
            problems.append(
                f"profile {profile_id!r} is not sealed; prove it and run "
                f"`python3 -m press.profile_lifecycle seal {profile_id}`")
            continue
        try:
            current = _current_seal(profile_id, seal.note, seal.qualified_on)
        except SystemExit as exc:
            problems.append(f"profile {profile_id!r} does not load: {exc}")
            continue
        if seal.digest != current.digest:
            problems.append(
                f"profile {profile_id!r} drifted from its seal "
                f"({seal.digest} -> {current.digest}); its geometry changed. "
                "This is a design-major decision: re-seal deliberately with "
                f"`python3 -m press.profile_lifecycle seal {profile_id}`")
        if seal.design_major != current.design_major:
            problems.append(
                f"profile {profile_id!r} seal records design-major "
                f"{seal.design_major}, profile declares {current.design_major}")
    for sealed_id in seals:
        if sealed_id not in known:
            problems.append(
                f"seal names {sealed_id!r}, which is not a shipped profile")
    return problems


def _parse_trim(spec: str) -> tuple[float, float]:
    """A ``WxH`` trim spec in inches, e.g. ``6x9`` or ``5.5x8.5``."""

    parts = spec.lower().replace("×", "x").split("x")
    if len(parts) != 2:
        raise SystemExit(f"trim must be WxH inches (e.g. 6x9), not {spec!r}")
    try:
        width, height = float(parts[0]), float(parts[1])
    except ValueError:
        raise SystemExit(f"trim must be WxH inches (e.g. 6x9), not {spec!r}")
    if width <= 0 or height <= 0:
        raise SystemExit(f"trim dimensions must be positive: {spec!r}")
    return width, height


def scaffold(profile_id: str, trim: str, *, ink: str = "single",
             base: str = profiles.HOUSE) -> str:
    """A new profile's YAML text, derived from an existing profile so it
    starts from proven geometry. Only the id, trim, and (optionally) the ink
    change; margins, figure cap, and typography carry over from the base for a
    maintainer to tune. The result is valid and loadable -- the same schema
    ``profiles.load`` reads."""

    if ink not in ("single", "color"):
        raise SystemExit(f"ink must be 'single' or 'color', not {ink!r}")
    if not profile_id or not profile_id.replace("-", "").isalnum():
        raise SystemExit(
            f"profile id must be a slug (letters, digits, hyphens): {profile_id!r}")
    width, height = _parse_trim(trim)
    src = profiles.load(base)
    interior = src.data["interior"]
    margins = " ".join(f"{k}: {float(v):g}," for k, v in src.margins.items()).rstrip(",")
    typ = interior["typography"]
    web = src.web

    lines = [
        f"# {profile_id}: a design profile scaffolded from {base} (#221).",
        "# A design profile carries the interior LOOK only -- trim, margins,",
        "# figure cap, typography -- sealed and versioned by design-major. The",
        "# geometry below is inherited from the base profile; tune the margins,",
        "# figure cap, and typography for this trim, PROVE it (the golden-copy",
        "# geometry test renders every shipped profile at its declared trim),",
        "# then SEAL it: python3 -m press.profile_lifecycle seal " + profile_id,
        "# See docs/PROFILE-LIFECYCLE.md and docs/PRINT-PROFILES-PLAN.md.",
        f"id: {profile_id}",
        f"design-major: {int(src.data.get('design-major', 1))}",
    ]
    if ink == "color":
        lines.append("ink: color")
    lines += [
        f"trim: {{width: {width:g}, height: {height:g}}}",
        "",
        "interior:",
        f"  # Inherited from {base}; the figure cap must never approach"
        " \\textheight.",
        f"  margins: {{{margins}}}",
        f"  figure-cap: {float(interior['figure-cap']):g}",
        f"  typography: {{indent: {typ['indent']}, leading: {float(typ['leading']):g}}}",
        "",
        f"web: {{measure: {web['measure']}, base-size: {web['base-size']}, "
        f"line-height: {float(web['line-height']):g}}}",
    ]
    return "\n".join(lines) + "\n"


def write_scaffold(profile_id: str, trim: str, *, ink: str = "single",
                   base: str = profiles.HOUSE) -> Path:
    """Lay a scaffolded profile into ``data/profiles/`` without clobbering an
    existing one, and confirm it loads as valid data before returning."""

    out = profiles.profiles_dir() / f"{profile_id}.yaml"
    if out.exists():
        raise SystemExit(f"profile {profile_id!r} already exists: {out}")
    text = scaffold(profile_id, trim, ink=ink, base=base)
    out.write_text(text, encoding="utf-8")
    # Prove the emitted text loads through the very reader books use, so a
    # scaffold never ships a file that fails at build time.
    _ = profiles.load(profile_id).trim
    return out


def write_seal(profile_id: str, note: str, *, on: str | None = None,
               path: Path | None = None) -> Seal:
    """Record (or refresh) a profile's seal at its current digest and write
    the ledger. Sealing is the deliberate act that qualifies a profile under
    the design contract; the digest is read from the profile, never supplied,
    so a seal cannot claim a geometry the profile does not have."""

    selected = path if path is not None else SEALS
    seals = load_seals(selected)
    on = on or date.today().isoformat()
    # Preserve the existing note when re-sealing without a new one.
    if not note and profile_id in seals:
        note = seals[profile_id].note
    seal = _current_seal(profile_id, note, on)
    seals[profile_id] = seal
    selected.write_text(render_seals(seals), encoding="utf-8")
    return seal


def _render_report(seals: dict[str, Seal], problems: list[str]) -> str:
    lines = ["print-profile seals:"]
    for seal in sorted(seals.values(), key=lambda s: s.profile_id):
        lines.append(
            f"  {seal.profile_id}  v{seal.design_major}  {seal.digest}  "
            f"sealed {seal.qualified_on}")
    if problems:
        lines.append("problems:")
        lines += [f"  - {p}" for p in problems]
    else:
        lines.append(f"all {len(_shipped_profile_ids())} shipped profiles are sealed and current")
    return "\n".join(lines)


_USAGE = (
    "usage: python3 -m press.profile_lifecycle validate\n"
    "       python3 -m press.profile_lifecycle scaffold <id> --trim WxH "
    "[--ink single|color] [--from <base>]\n"
    "       python3 -m press.profile_lifecycle seal <id> [--note \"why\"]\n"
    "       python3 -m press.profile_lifecycle list"
)


def _opt(argv: list[str], name: str, default: str | None = None) -> str | None:
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default


def main(argv: list[str] | None = None) -> int:
    """Drive the profile lifecycle from the command line -- validate the
    ledger, scaffold a profile, or seal one. Refusals are locatable and exit
    non-zero."""

    import sys

    argv = list(sys.argv[1:] if argv is None else argv)
    action = argv[0] if argv else "validate"

    if action in ("validate", "list"):
        seals = load_seals()
        problems = validate(seals)
        print(_render_report(seals, problems))
        return 1 if (problems and action == "validate") else 0

    if action == "scaffold":
        if len(argv) < 2 or "--trim" not in argv:
            print(_USAGE)
            return 2
        ink = _opt(argv, "--ink", "single") or "single"
        base = _opt(argv, "--from", profiles.HOUSE) or profiles.HOUSE
        trim = _opt(argv, "--trim")
        if trim is None:
            print(_USAGE)
            return 2
        out = write_scaffold(argv[1], trim, ink=ink, base=base)
        print(f"scaffolded {out}\nnow PROVE it (render + the geometry test) and "
              f"SEAL it: python3 -m press.profile_lifecycle seal {argv[1]}")
        return 0

    if action == "seal":
        if len(argv) < 2:
            print(_USAGE)
            return 2
        seal = write_seal(argv[1], _opt(argv, "--note", "") or "")
        print(f"sealed {seal.profile_id} at digest {seal.digest} "
              f"(design-major {seal.design_major}, {seal.qualified_on})")
        return 0

    print(_USAGE)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
