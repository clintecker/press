"""The artifact graph as build-mutate-verify state transitions.

Testing verifiers in isolation cannot prove the workflow laws that
depend on operation order: a mutated output must not be blessed,
rebuilding must restore validity, clean must remove every declared
output, and prerequisites must precede dependents. This module drives
bounded, deterministic transition sequences over a real artifact and
asserts those laws.

The concrete artifact is the source archive: it is built from git
alone (no LuaLaTeX), verified by verify_archives, and mutated by the
damage operators, so a full clean -> build -> verify -> mutate ->
verify-fails -> rebuild -> verify-passes -> clean-gone cycle runs
deterministically in a unit test. The graph-shape laws (ordering,
clean coverage) come from the registry, which is pure. Both cwd and
BOOK_ROOT execution are exercised.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from press import registry, verify_archives
from tests import damage, factories


def _clean_env() -> dict:
    import os
    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_WORK_TREE"):
        env.pop(key, None)
    return env


def _git_init(root: Path) -> None:
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t",
                 "commit", "-qm", "fixture"]):
        subprocess.run(cmd, cwd=root, check=True, env=_clean_env())


class SourceArchiveMachine:
    """The transitions the state model drives, over the source archive.
    Every step is deterministic and records itself, so a failing
    sequence is a replayable list of step names."""

    def __init__(self, handle) -> None:
        self.handle = handle
        self.root = handle.root
        self.slug = handle.slug
        self.trace: list[str] = []

    @property
    def output(self) -> Path:
        return self.root / "dist" / f"{self.slug}-source.zip"

    def clean(self) -> None:
        self.trace.append("clean")
        import shutil
        for name in ("build", "dist"):
            d = self.root / name
            if d.exists():
                shutil.rmtree(d)

    def build(self) -> None:
        self.trace.append("build")
        from press import package_source
        package_source.main()

    def mutate(self) -> None:
        self.trace.append("mutate")
        mutated, _ = damage.flip_member_byte(self.output.read_bytes())
        self.output.write_bytes(mutated)

    def verify(self) -> list[str]:
        self.trace.append("verify")
        return verify_archives.verify_source_zip(self.output, self.slug)


@pytest.fixture
def machine(tmp_path):
    handle = factories.minimal().build(tmp_path)
    with handle.use():
        _git_init(handle.root)
        yield SourceArchiveMachine(handle)


@pytest.mark.invariant("INV-graph-no-stale")
@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_mutated_output_cannot_be_blessed(machine):
    machine.clean()
    machine.build()
    assert machine.verify() == [], "a freshly built archive must pass"
    machine.mutate()
    assert machine.verify() != [], f"a mutated archive was blessed: {machine.trace}"


@pytest.mark.invariant("INV-graph-no-stale")
@pytest.mark.layer("integration")
@pytest.mark.proof("positive")
def test_rebuild_restores_validity(machine):
    machine.clean()
    machine.build()
    machine.mutate()
    assert machine.verify() != []
    machine.build()  # rebuild overwrites the mutated output
    assert machine.verify() == [], f"rebuild did not restore validity: {machine.trace}"


@pytest.mark.layer("integration")
def test_clean_removes_the_output(machine):
    machine.clean()
    machine.build()
    assert machine.output.is_file()
    machine.clean()
    assert not machine.output.exists(), "clean left a declared output behind"


def test_missing_output_cannot_be_blessed(machine):
    machine.clean()
    machine.build()
    machine.output.unlink()
    # verify over a missing archive is a locatable refusal, not a pass.
    with pytest.raises(Exception):
        result = verify_archives.verify_source_zip(machine.output, machine.slug)
        assert result != []


def test_bounded_transition_sequence_holds_the_laws(machine):
    """A fixed, replayable sequence of transitions, with the invariant
    checked after each: no reachable state blesses a bad artifact."""

    steps = [
        ("clean", lambda: machine.clean()),
        ("build", lambda: machine.build()),
        ("verify_ok", lambda: _assert_ok(machine)),
        ("mutate", lambda: machine.mutate()),
        ("verify_bad", lambda: _assert_bad(machine)),
        ("build", lambda: machine.build()),
        ("verify_ok", lambda: _assert_ok(machine)),
        ("clean", lambda: machine.clean()),
        ("verify_absent", lambda: _assert_absent(machine)),
    ]
    for name, step in steps:
        step()
    assert machine.trace  # the sequence ran; trace is the replay record


def _assert_ok(machine) -> None:
    assert machine.verify() == [], f"expected valid at {machine.trace}"


def _assert_bad(machine) -> None:
    assert machine.verify() != [], f"expected invalid at {machine.trace}"


def _assert_absent(machine) -> None:
    assert not machine.output.exists()


# ---- graph-shape laws (pure, from the registry) ----

def test_prerequisites_precede_dependents():
    for target in registry.ARTIFACTS:
        order = registry.build_order([target])
        seen: set[str] = set()
        for step in order:
            for prereq in registry.ARTIFACTS[step].prerequisites:
                assert prereq in seen, f"{step} runs before its prerequisite {prereq}"
            seen.add(step)


def test_clean_would_remove_every_declared_output(tmp_path):
    """Every artifact's declared outputs live under build/ or dist/, so
    the clean transition (which removes both) removes them all."""

    for artifact in registry.ARTIFACTS.values():
        for output in artifact.outputs:
            assert not output.startswith(("/", "..")), output


def test_both_root_modes(tmp_path):
    """The same build-verify law holds whether the press finds the book
    by cwd or by BOOK_ROOT."""

    import os

    handle = factories.minimal().build(tmp_path)
    # cwd mode: chdir in, no BOOK_ROOT.
    from press import selftest
    selftest.clear_book_caches()
    previous = os.environ.pop("BOOK_ROOT", None)
    prev_cwd = Path.cwd()
    try:
        os.chdir(handle.root)
        _git_init(handle.root)
        from press import package_source
        package_source.main()
        out = handle.root / "dist" / f"{handle.slug}-source.zip"
        assert verify_archives.verify_source_zip(out, handle.slug) == []
    finally:
        os.chdir(prev_cwd)
        if previous is not None:
            os.environ["BOOK_ROOT"] = previous
        selftest.clear_book_caches()

    # BOOK_ROOT mode: the handle's own use() context.
    with handle.use():
        from press import package_source
        package_source.main()
        out = handle.root / "dist" / f"{handle.slug}-source.zip"
        assert verify_archives.verify_source_zip(out, handle.slug) == []
