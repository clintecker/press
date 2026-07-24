"""The boundary-inventory gate: direct process/env/network calls live only
in the adapter package.

Issue #82 routes the press's outward calls -- subprocess, ``os.environ``,
PATH resolution, and HTTP -- through ``press.adapters`` so they can be faked
deterministically in tests. This gate keeps that true by construction: it
parses every module's AST and fails if a boundary call appears anywhere the
policy does not permit. A brand-new module, or a regression that reaches for
``subprocess.run`` in already-migrated code, turns this test red.

There is now exactly one approved home: the ``press.adapters`` package.
The legacy allowlist that once carried the not-yet-migrated modules is
empty and gone (issue #199 migrated the last one, ``selftest``), so no
module outside ``press.adapters`` may hold a direct boundary call.
"""

from __future__ import annotations

import ast
from pathlib import Path

PRESS = Path(__file__).resolve().parent.parent / "src" / "press"

# Modules #82 migrated onto the adapters. They must contain no direct
# boundary call: that is the whole point of the issue.
MIGRATED = {
    "build",
    "doctor",
    "operator",
    "art_commission",
    "package_source",
}

# subprocess members that actually execute a command (as opposed to the
# exception classes a migrated module may still import to catch).
_SUBPROCESS_EXEC = {
    "run", "Popen", "call", "check_call", "check_output",
    "getoutput", "getstatusoutput",
}
_OS_ENV_FUNCS = {"getenv", "putenv", "unsetenv"}


class _BoundaryVisitor(ast.NodeVisitor):
    """Collects (lineno, description) for every direct boundary call."""

    def __init__(self) -> None:
        self.findings: list[tuple[int, str]] = []

    def _flag(self, node: ast.AST, what: str) -> None:
        self.findings.append((getattr(node, "lineno", 0), what))

    def visit_Attribute(self, node: ast.Attribute) -> None:
        value = node.value
        # os.environ (read or subscripted)
        if isinstance(value, ast.Name) and value.id == "os" and node.attr == "environ":
            self._flag(node, "os.environ")
        # subprocess.<executor>
        elif (isinstance(value, ast.Name) and value.id == "subprocess"
              and node.attr in _SUBPROCESS_EXEC):
            self._flag(node, f"subprocess.{node.attr}")
        # os.getenv / os.putenv / os.unsetenv
        elif (isinstance(value, ast.Name) and value.id == "os"
              and node.attr in _OS_ENV_FUNCS):
            self._flag(node, f"os.{node.attr}")
        # shutil.which
        elif (isinstance(value, ast.Name) and value.id == "shutil"
              and node.attr == "which"):
            self._flag(node, "shutil.which")
        # urllib.request / urllib.error (network), but not urllib.parse
        elif (isinstance(value, ast.Name) and value.id == "urllib"
              and node.attr in {"request", "error"}):
            self._flag(node, f"urllib.{node.attr}")
        # requests.<anything>
        elif isinstance(value, ast.Name) and value.id == "requests":
            self._flag(node, f"requests.{node.attr}")
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "requests" or alias.name.startswith("requests."):
                self._flag(node, f"import {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if module == "requests" or module.startswith("requests."):
            self._flag(node, f"from {module} import ...")
        if module.startswith("urllib.request") or module.startswith("urllib.error"):
            self._flag(node, f"from {module} import ...")
        if module == "urllib":
            for alias in node.names:
                if alias.name in {"request", "error"}:
                    self._flag(node, f"from urllib import {alias.name}")
        self.generic_visit(node)


def _boundary_findings(path: Path) -> list[tuple[int, str]]:
    visitor = _BoundaryVisitor()
    visitor.visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
    return visitor.findings


def _package_modules() -> list[Path]:
    """Every module under press, excluding the adapters package (the one
    approved home) and generated/data trees."""

    modules = []
    for path in sorted(PRESS.rglob("*.py")):
        relative = path.relative_to(PRESS)
        if relative.parts[0] in {"adapters", "data"}:
            continue
        modules.append(path)
    return modules


def test_migrated_modules_have_no_direct_boundary_calls():
    """The five modules #82 migrated route every outward call through
    ``press.adapters``; none may reach a boundary directly."""

    offenders = {}
    for path in _package_modules():
        if path.stem in MIGRATED:
            findings = _boundary_findings(path)
            if findings:
                offenders[path.stem] = findings
    assert not offenders, (
        "migrated modules must call boundaries only through press.adapters; "
        f"found direct calls: {offenders}"
    )


def test_no_boundary_calls_outside_adapters():
    """No module outside ``press.adapters`` may hold a direct boundary
    call: the legacy allowlist is empty, so a module reaching for
    subprocess/os.environ/urllib/requests/shutil.which anywhere else fails
    here. A new module, or a regression in a migrated one, turns this red."""

    offenders = {}
    for path in _package_modules():
        findings = _boundary_findings(path)
        if findings:
            offenders[path.stem] = findings
    assert not offenders, (
        "direct boundary calls found outside press.adapters -- route them "
        f"through an adapter: {offenders}"
    )
