"""One YAML library, one version: every module reads and writes YAML through
`press.yamlio` (ruamel at YAML 1.2), never a raw `import yaml` (PyYAML, YAML
1.1) or a private `ruamel` import.

Press once split its YAML across two libraries and two versions -- PyYAML
(1.1, where a bare `no` is a boolean) for reads, ruamel (1.2) for the config
writer -- so a written `no` could read back as `False`. This gate keeps the
package single-sourced by construction: it parses every module's AST and
fails on a raw YAML import outside the one door. `yamlio` is that door;
`config_store` is the only other module allowed to touch ruamel directly,
because the comment-preserving `press config` writer needs round-trip mode.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PRESS = Path(__file__).resolve().parent.parent / "src" / "press"

# The only modules permitted to import a YAML library directly: the one
# door (yamlio), the comment-preserving config writer that needs ruamel's
# round-trip mode (config_store), and doctor's dependency-importability
# probe (which imports ruamel only to confirm it is installed).
ALLOWED = {"yamlio", "config_store", "doctor"}


def _yaml_imports(tree: ast.AST) -> list[str]:
    """Every top-level YAML library name imported in this module."""

    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names if _is_yaml(a.name)]
        elif isinstance(node, ast.ImportFrom):
            if node.module and _is_yaml(node.module):
                names.append(node.module)
    return names


def _is_yaml(module: str) -> bool:
    root = module.split(".")[0]
    return root in {"yaml", "ruamel"}


def _modules() -> list[Path]:
    return sorted(p for p in PRESS.rglob("*.py") if p.name != "__init__.py")


def test_no_module_imports_a_yaml_library_outside_the_one_door():
    offenders: list[str] = []
    for path in _modules():
        if path.stem in ALLOWED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name in _yaml_imports(tree):
            offenders.append(f"{path.stem}: import {name}")
    assert not offenders, (
        "YAML must be reached through press.yamlio, not a raw import:\n  "
        + "\n  ".join(offenders)
    )


def test_pyyaml_is_not_a_dependency():
    text = (PRESS.parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert "PyYAML" not in text and "types-PyYAML" not in text


@pytest.mark.parametrize("allowed", sorted(ALLOWED))
def test_the_allowed_modules_actually_use_ruamel(allowed):
    # A stale exemption is a defect: each allowed module must really import a
    # YAML library, so the allowlist cannot outlive its reason.
    tree = ast.parse((PRESS / f"{allowed}.py").read_text(encoding="utf-8"))
    assert _yaml_imports(tree), f"{allowed} is exempt but imports no YAML library"
