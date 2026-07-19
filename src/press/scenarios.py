"""The configuration-scenario generator.

Optional book features interact, but the Cartesian product of every
dimension is wasteful and hand-picked scenarios silently stop covering
new dimensions. This module reads the scenario ledger
(quality/scenarios.yaml), produces a *deterministic* all-pairs covering
set over its dimensions, and carries the hand-named high-risk
interactions a pairwise set can never be trusted to hit on its own.

Determinism is a requirement, not a nicety: there is no RNG and no
clock here. The pairwise search is a fixed greedy over dimensions and
values in ledger order, so the covering set is byte-for-byte the same
on every run and a reviewer reads a diff, not a shuffle. Each scenario
carries a stable id (a high-risk scenario's is its ledger id; a
pairwise scenario's is derived from its chosen values), so a failure or
a trust receipt can name exactly which combination broke.

The gates that consume this (tests/test_scenarios.py) fail when a
surface dimension is never covered both present and absent, or when a
declared high-risk interaction has no collected test.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

CONFIG = Path(__file__).resolve().parent.parent.parent / "quality" / "scenarios.yaml"

# The high-risk interactions that MUST always be declared. The ledger
# may add more, but if one of these leaves quality/scenarios.yaml the
# high-risk gate reddens: these are the combinations a pairwise set is
# structurally unable to guarantee, learned the hard way.
REQUIRED_HIGH_RISK = frozenset({
    "css-pages-crawl",
    "authorities-sources-companion",
    "index-tex-safety",
    "retail-registrations",
    "overrides-design",
})


def load(path: Path | None = None) -> dict[str, Any]:
    """The scenario ledger as a mapping, validated enough that a
    malformed dimension surfaces here and not deep in the generator."""

    with (path or CONFIG).open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError("scenarios.yaml must be a mapping")
    dims = config.get("dimensions")
    if not isinstance(dims, dict) or not dims:
        raise ValueError("scenarios.yaml needs a non-empty 'dimensions' mapping")
    for name, spec in dims.items():
        if not isinstance(spec, dict):
            raise ValueError(f"dimension {name!r} must be a mapping")
        values = spec.get("values")
        if not isinstance(values, list) or len(values) < 2:
            raise ValueError(f"dimension {name!r} needs at least two values")
        if spec.get("kind") == "surface" and spec.get("absent") not in values:
            raise ValueError(
                f"surface dimension {name!r} must name an 'absent' value from its values"
            )
    return config


def dimension_values(config: dict[str, Any] | None = None) -> dict[str, list[str]]:
    """Dimension name -> its ordered value list, in ledger order. The
    ordering is load-bearing: it fixes the pairwise search."""

    config = config if config is not None else load()
    return {name: list(spec["values"]) for name, spec in config["dimensions"].items()}


def surface_dimensions(config: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """The optional-configuration-surface dimensions only, each mapped to
    ``{absent, present}`` value partitions. A `mode` dimension has no
    absent state and is excluded; the surface gate reads exactly this."""

    config = config if config is not None else load()
    surfaces: dict[str, dict[str, Any]] = {}
    for name, spec in config["dimensions"].items():
        if spec.get("kind") != "surface":
            continue
        absent = spec["absent"]
        present = [v for v in spec["values"] if v != absent]
        surfaces[name] = {"absent": absent, "present": present}
    return surfaces


def scenario_id(dimensions: dict[str, str]) -> str:
    """A stable id for a chosen combination: the same values always
    yield the same id, independent of insertion order, with no clock or
    RNG. A short digest keeps it terse while staying collision-safe for
    the handful of scenarios a covering set holds."""

    canonical = ";".join(f"{k}={dimensions[k]}" for k in sorted(dimensions))
    digest = hashlib.blake2s(canonical.encode("utf-8"), digest_size=4).hexdigest()
    return f"pw-{digest}"


def pairwise(values: dict[str, list[str]]) -> list[dict[str, str]]:
    """A deterministic all-pairs covering set over the given dimensions.

    Every (dimension_a=value, dimension_b=value) pair appears in at
    least one returned combination. The search is a fixed greedy with no
    randomness: it seeds each new combination from the
    lexicographically-first still-uncovered pair, then fills the
    remaining dimensions in ledger order choosing, for each, the value
    that covers the most currently-uncovered pairs (ties broken by value
    order). Identical input yields an identical set on every run.
    """

    names = list(values)
    # Every pair to cover, stored canonically with the earlier-in-order
    # dimension first so lookups and discards agree.
    uncovered: set[tuple[str, str, str, str]] = set()
    for i, ni in enumerate(names):
        for nj in names[i + 1:]:
            for a in values[ni]:
                for b in values[nj]:
                    uncovered.add((ni, a, nj, b))

    order = {name: idx for idx, name in enumerate(names)}

    def key(n1: str, v1: str, n2: str, v2: str) -> tuple[str, str, str, str]:
        if order[n1] <= order[n2]:
            return (n1, v1, n2, v2)
        return (n2, v2, n1, v1)

    combinations: list[dict[str, str]] = []
    while uncovered:
        seed = min(uncovered)
        combo: dict[str, str] = {seed[0]: seed[1], seed[2]: seed[3]}
        for name in names:
            if name in combo:
                continue
            best_value = values[name][0]
            best_gain = -1
            for value in values[name]:
                gain = sum(
                    1 for other, chosen in combo.items()
                    if key(name, value, other, chosen) in uncovered
                )
                if gain > best_gain:
                    best_gain = gain
                    best_value = value
            combo[name] = best_value
        for i, ni in enumerate(names):
            for nj in names[i + 1:]:
                uncovered.discard((ni, combo[ni], nj, combo[nj]))
        combinations.append({name: combo[name] for name in names})
    return combinations


def high_risk_scenarios(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """The hand-named high-risk interactions, each a full buildable
    scenario: the ledger fixes the dimensions that carry its risk and
    the rest fill with each dimension's absent (or first) value."""

    config = config if config is not None else load()
    defaults = _defaults(config)
    scenarios: list[dict[str, Any]] = []
    for entry in config.get("high_risk") or []:
        fixed = entry.get("dimensions") or {}
        unknown = set(fixed) - set(defaults)
        if unknown:
            raise ValueError(
                f"high-risk {entry['id']!r} names unknown dimension(s) {sorted(unknown)}"
            )
        for name, value in fixed.items():
            if value not in defaults[name][1]:
                raise ValueError(
                    f"high-risk {entry['id']!r} sets {name}={value!r}, not a declared value"
                )
        dimensions = {name: fixed.get(name, absent) for name, (absent, _) in defaults.items()}
        scenarios.append({
            "id": entry["id"],
            "kind": "high-risk",
            "fixed": dict(fixed),
            "rationale": entry.get("rationale", ""),
            "dimensions": dimensions,
        })
    return scenarios


def covering_set(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """The full scenario set: the deterministic pairwise combinations
    first (each tagged with its derived id), then the high-risk
    interactions. This is what the gates and any trust receipt consume."""

    config = config if config is not None else load()
    scenarios: list[dict[str, Any]] = []
    for combo in pairwise(dimension_values(config)):
        scenarios.append({
            "id": scenario_id(combo),
            "kind": "pairwise",
            "dimensions": combo,
        })
    scenarios.extend(high_risk_scenarios(config))
    return scenarios


def _defaults(config: dict[str, Any]) -> dict[str, tuple[str, list[str]]]:
    """Dimension name -> (fill value, all values). A surface fills with
    its absent value; a mode fills with its first."""

    out: dict[str, tuple[str, list[str]]] = {}
    for name, spec in config["dimensions"].items():
        vals = list(spec["values"])
        fill = spec["absent"] if spec.get("kind") == "surface" else vals[0]
        out[name] = (fill, vals)
    return out
