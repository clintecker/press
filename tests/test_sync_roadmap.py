"""The roadmap reconcile boundary, and the CI posture that grants it write.

`scripts/sync_roadmap.py --apply-github` is the one place the press exercises
GitHub *write* authority. It reconciles milestone title/state/description for
milestone numbers already in the reviewed registry -- never creating, deleting,
or editing an issue. These tests drive that reconcile against a fake GitHub
boundary (no network, no `gh`) and prove the no-op, patch, retry, partial-
failure, unknown-milestone, and malicious-registry cases; a companion block
proves the workflow only grants the write on a push to main, with least
privilege and a concurrency guard, so a fork PR or the projection path can
never obtain it.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "roadmap.yml"


def _load():
    path = ROOT / "scripts" / "sync_roadmap.py"
    spec = importlib.util.spec_from_file_location("sync_roadmap", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


sr = _load()


REPO = "acme/book"


def _milestone(number: int, *, title: str, state: str = "open", description: str = "d") -> dict:
    return {
        "number": number,
        "group": "complete" if state == "closed" else "active-v1",
        "title": title,
        "state": state,
        "description": description,
    }


def _registry(*milestones: dict) -> dict:
    return {"repository": REPO, "milestones": list(milestones)}


class FakeGitHub:
    """A faithful stand-in for the `gh` callable used by the reconcile.

    It answers the two argv shapes the reconcile emits -- a milestone GET and a
    milestone PATCH -- from an in-memory store, records every call, and can be
    told to raise a transient error (retryable) or to treat a milestone number
    as absent (a definitive 404). It refuses any other endpoint or method, so a
    reconcile that tried to create/delete a milestone or touch an issue would
    trip an assertion here rather than pass silently.
    """

    def __init__(self, store: dict[int, dict], *, absent: set[int] | None = None):
        self.store = {n: dict(v) for n, v in store.items()}
        self.absent = absent or set()
        self.calls: list[tuple[tuple, str | None]] = []
        # number -> remaining transient failures to raise before succeeding.
        self.transient: dict[int, int] = {}

    def _number(self, endpoint: str) -> int:
        assert endpoint.startswith(f"repos/{REPO}/milestones/"), endpoint
        return int(endpoint.rsplit("/", 1)[1])

    def __call__(self, *args, input_data=None):
        self.calls.append((args, input_data))
        assert args[0] == "api", f"unexpected gh subcommand: {args!r}"
        # A GET: ("api", endpoint)
        if len(args) == 2:
            endpoint = args[1]
            number = self._number(endpoint)
            if number in self.absent:
                raise sr.MilestoneNotFound("HTTP 404: Not Found")
            self._maybe_transient(number)
            return dict(self.store[number])
        # A PATCH: ("api", "--method", "PATCH", endpoint, "--input", "-")
        assert args[1] == "--method", f"unexpected write shape: {args!r}"
        assert args[2] == "PATCH", f"reconcile must only PATCH, got {args[2]!r}"
        endpoint = args[3]
        number = self._number(endpoint)
        assert "issues" not in endpoint, "reconcile must never touch issues"
        self._maybe_transient(number)
        payload = json.loads(input_data)
        assert set(payload) <= {"title", "state", "description"}, payload
        self.store[number].update(payload)
        return dict(self.store[number])

    def _maybe_transient(self, number: int) -> None:
        left = self.transient.get(number, 0)
        if left > 0:
            self.transient[number] = left - 1
            raise sr.GhError("HTTP 502: Bad Gateway")

    def methods(self) -> list[str]:
        out = []
        for args, _ in self.calls:
            out.append("PATCH" if len(args) > 2 and args[1] == "--method" else "GET")
        return out


def _no_sleep(_seconds: float) -> None:  # retries must not wait in tests
    return None


# ---------------------------------------------------------------- no-op ----

def test_reconcile_noop_makes_no_writes_and_reports_success(capsys):
    data = _registry(_milestone(4, title="v2"))
    fake = FakeGitHub({4: _milestone(4, title="v2")})
    rc = sr.github_drift(data, apply=True, api=fake, env={}, sleep=_no_sleep)
    assert rc == 0
    assert fake.methods() == ["GET"], "a matching milestone must not be PATCHed"


# ---------------------------------------------------------------- patch ----

def test_reconcile_patches_only_drifted_fields_for_registry_numbers(capsys):
    data = _registry(
        _milestone(4, title="v2 — Composable press", state="open", description="new body"),
        _milestone(5, title="v3", state="open", description="same"),
    )
    fake = FakeGitHub({
        4: _milestone(4, title="v2 — old", state="closed", description="old body"),
        5: _milestone(5, title="v3", state="open", description="same"),
    })
    rc = sr.github_drift(data, apply=True, api=fake, env={}, sleep=_no_sleep)
    assert rc == 0
    # milestone 4 drifted (title/state/description) and was PATCHed; 5 matched.
    assert fake.methods() == ["GET", "PATCH", "GET"]
    assert fake.store[4]["title"] == "v2 — Composable press"
    assert fake.store[4]["state"] == "open"
    assert fake.store[4]["description"] == "new body"


def test_apply_is_idempotent_second_run_is_a_noop():
    data = _registry(_milestone(4, title="v2", description="body"))
    fake = FakeGitHub({4: _milestone(4, title="stale", description="old")})
    assert sr.github_drift(data, apply=True, api=fake, env={}, sleep=_no_sleep) == 0
    fake.calls.clear()
    assert sr.github_drift(data, apply=True, api=fake, env={}, sleep=_no_sleep) == 0
    assert fake.methods() == ["GET"], "reconciled state must not PATCH again"


# ------------------------------------------------ partial failure / retry ----

def test_transient_failure_is_retried_then_succeeds():
    data = _registry(_milestone(4, title="v2", description="body"))
    fake = FakeGitHub({4: _milestone(4, title="stale", description="old")})
    fake.transient[4] = 2  # first two calls blow up, third succeeds
    rc = sr.github_drift(data, apply=True, api=fake, env={}, sleep=_no_sleep, retries=2)
    assert rc == 0
    assert fake.store[4]["title"] == "v2"


def test_exhausted_retries_fail_the_run_and_do_not_bless_github(capsys):
    data = _registry(_milestone(4, title="v2", description="body"))
    fake = FakeGitHub({4: _milestone(4, title="stale", description="old")})
    fake.transient[4] = 99  # never recovers within the retry budget
    rc = sr.github_drift(data, apply=True, api=fake, env={}, sleep=_no_sleep, retries=2)
    assert rc == 1, "a persistent failure must turn the job red"
    err = capsys.readouterr().err
    assert "reconcile failed" in err


def test_one_milestone_failing_does_not_abort_the_others():
    data = _registry(
        _milestone(4, title="v2", description="body"),
        _milestone(5, title="v3-new", description="body"),
    )
    fake = FakeGitHub({
        4: _milestone(4, title="stale", description="old"),
        5: _milestone(5, title="v3-old", description="old"),
    })
    fake.transient[4] = 99  # milestone 4 never recovers
    rc = sr.github_drift(data, apply=True, api=fake, env={}, sleep=_no_sleep, retries=1)
    assert rc == 1, "the run fails because milestone 4 could not be reconciled"
    assert fake.store[5]["title"] == "v3-new", "milestone 5 was still reconciled"


# ---------------------------------------------------- unknown milestone ----

def test_absent_milestone_is_skipped_never_created(capsys):
    data = _registry(
        _milestone(4, title="v2", description="body"),
        _milestone(9, title="ghost", description="body"),
    )
    fake = FakeGitHub({4: _milestone(4, title="stale", description="old")}, absent={9})
    rc = sr.github_drift(data, apply=True, api=fake, env={}, sleep=_no_sleep)
    assert rc == 0, "a registry milestone absent on GitHub is out of scope, not a failure"
    # 9 was GET (404) then skipped: never PATCHed, never created.
    assert fake.methods() == ["GET", "PATCH", "GET"]
    assert 9 not in fake.store
    assert "milestone 9 absent" in capsys.readouterr().err


def test_absent_milestone_is_not_retried():
    data = _registry(_milestone(9, title="ghost", description="body"))
    fake = FakeGitHub({}, absent={9})
    rc = sr.github_drift(data, apply=True, api=fake, env={}, sleep=_no_sleep, retries=5)
    assert rc == 0
    assert fake.methods() == ["GET"], "a 404 is definitive; it must not be retried"


# --------------------------------------------------- malicious registry ----

def test_malicious_registry_is_refused_by_validation_before_any_network():
    """A crafted registry (extra field smuggling a create instruction) is
    rejected by the schema before load_registry returns, so no boundary call
    is ever made. The write path is only reachable through validated data."""

    bad = {
        "schema_version": 2,
        "repository": REPO,
        "groups": [
            {"id": "active-v1", "heading": "H", "description": "D"},
            {"id": "complete", "heading": "H", "description": "D"},
        ],
        "milestones": [
            {
                "number": 4,
                "group": "active-v1",
                "title": "v2",
                "state": "open",
                "description": "body",
                "create_if_missing": True,  # smuggled field the schema forbids
            }
        ],
    }
    path = ROOT / "roadmap" / "milestones.json"
    original = path.read_text(encoding="utf-8")
    try:
        path.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(SystemExit):
            sr.load_registry()
    finally:
        path.write_text(original, encoding="utf-8")


def test_reconcile_never_issues_a_create_delete_or_issue_write():
    """Whatever the (validated) registry says, the reconcile only ever GETs
    and PATCHes milestones. The fake asserts endpoint/method, so a reconcile
    that tried to POST/DELETE a milestone or touch an issue would fail here."""

    data = _registry(
        _milestone(4, title="v2", description="new"),
        _milestone(5, title="v3", state="closed", description="new"),
    )
    fake = FakeGitHub({
        4: _milestone(4, title="old", description="old"),
        5: _milestone(5, title="v3", state="open", description="old"),
    })
    sr.github_drift(data, apply=True, api=fake, env={}, sleep=_no_sleep)
    assert set(fake.methods()) <= {"GET", "PATCH"}


# ------------------------------------------------------- durable summary ----

def test_apply_emits_a_durable_summary_linking_commit_and_changes(tmp_path):
    summary = tmp_path / "summary.md"
    data = _registry(_milestone(4, title="v2 — Composable press", description="new"))
    fake = FakeGitHub({4: _milestone(4, title="stale", description="old")})
    env = {"GITHUB_STEP_SUMMARY": str(summary), "GITHUB_SHA": "0123456789abcdef"}
    sr.github_drift(data, apply=True, api=fake, env=env, sleep=_no_sleep)
    text = summary.read_text(encoding="utf-8")
    assert "commit/0123456789abcdef" in text, "summary must link the source commit"
    assert "v2 — Composable press" in text and "milestone 4" in text


def test_summary_is_written_even_on_a_noop_run(tmp_path):
    summary = tmp_path / "summary.md"
    data = _registry(_milestone(4, title="v2"))
    fake = FakeGitHub({4: _milestone(4, title="v2")})
    env = {"GITHUB_STEP_SUMMARY": str(summary), "GITHUB_SHA": "deadbeefcafe"}
    sr.github_drift(data, apply=True, api=fake, env=env, sleep=_no_sleep)
    text = summary.read_text(encoding="utf-8")
    assert "No milestone metadata changes" in text
    assert "commit/deadbeefcafe" in text


def test_check_mode_never_writes_even_on_drift():
    data = _registry(_milestone(4, title="v2", description="new"))
    fake = FakeGitHub({4: _milestone(4, title="stale", description="old")})
    rc = sr.github_drift(data, apply=False, api=fake, env={}, sleep=_no_sleep)
    assert rc == 1, "drift under --check-github must be reported as failure"
    assert fake.methods() == ["GET"], "check mode must never PATCH"


# ============================================================ CI posture ====
# The reconcile is the one job that grants GitHub write. These prove the grant
# is fenced: push-to-main only, least privilege, concurrency-guarded, and never
# reachable by a pull_request (fork) or the projection path.


def _roadmap_yaml() -> dict:
    from press import yamlio

    return yamlio.loads(WORKFLOW.read_text(encoding="utf-8"))


def test_reconcile_job_runs_only_on_push_to_main():
    job = _roadmap_yaml()["jobs"]["reconcile"]
    guard = job["if"]
    assert "push" in guard and "refs/heads/main" in guard, guard


def test_reconcile_job_has_least_privilege_write():
    job = _roadmap_yaml()["jobs"]["reconcile"]
    perms = job["permissions"]
    assert perms == {"contents": "read", "issues": "write"}, perms


def test_reconcile_job_is_concurrency_guarded_against_stale_overwrites():
    job = _roadmap_yaml()["jobs"]["reconcile"]
    concurrency = job["concurrency"]
    assert "workflow" in concurrency["group"], concurrency
    assert concurrency["cancel-in-progress"] is True, concurrency


def test_reconcile_job_runs_the_apply_command():
    job = _roadmap_yaml()["jobs"]["reconcile"]
    steps = " ".join(str(s) for s in job["steps"])
    assert "--apply-github" in steps


def test_pull_request_path_has_no_milestone_write_authority():
    data = _roadmap_yaml()
    # Top-level permission is read-only; the projection job (which runs on PRs,
    # including forks) declares no write override.
    assert data["permissions"] == {"contents": "read"}
    projection = data["jobs"]["projection"]
    assert "permissions" not in projection or "write" not in str(projection["permissions"])
    # The only job that carries issues:write is reconcile (push-to-main gated).
    writers = [
        name for name, job in data["jobs"].items()
        if (job.get("permissions") or {}).get("issues") == "write"
    ]
    assert writers == ["reconcile"], writers


def test_drift_alarm_remains_read_only():
    job = _roadmap_yaml()["jobs"]["github-drift"]
    assert job["permissions"] == {"contents": "read", "issues": "read"}
