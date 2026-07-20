"""Git subprocesses observe only their own repository, even when an ambient
repo-binding GIT_* variable is set (#176).

A `git commit` runs its hooks with GIT_INDEX_FILE (and often GIT_DIR,
GIT_PREFIX) pointing at the outer commit's transient index. When the test
suite -- or press itself -- then builds or inspects a nested/independent
repository, those calls must not consult the outer index. The production
process runner strips the repo-binding GIT_* for every git command it runs,
so the leak is closed at the one boundary all git calls pass through, not
patched ad hoc per call site.
"""

from __future__ import annotations

import subprocess

import pytest

from press.adapters.production import SubprocessRunner

pytestmark = pytest.mark.layer("integration")


def _init_repo(path):
    env = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t",
                 "commit", "-qm", "seed"]):
        subprocess.run(cmd, cwd=path, check=True, env={**_clean_env(), **env})


def _clean_env() -> dict:
    import os
    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_PREFIX"):
        env.pop(key, None)
    return env


def test_ambient_git_index_does_not_hide_a_nested_repos_files(tmp_path, monkeypatch):
    repo = tmp_path / "book"
    repo.mkdir()
    (repo / "chapter.md").write_text("one two three", encoding="utf-8")
    _init_repo(repo)

    # Simulate a commit hook: a foreign, non-existent index and git dir.
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "outer-index.lock"))
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "outer.git"))

    result = SubprocessRunner().run(
        ["git", "-C", str(repo), "ls-files", "-z"], capture=True, check=True)
    listed = result.stdout.decode().split("\0")
    assert "chapter.md" in listed, "ambient GIT_INDEX_FILE hid the repo's tracked files"


def test_an_explicitly_injected_git_env_is_respected(tmp_path, monkeypatch):
    # When a caller passes env deliberately (git is the subject under test),
    # the runner uses it verbatim and does not strip GIT_* from it.
    repo = tmp_path / "book"
    repo.mkdir()
    (repo / "a.md").write_text("x", encoding="utf-8")
    _init_repo(repo)

    alt_index = tmp_path / "alt.index"
    env = {**_clean_env(), "GIT_INDEX_FILE": str(alt_index)}
    # Staging into the alternate index must land there, not the repo's real
    # index -- proof the explicit env is honored.
    SubprocessRunner().run(
        ["git", "-C", str(repo), "add", "a.md"], env=env, check=True)
    assert alt_index.is_file(), "explicit GIT_INDEX_FILE was stripped, not honored"
