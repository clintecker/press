"""The mutation ratchet's enumeration and mutation are deterministic and
never emit a no-op. A no-op mutation would leave the source unchanged and
"survive" every test -- a false gap; a non-deterministic enumeration would
make the gate flake. These are the properties the whole gate rests on.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load():
    path = ROOT / "scripts" / "mutation_ratchet.py"
    spec = importlib.util.spec_from_file_location("mutation_ratchet", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["mutation_ratchet"] = module  # so its dataclass resolves
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_enumeration_is_deterministic_and_deduplicated():
    mr = _load()
    for module in mr.TARGETS:
        tree = ast.parse((mr.SRC / f"{module}.py").read_text(encoding="utf-8"))
        first = [s.id for s in mr._enumerate(tree)]
        second = [s.id for s in mr._enumerate(tree)]
        assert first == second, f"{module}: enumeration not stable"
        assert len(first) == len(set(first)), f"{module}: duplicate site ids"


def test_every_mutation_changes_the_source():
    mr = _load()
    for module in mr.TARGETS:
        source = (mr.SRC / f"{module}.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        base = ast.unparse(tree)
        for site in mr._enumerate(tree):
            mutated = ast.unparse(mr._apply(tree, site))
            assert mutated != base, f"{module} {site.id}: no-op mutation"


def test_baseline_is_well_formed_and_covers_the_targets():
    mr = _load()
    data = json.loads((ROOT / "quality" / "mutation-baseline.json").read_text())
    for module in mr.TARGETS:
        entry = data["modules"][module]
        assert entry["total"] >= entry["killed"] >= 0
        # killed + survivors accounts for every mutant.
        assert entry["killed"] + len(entry["survivors"]) == entry["total"]
