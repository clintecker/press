"""The public-surface inventory gate.

quality/surfaces.yaml classifies every public callable in the package
by role (pure, parser, normalizer, verifier, producer, orchestrator,
adapter, presenter), assigned by module default with per-callable
overrides. This module discovers the actual public callables by AST
and fails when one exists that the classification does not account for,
so a new public function cannot ship without a deliberate decision
about how it is proven. An exemption is a decision on the record, with
a reason and a review date, never a silent gap.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from . import yamlio

SRC = Path(__file__).resolve().parent
CONFIG = SRC.parent.parent / "quality" / "surfaces.yaml"
# Modules whose public callables are not part of the classified surface:
# entrypoint dispatch and the classifier itself.
UNCLASSIFIED_MODULES = {"__main__", "surfaces"}


def public_callables() -> dict[str, list[str]]:
    """Module stem -> its public module-level function names, by AST so
    importing is never required to take the inventory."""

    found: dict[str, list[str]] = {}
    for path in sorted(SRC.glob("*.py")):
        if path.stem.startswith("_") or path.stem in UNCLASSIFIED_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = [
            node.name for node in tree.body
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        ]
        if names:
            found[path.stem] = names
    return found


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yamlio.loads(handle.read())


def classify(config: dict[str, Any], module: str, func: str) -> str | None:
    """The role assigned to one callable, or None if unclassified."""

    exempt = {e["callable"] for e in config.get("exemptions") or []}
    if f"{module}.{func}" in exempt:
        return "exempt"
    spec = (config.get("modules") or {}).get(module)
    if spec is None:
        return None
    if isinstance(spec, str):
        return spec
    overrides = spec.get("overrides") or {}
    if func in overrides:
        return overrides[func]
    return spec.get("default")


def audit() -> dict[str, Any]:
    """The full inventory: every public callable with its role, and the
    problems (unclassified callables, config referencing callables that
    no longer exist, exemptions missing a reason or review date)."""

    config = load_config()
    roles = set(config.get("roles") or {})
    inventory = public_callables()
    classified: dict[str, str] = {}
    problems: list[str] = []

    for module, funcs in inventory.items():
        for func in funcs:
            role = classify(config, module, func)
            if role is None:
                problems.append(f"{module}.{func} is an unclassified public callable")
            elif role != "exempt" and role not in roles:
                problems.append(f"{module}.{func}: unknown role {role!r}")
            else:
                classified[f"{module}.{func}"] = role

    # Config that names callables the code no longer has is stale.
    live = {f"{m}.{f}" for m, funcs in inventory.items() for f in funcs}
    for module, spec in (config.get("modules") or {}).items():
        if isinstance(spec, dict):
            for func in spec.get("overrides") or {}:
                if f"{module}.{func}" not in live:
                    problems.append(f"override {module}.{func} names no live callable")
    for exemption in config.get("exemptions") or []:
        name = exemption["callable"]
        if name not in live:
            problems.append(f"exemption {name} names no live callable")
        if not exemption.get("reason") or not exemption.get("review"):
            problems.append(f"exemption {name} needs a reason and a review date")

    return {"classified": classified, "problems": problems, "total": len(live)}


def missing_modules(config: dict[str, Any] | None = None) -> list[str]:
    """Modules the AST inventory found that the config does not yet
    classify at all. `--write` appends these as 'unclassified' so the
    module list is maintained mechanically; a human then assigns the
    role, and the gate fails until they do."""

    config = config if config is not None else load_config()
    known = set(config.get("modules") or {})
    return sorted(set(public_callables()) - known)


def scaffold(path: Path = CONFIG) -> list[str]:
    """Append every unclassified module to the config as 'unclassified'
    and return the ones added. Comment-preserving: it appends lines, it
    does not rewrite the file."""

    added = missing_modules()
    if added:
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n  # Added mechanically by --write; assign a real role.\n")
            for module in added:
                handle.write(f"  {module}: unclassified\n")
    return added


def main(argv: list[str] | None = None) -> int:
    import sys

    if argv is None:
        argv = sys.argv[1:]
    if "--write" in argv:
        added = scaffold()
        print(f"scaffolded {len(added)} new module(s): {added}" if added
              else "surfaces.yaml already lists every module")
    result = audit()
    if result["problems"]:
        raise SystemExit(
            "public surface not fully classified "
            "(run `python3 -m press.surfaces --write` to scaffold new modules):\n"
            + "\n".join(f"  - {p}" for p in result["problems"])
        )
    print(
        f"Public surface classified: {result['total']} callables, "
        "every one has a role or a recorded exemption"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
