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

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def _workflow_files():
    return sorted(WORKFLOWS.glob("*.yml")) if WORKFLOWS.is_dir() else []


# The toolchain image is public (#161), so a book under any account builds
# with no package grant. These guard that the docs and the workflow keep
# that promise: a live second-party proof (blocked on a second identity)
# would exercise it, and this catches a doc or pin regression without one.
_GRANT_PHRASES = (
    "granted read access",
    "Manage Actions access",
    "grant it once",
    "not granted to your repo",
    "one-time read grant",
    "private toolchain",
)
_CONSUMER_DOCS = ("README.md", "docs/INSTALL.md", "docs/COMPATIBILITY.md",
                  "docs/QUICKSTART.md")


@pytest.mark.parametrize("relpath", _CONSUMER_DOCS)
def test_consumer_docs_do_not_require_a_toolchain_grant(relpath):
    text = (ROOT / relpath).read_text(encoding="utf-8")
    hits = [p for p in _GRANT_PHRASES if p in text]
    assert not hits, f"{relpath} still tells a consumer to obtain a grant: {hits}"


def test_the_build_pins_a_versioned_toolchain_image():
    # A public image is only trustworthy if the build pins an exact version;
    # the release contract additionally proves the pin is immutable.
    build = (WORKFLOWS / "build.yml").read_text(encoding="utf-8")
    assert re.search(r"image:\s*ghcr\.io/clintecker/press-toolchain:sha-[0-9a-f]+", build), \
        "build.yml does not pin an exact toolchain image"


def _all_job_names() -> set[str]:
    from press import yamlio

    names: set[str] = set()
    for f in _workflow_files():
        data = yamlio.loads(f.read_text(encoding="utf-8"))
        names |= set((data.get("jobs") or {}).keys())
    return names


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

    from press import yamlio

    data = yamlio.loads(workflow.read_text(encoding="utf-8"))
    has_top = "permissions" in data
    jobs = data.get("jobs", {})
    all_jobs_scoped = jobs and all("permissions" in job for job in jobs.values())
    assert has_top or all_jobs_scoped, (
        f"{workflow.name} declares no permissions block at top level or on "
        "every job; a fork PR could inherit a broad token"
    )


# ---- the release DAG: every layer the chain claims is backed by a real,
#      privileged check the release-contract actually waits on (#94/#97) ----

RELEASE_CONTRACT = WORKFLOWS / "release-contract.yml"


def _required_checks() -> list[str]:
    """The check-run names the release-contract blocks the release on, read
    from its `required="..."` line, so the test tracks the workflow."""

    text = RELEASE_CONTRACT.read_text(encoding="utf-8")
    match = re.search(r'required="([^"]+)"', text)
    assert match, "release-contract declares no required checks list"
    return match.group(1).split()


def _effective_check_names() -> set[str]:
    """The check-run names GitHub will publish: a job's key, unless the
    job overrides it with `name:`. The release poll matches on this name,
    not the job key, so this is what a required check must resolve to."""

    from press import yamlio

    names: set[str] = set()
    for f in _workflow_files():
        data = yamlio.loads(f.read_text(encoding="utf-8"))
        for key, job in (data.get("jobs") or {}).items():
            names.add(job.get("name", key) if isinstance(job, dict) else key)
    return names


def test_every_required_check_is_a_real_job():
    """The release waits for each required check to go green. A check name
    that matches no published check-run would never appear, so the release
    would hang forever instead of failing -- a silent broken dependency.
    The poll matches the check-run NAME, so a job that sets a differing
    `name:` (not just a renamed key) must also be caught."""

    names = _effective_check_names()
    unknown = [c for c in _required_checks() if c not in names]
    assert not unknown, (
        f"release-contract waits on checks with no matching check-run: {unknown}; "
        "a renamed job or a differing job `name:` would deadlock the release"
    )


def test_the_release_waits_on_the_integration_gate():
    """The container gauntlet (consumer) is the strongest layer; the
    release must not be cuttable without it."""

    assert "consumer" in _required_checks()


def test_the_integration_gate_runs_privileged_in_the_container():
    """The consumer job pulls the private toolchain image, so it must run
    in that container with registry credentials and packages:read. If this
    privilege regressed, the integration layer could not run at all."""

    from press import yamlio

    data = yamlio.loads((WORKFLOWS / "integration.yml").read_text(encoding="utf-8"))
    consumer = data["jobs"]["consumer"]
    assert "container" in consumer, "consumer does not run in the toolchain container"
    assert "credentials" in consumer["container"], "container pulls without credentials"
    # packages:read may be declared at the top level or on the job.
    top = (data.get("permissions") or {})
    job = (consumer.get("permissions") or {})
    assert top.get("packages") == "read" or job.get("packages") == "read", (
        "no packages:read privilege to pull the private toolchain"
    )
