"""The extension contract, made executable.

The press has no plugin loader, no entry-point group, and no import-time
discovery, and that is the contract, not a gap: behavior cannot come from
the accident of which package imported first. What the press *does* extend
is declarative — a design profile, a provider spec, an artifact, a skill,
or a workflow is a named data file selected by id (see ``profiles.py`` and
``provider_specs.py``). This module states the law those declarations must
obey and proves it against fixtures.

An **extension manifest** is the record an extension carries: what it is,
which surface it registers into, the exact names it claims, what it depends
on, the invariants it takes on and how they are proven, the capabilities it
asserts, and whether the artifacts it adds are published. ``conformance``
is the gate: it refuses a manifest that collides with a core name, targets
an unsupported contract major, leaves a declared invariant unproven, or
claims a sealed capability -- *before* anything is built. A conforming
manifest earns no privilege to run code; it earns a place in a registry the
same typed, path-contained, deterministic laws already govern.

The document this enforces is ``docs/EXTENSION-CONTRACT.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

# The extension-contract major this press speaks. It moves with the design
# major (v2 is the first press to have configurable surfaces to extend), so
# an extension pins the contract it was written against and a press refuses
# a contract it does not implement rather than guess.
CONTRACT_MAJOR = 2
SUPPORTED_CONTRACT_MAJORS: tuple[int, ...] = (2,)

# The surfaces an extension may register into. Each is already a named,
# id-selected, data-declared registry; an extension is one more entry in one
# of them, never a new kind of thing.
KINDS: tuple[str, ...] = (
    "design-profile",
    "provider-spec",
    "artifact",
    "skill",
    "workflow",
)

# Publication policy an extension declares for any artifact it adds. It must
# be explicit: an artifact that reaches readers is a decision, not a default.
PUBLICATION = ("published", "internal")

# Capabilities the core keeps for itself. An extension may *depend on* these
# running, but it may never declare that it provides or replaces one: the
# mandatory verification, the containment of every write under the book
# root, the acyclic artifact graph, and the release gate are the press's to
# guarantee, and a manifest that claims them is refused. This is the tooth
# behind "a plugin cannot weaken or replace mandatory core verification
# invisibly."
SEALED_CAPABILITIES: frozenset[str] = frozenset({
    "core-verification",
    "path-containment",
    "artifact-graph",
    "release-gate",
    "config-validation",
})


@dataclass(frozen=True)
class Manifest:
    """A parsed, structurally-valid extension declaration. Structural
    validity (the required keys are present and well-typed) is guaranteed by
    ``load_manifest``; *policy* validity (no collision, a supported contract,
    proven invariants, no sealed claim) is what ``conformance`` decides."""

    name: str
    kind: str
    contract_major: int
    provides: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    invariants: tuple[str, ...] = ()
    proofs: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    publication: str = "internal"


def fixtures_dir() -> Path:
    from . import booklib

    return booklib.DATA / "extensions"


def _require(data: dict[str, Any], key: str, kind: type) -> Any:
    if key not in data:
        raise SystemExit(f"extension manifest missing required key {key!r}")
    value = data[key]
    if not isinstance(value, kind):
        raise SystemExit(
            f"extension manifest key {key!r} must be {kind.__name__}, "
            f"got {type(value).__name__}"
        )
    return value


def _string_list(data: dict[str, Any], key: str) -> tuple[str, ...]:
    value = data.get(key) or []
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise SystemExit(f"extension manifest key {key!r} must be a list of strings")
    return tuple(value)


def load_manifest(data: dict[str, Any]) -> Manifest:
    """Parse a manifest mapping into a ``Manifest``, refusing anything
    structurally malformed (a missing or mistyped required key). This is the
    parser boundary; it says nothing about policy."""

    if not isinstance(data, dict):
        raise SystemExit("extension manifest must be a mapping")
    name = _require(data, "name", str)
    kind = _require(data, "kind", str)
    contract_major = _require(data, "contract-major", int)
    publication = data.get("publication", "internal")
    if not isinstance(publication, str):
        raise SystemExit("extension manifest key 'publication' must be a string")
    return Manifest(
        name=name,
        kind=kind,
        contract_major=contract_major,
        provides=_string_list(data, "provides"),
        requires=_string_list(data, "requires"),
        invariants=_string_list(data, "invariants"),
        proofs=_string_list(data, "proofs"),
        capabilities=_string_list(data, "capabilities"),
        publication=publication,
    )


def load_manifest_file(path: Path) -> Manifest:
    from . import yamlio

    return load_manifest(yamlio.load(path))


def core_names() -> set[str]:
    """Every name the core already owns across the extensible surfaces, read
    live so the reserved set can never drift from what actually ships: the
    artifact ids, the CLI command names and their aliases, and the design
    profile and provider-spec ids on disk."""

    from . import catalog, registry

    names: set[str] = set(registry.ARTIFACTS)
    for command in catalog.COMMANDS:
        names.add(command.name)
        names.update(command.aliases)
    for surface in ("profiles", "provider-specs"):
        directory = _data_dir(surface)
        if directory.is_dir():
            names.update(p.stem for p in directory.glob("*.yaml"))
    return names


def _data_dir(name: str) -> Path:
    from . import booklib

    return booklib.DATA / name


def conformance(manifest: Manifest, reserved: set[str] | None = None) -> list[str]:
    """The policy gate. Return the reasons this manifest is refused, most
    important first; an empty list means it conforms. Every reason names the
    exact declaration at fault so a failure is locatable, never a bare
    'invalid extension'."""

    reserved = core_names() if reserved is None else reserved
    problems: list[str] = []

    if manifest.contract_major not in SUPPORTED_CONTRACT_MAJORS:
        supported = ", ".join(str(m) for m in SUPPORTED_CONTRACT_MAJORS)
        problems.append(
            f"targets extension contract major {manifest.contract_major}; "
            f"this press supports {{{supported}}}"
        )

    if manifest.kind not in KINDS:
        problems.append(
            f"kind {manifest.kind!r} is not an extensible surface "
            f"(one of: {', '.join(KINDS)})"
        )

    if manifest.publication not in PUBLICATION:
        problems.append(
            f"publication {manifest.publication!r} must be one of: "
            f"{', '.join(PUBLICATION)}"
        )

    # A provided name may not collide with a core name or with another name
    # this same manifest claims. Collision is decided before any build.
    seen: set[str] = set()
    for name in manifest.provides:
        if name in reserved:
            problems.append(f"provides {name!r}, which collides with a core name")
        if name in seen:
            problems.append(f"provides {name!r} more than once")
        seen.add(name)

    # A dependency must resolve to something knowable now: a core name or a
    # name this manifest itself provides. An ambient, hope-it-loads dependency
    # is refused so discovery order cannot decide behavior.
    knowable = reserved | set(manifest.provides)
    for name in manifest.requires:
        if name not in knowable:
            problems.append(
                f"requires {name!r}, which is neither a core name nor provided here"
            )

    # Every invariant an extension takes on must carry a proof. An obligation
    # without a proof is exactly the invisible weakening the seal forbids.
    proofs = [p for p in manifest.proofs if p and p != "none"]
    if manifest.invariants and not proofs:
        problems.append(
            "declares invariants "
            f"({', '.join(manifest.invariants)}) but names no proof for them"
        )

    sealed = [c for c in manifest.capabilities if c in SEALED_CAPABILITIES]
    for capability in sealed:
        problems.append(
            f"claims sealed capability {capability!r}; core verification, "
            "containment, the artifact graph, and the release gate cannot be "
            "provided or replaced by an extension"
        )

    return problems


def conforms(manifest: Manifest, reserved: set[str] | None = None) -> bool:
    return not conformance(manifest, reserved)
