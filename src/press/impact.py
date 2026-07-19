"""Map a change to its proof obligations.

Repository-wide coverage can stay green while a changed decision branch
gets no proof, and running the whole expensive stack for a one-line
edit wastes feedback. Both are failures of the same missing map: from a
change, to the surfaces it touches, to the invariants those surfaces
owe, to the proofs and tests that discharge them.

This module builds that map from the ledgers already in the repository:
the public-surface classification (quality/surfaces.yaml) says what each
changed module is, and the invariant ledger (quality/invariants.yaml)
says which guarantees name it as their enforcer. A change to
policy-bearing code (a verifier, parser, or the like) that maps to no
invariant, or to no classified surface, is a gap the gate refuses. The
selection is for acceleration only; a release always runs the whole
suite, and the selector's predictions are audited against full runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import adapters, invariants, surfaces

# Surface roles that carry correctness policy: a change to one of these
# owes an invariant and a proof. Presenters and pure helpers are lower
# stakes and are reported but not required to name an invariant.
POLICY_ROLES = frozenset({"verifier", "parser", "producer", "adapter", "orchestrator"})


@dataclass(frozen=True)
class ModuleImpact:
    module: str
    role: str | None
    invariants: tuple[str, ...]
    required: bool  # does a change here owe an invariant and a proof

    @property
    def unproven(self) -> bool:
        return self.required and not self.invariants


@dataclass
class Impact:
    modules: tuple[ModuleImpact, ...]
    gaps: tuple[str, ...] = field(default_factory=tuple)

    @property
    def selected_invariants(self) -> tuple[str, ...]:
        seen: list[str] = []
        for m in self.modules:
            for inv in m.invariants:
                if inv not in seen:
                    seen.append(inv)
        return tuple(seen)


def changed_modules(base_ref: str = "origin/main") -> list[str]:
    """The press module stems changed against a base ref, by git diff so
    it needs no build. An unavailable ref yields the empty set (a caller
    then runs everything)."""

    try:
        result = adapters.process_runner.run(
            ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
            capture=True, check=True,
        )
    except Exception:
        return []
    stems = []
    for line in result.stdout.decode("utf-8").splitlines():
        if line.startswith("src/press/") and line.endswith(".py"):
            stem = line[len("src/press/"):-len(".py")]
            if "/" not in stem and stem not in ("__init__", "__main__"):
                stems.append(stem)
    return sorted(set(stems))


def _role_of(config: dict, module: str) -> str | None:
    spec = (config.get("modules") or {}).get(module)
    if spec is None:
        return None
    return spec if isinstance(spec, str) else spec.get("default")


def _invariants_for(ledger: list[dict], module: str) -> tuple[str, ...]:
    hits = []
    for inv in ledger:
        enforcer = inv["enforcer"]
        owner = enforcer.split(".", 1)[0]
        if owner == module or inv.get("owner") == module:
            hits.append(inv["id"])
    return tuple(sorted(set(hits)))


def analyze(modules: list[str]) -> Impact:
    """The obligations of a set of changed modules."""

    config = surfaces.load_config()
    ledger = invariants.load()
    impacts = []
    gaps = []
    for module in modules:
        role = _role_of(config, module)
        invs = _invariants_for(ledger, module)
        required = role in POLICY_ROLES
        impact = ModuleImpact(module, role, invs, required)
        impacts.append(impact)
        if role is None:
            gaps.append(f"{module}: changed but not classified in the surface ledger")
        elif impact.unproven:
            gaps.append(
                f"{module}: policy code ({role}) changed but no invariant names "
                "it; add one or reclassify"
            )
    return Impact(tuple(impacts), tuple(gaps))


def render(impact: Impact) -> str:
    lines = ["change impact:"]
    if not impact.modules:
        lines.append("  no press modules changed; the full suite is the selection")
        return "\n".join(lines)
    for m in impact.modules:
        role = m.role or "UNCLASSIFIED"
        proof = f"invariants: {', '.join(m.invariants)}" if m.invariants else "no invariant"
        why = " (policy: owes a proof)" if m.required else ""
        lines.append(f"  {m.module} [{role}]{why}: {proof}")
    if impact.selected_invariants:
        lines.append(f"selected invariants: {', '.join(impact.selected_invariants)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import sys

    args = list(argv if argv is not None else sys.argv[1:])
    base = args[0] if args else "origin/main"
    impact = analyze(changed_modules(base))
    print(render(impact))
    if impact.gaps:
        print("\nchange-obligation gaps:")
        for gap in impact.gaps:
            print(f"  - {gap}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
