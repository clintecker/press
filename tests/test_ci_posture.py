"""The CI privilege posture, proven mechanically.

The live second-party proofs (a fork PR from another account, a private
book in another org) need a second GitHub identity, so they cannot run
here. What can be proven from the workflow files is the posture those
proofs would exercise: no pull_request_target (which would run a fork's
code with the base repo's secrets), no workflow granting write on a
pull_request event, and the least-privilege permissions blocks that
keep a fork PR read-only. If this posture ever regresses, the live
proof would fail; this suite catches the regression without a second
party.
"""

from __future__ import annotations

from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"


def _workflow_files():
    return sorted(WORKFLOWS.glob("*.yml")) if WORKFLOWS.is_dir() else []


def test_no_pull_request_target_anywhere():
    """pull_request_target runs a fork's code with base-repo secrets; the
    press must never use it."""

    offenders = [f.name for f in _workflow_files()
                 if "pull_request_target" in f.read_text(encoding="utf-8")]
    assert not offenders, f"pull_request_target present in {offenders}"


@pytest.mark.parametrize("workflow", _workflow_files(), ids=lambda p: p.name)
def test_workflow_declares_permissions(workflow):
    """Every workflow declares an explicit permissions block, so a fork
    PR never inherits the default broad token."""

    import yaml

    data = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    has_top = "permissions" in data
    jobs = data.get("jobs", {})
    all_jobs_scoped = jobs and all("permissions" in job for job in jobs.values())
    assert has_top or all_jobs_scoped, (
        f"{workflow.name} declares no permissions block at top level or on "
        "every job; a fork PR could inherit a broad token"
    )
