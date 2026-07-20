"""The boundary-inventory gate: direct process/env/network calls live only
in the adapter package.

Issue #82 routes the press's outward calls -- subprocess, ``os.environ``,
PATH resolution, and HTTP -- through ``press.adapters`` so they can be faked
deterministically in tests. This gate keeps that true by construction: it
parses every module's AST and fails if a boundary call appears anywhere the
policy does not permit. A brand-new module, or a regression that reaches for
``subprocess.run`` in already-migrated code, turns this test red.

Two tiers of permission:

* the ``press.adapters`` package -- the one approved home;
* a shrinking ``LEGACY_ALLOWED`` set of modules not yet migrated. Every
  entry must still contain a boundary call (a stale entry fails, so the
  allowlist can only shrink), and none of the five modules #82 migrated may
  appear in it (they must be clean).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

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

# Modules that still hold direct boundary calls and are not part of #82's
# scope. Each must genuinely still contain one (proven below), so this list
# can only shrink as later work migrates them. Adding a boundary call to a
# module not listed here -- or to a migrated one -- fails the gate.
LEGACY_ALLOWED = {
    "__main__",
    "booklib",
    "check_the_checkers",
    "gen_coverwrap",
    "scaffold",
    "selftest",
    "verify_coverwrap",
    "verify_formats",
    "verify_pdf",
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


def test_no_boundary_calls_outside_adapters_or_legacy_allowlist():
    """No module may grow a direct boundary call unless it is on the
    explicit, shrinking legacy allowlist. A new module reaching for
    subprocess/os.environ/urllib/requests/shutil.which fails here."""

    offenders = {}
    for path in _package_modules():
        if path.stem in LEGACY_ALLOWED:
            continue
        findings = _boundary_findings(path)
        if findings:
            offenders[path.stem] = findings
    assert not offenders, (
        "direct boundary calls found outside press.adapters and the legacy "
        f"allowlist -- route them through an adapter: {offenders}"
    )


@pytest.mark.parametrize("module", sorted(LEGACY_ALLOWED))
def test_legacy_allowlist_has_no_stale_entries(module):
    """A module on the legacy allowlist must still contain a boundary call.
    Once migrated, it must be removed from the list, so the allowlist can
    only shrink -- it cannot rot into a silent permanent exemption."""

    path = PRESS / f"{module}.py"
    assert path.exists(), f"allowlisted module {module} does not exist"
    assert _boundary_findings(path), (
        f"{module} is on LEGACY_ALLOWED but has no direct boundary call; "
        "remove it from the allowlist"
    )


def test_migrated_and_legacy_are_disjoint():
    """A module cannot be both claimed-clean and legacy-exempt."""

    assert not (MIGRATED & LEGACY_ALLOWED)
