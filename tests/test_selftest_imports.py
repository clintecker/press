"""The import inventory gate: recursive, installed-package discovery.

INV-pkg-import-inventory. `press selftest` used to inventory only
top-level ``src/press/*.py`` files, so a nested runtime module under
adapters/, providers/, or desk/ could ship unimportable in a wheel while
the selftest stayed green (audit five: 58 reported versus 76 files). These
cases prove the gate now discovers the installed package recursively, names
the precise module on failure, keeps distinct identities for same-stem
modules, imports each module exactly once in deterministic order, and --
the strongest proof -- imports every nested module from a wheel built and
loaded outside the checkout.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from press import selftest

ROOT = Path(__file__).resolve().parent.parent


def _write_pkg(root: Path, layout: dict[str, str]) -> None:
    for rel, body in layout.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


@pytest.fixture
def synthetic_package(tmp_path, monkeypatch):
    """Build a throwaway importable package on a temp dir, put it on
    sys.path, and guarantee whatever it imports leaves sys.modules clean."""

    root = tmp_path / "pkgroot"
    root.mkdir()
    monkeypatch.syspath_prepend(str(root))
    before = set(sys.modules)

    def build(name: str, layout: dict[str, str]):
        _write_pkg(root / name, {"__init__.py": "", **layout})
        importlib.invalidate_caches()
        return importlib.import_module(name)

    try:
        yield build
    finally:
        for mod in set(sys.modules) - before:
            sys.modules.pop(mod, None)


def test_discovery_covers_nested_runtime_modules():
    """The bug this gate closes: every nested runtime subpackage is in the
    inventory, not only the top-level files a glob would find."""

    inventory = selftest.modules()
    for nested in ("press.adapters.http", "press.providers.contract",
                   "press.desk.app"):
        assert nested in inventory, f"{nested} missing from the import inventory"
    assert "press.__main__" not in inventory  # held out with a recorded reason


def test_discovery_is_deterministic_and_unique():
    inventory = selftest.modules()
    assert inventory == sorted(inventory), "inventory is not deterministically ordered"
    assert len(inventory) == len(set(inventory)), "inventory has a duplicate name"


def test_same_stem_in_different_subpackages_keep_distinct_identity(synthetic_package):
    """A filename-stem glob collapses ``thing.py`` in two subpackages to one
    name; recursive dotted discovery keeps both as distinct modules."""

    pkg = synthetic_package("dupident", {
        "thing.py": "MARK = 'top'\n",
        "sub/__init__.py": "",
        "sub/thing.py": "MARK = 'nested'\n",
    })
    names = selftest._discover_package_modules(pkg)
    assert "dupident.thing" in names and "dupident.sub.thing" in names
    top = importlib.import_module("dupident.thing")
    nested = importlib.import_module("dupident.sub.thing")
    assert top is not nested
    assert (top.MARK, nested.MARK) == ("top", "nested")


def test_broken_nested_import_names_the_module_and_chains_the_cause(synthetic_package):
    pkg = synthetic_package("brokenleaf", {
        "sub/__init__.py": "",
        "sub/wrong.py": "raise RuntimeError('boom at import')\n",
    })
    names = selftest._discover_package_modules(pkg)
    assert "brokenleaf.sub.wrong" in names
    with pytest.raises(SystemExit) as exc:
        selftest._import_module_names(names)
    assert "brokenleaf.sub.wrong" in str(exc.value)
    assert isinstance(exc.value.__cause__, RuntimeError)
    assert "boom at import" in str(exc.value.__cause__)


def test_broken_nested_package_fails_discovery_rather_than_shrinking_it(synthetic_package):
    """A nested package whose __init__ cannot import is a loud failure, not
    a silently smaller inventory that walk_packages would otherwise hand
    back."""

    pkg = synthetic_package("brokenpkg", {
        "sub/__init__.py": "raise RuntimeError('init exploded')\n",
        "sub/leaf.py": "",
    })
    with pytest.raises(ImportError) as exc:
        selftest._discover_package_modules(pkg)
    assert "brokenpkg.sub" in str(exc.value)
    assert isinstance(exc.value.__cause__, RuntimeError)
    assert "init exploded" in str(exc.value.__cause__)


@pytest.mark.invariant("INV-pkg-import-inventory")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
@pytest.mark.parametrize("effect, body, needle", [
    ("filesystem write",
     "from pathlib import Path; Path('scratch.txt').write_text('x')\n",
     "wrote a file"),
    ("builtin open for write",
     "open('scratch.txt', 'w').close()\n",
     "for writing"),
    ("spawned subprocess",
     "import subprocess; subprocess.run(['true'])\n",
     "spawned a subprocess"),
    ("shell command",
     "import os; os.system('true')\n",
     "ran a shell command"),
    ("network connection",
     "import socket; socket.create_connection(('127.0.0.1', 9))\n",
     "network connection"),
])
def test_forbidden_import_side_effect_is_named_and_refused(
        synthetic_package, effect, body, needle):
    """The invariant's teeth: a module that reaches for the network, spawns
    a subprocess, or writes a file *while being imported* is caught by the
    sandbox and named -- the guard sits on the acting call, so the effect is
    trapped before it happens (the socket never connects, the file is never
    written), never merely observed after the damage. The leaf is only ever
    imported inside the sandbox, so the effect cannot escape into the test
    run."""

    # Empty __init__: discovery finds the leaf without importing it, so the
    # side effect fires only under the sandbox, never when the package loads.
    pkg = synthetic_package("hostilefx", {"leaf.py": body})
    names = selftest._discover_package_modules(pkg)
    assert names == ["hostilefx.leaf"]
    offender = selftest._prove_no_import_side_effects(names)
    assert offender is not None, f"{effect} slipped past the import sandbox"
    assert offender.startswith("hostilefx.leaf"), offender
    assert needle in offender, offender


@pytest.mark.invariant("INV-pkg-import-inventory")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_side_effect_free_import_passes_the_sandbox(synthetic_package):
    """A module that only defines names -- constructing a Path or a socket
    without acting on it -- is not a side effect and passes clean."""

    pkg = synthetic_package("cleanfx", {
        "leaf.py": (
            "from pathlib import Path\n"
            "import socket\n"
            "HANDLE = Path('never-written.txt')\n"
            "SOCK = socket.socket(); SOCK.close()\n"
            "VALUE = 2 + 2\n"
        ),
    })
    names = selftest._discover_package_modules(pkg)
    assert selftest._prove_no_import_side_effects(names) is None


def test_import_side_effect_runs_once_in_deterministic_order(synthetic_package, monkeypatch):
    """Each module body executes exactly once, in sorted order, even when a
    name is offered twice -- the import gate does not re-run side effects."""

    log: list[str] = []
    import builtins

    monkeypatch.setattr(builtins, "_press_import_log", log, raising=False)
    pkg = synthetic_package("sidefx", {
        "b.py": "import builtins; builtins._press_import_log.append('sidefx.b')\n",
        "a.py": "import builtins; builtins._press_import_log.append('sidefx.a')\n",
        "c.py": "import builtins; builtins._press_import_log.append('sidefx.c')\n",
    })
    names = selftest._discover_package_modules(pkg)
    selftest._import_module_names(names + ["sidefx.a"])
    assert log == ["sidefx.a", "sidefx.b", "sidefx.c"]


def test_stale_import_exception_fails_the_gate(monkeypatch):
    monkeypatch.setitem(selftest.IMPORT_EXCEPTIONS, "press.ghost_module", "gone")
    with pytest.raises(SystemExit, match="no longer exist"):
        selftest.check_imports()


def test_top_level_only_discovery_is_rejected(monkeypatch):
    """The regression guard: a discovery that finds only top-level modules
    (the old glob) fails the gate instead of quietly passing every import
    while nested modules ship unproven."""

    monkeypatch.setattr(
        selftest, "_discover_package_modules",
        lambda package: ["press.__main__", "press.selftest", "press.build"],
    )
    with pytest.raises(SystemExit, match="regressed to top-level only"):
        selftest.check_imports()


@pytest.mark.skipif(
    importlib.util.find_spec("build") is None,
    reason="requires capability: build (pip install '.[dev]')",
)
@pytest.mark.invariant("INV-pkg-import-inventory")
@pytest.mark.layer("integration")
@pytest.mark.proof("positive")
def test_built_wheel_imports_every_nested_module_outside_checkout(tmp_path):
    """The invariant's whole point: from a wheel built and loaded outside
    the checkout -- where a filename glob over the source tree cannot reach
    -- every nested runtime module is discovered and imports."""

    dist = tmp_path / "dist"
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist)],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    wheels = list(dist.glob("*.whl"))
    assert len(wheels) == 1, wheels
    extract = tmp_path / "extract"
    with zipfile.ZipFile(wheels[0]) as archive:
        archive.extractall(extract)
    outside = tmp_path / "outside"
    outside.mkdir()

    probe = (
        "from pathlib import Path;"
        "import press;"
        "from press import selftest;"
        "ms = selftest.modules();"
        f"assert Path(press.__file__).is_relative_to(r'{extract}'), press.__file__;"
        "assert any('.adapters.' in m for m in ms), 'no adapters module discovered';"
        "assert any('.providers.' in m for m in ms), 'no providers module discovered';"
        "assert any('.desk.' in m for m in ms), 'no desk module discovered';"
        "selftest.check_imports();"
        "assert selftest._prove_no_import_side_effects(ms) is None, "
        "selftest._prove_no_import_side_effects(ms);"
        "print('IMPORTS_OK', len(ms))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=outside,
        env={**os.environ, "PYTHONPATH": str(extract)},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "IMPORTS_OK" in result.stdout, result.stdout + result.stderr
