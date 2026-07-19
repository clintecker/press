"""Contract tests for the boundary adapters and their deterministic fakes.

The production adapters and the fakes satisfy the same Protocols, so where
it is practical the same behavioral assertion runs against both. Nothing
here touches the live network, ambient credentials, or the clock: the
process tests drive a portable, side-effect-free command (``true``/``false``
where present, otherwise the running interpreter), the environment tests use
a fixed map, and the HTTP and retry tests never leave memory.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

import pytest

from press import adapters
from press.adapters import fakes, production, protocols, retry
from press.results import PolicyError, ToolError


# --------------------------------------------------------------------------
# ProcessRunner: production and fake against one interface
# --------------------------------------------------------------------------


def test_subprocess_runner_returns_typed_result_and_captures():
    runner = production.SubprocessRunner()
    result = runner.run([sys.executable, "-c", "print('hi')"], capture=True)
    assert isinstance(result, protocols.ProcessResult)
    assert result.returncode == 0
    assert result.stdout.strip() == b"hi"


def test_subprocess_runner_leaves_streams_empty_when_not_capturing():
    runner = production.SubprocessRunner()
    result = runner.run([sys.executable, "-c", "pass"])
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr == b""


def test_subprocess_runner_raises_calledprocesserror_on_check():
    """The CLI boundary's exit-code translation depends on this exact
    exception propagating; the adapter must not swallow it."""

    runner = production.SubprocessRunner()
    with pytest.raises(subprocess.CalledProcessError):
        runner.run([sys.executable, "-c", "import sys; sys.exit(3)"], check=True)


def test_subprocess_runner_raises_timeout():
    runner = production.SubprocessRunner()
    with pytest.raises(subprocess.TimeoutExpired):
        runner.run([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.2)


def test_subprocess_runner_raises_oserror_on_missing_binary():
    runner = production.SubprocessRunner()
    with pytest.raises(OSError):
        runner.run(["press-no-such-binary-xyz"])


def test_fake_runner_records_argv_cwd_env_and_flags():
    fake = fakes.FakeProcessRunner()
    fake.run(["git", "status"], cwd="/repo", env={"A": "1"}, capture=True, timeout=15)
    assert len(fake.runs) == 1
    recorded = fake.runs[0]
    assert recorded.argv == ("git", "status")
    assert recorded.cwd == "/repo"
    assert recorded.env == {"A": "1"}
    assert recorded.capture is True
    assert recorded.timeout == 15
    assert fake.argvs == [("git", "status")]


def test_fake_runner_answers_by_command_and_from_queue():
    fake = fakes.FakeProcessRunner(
        results=[protocols.ProcessResult(0, b"first")],
        by_command={"git": protocols.ProcessResult(0, b"tracked\0files\0")},
    )
    # keyed by argv[0]
    assert fake.run(["git", "ls-files"]).stdout == b"tracked\0files\0"
    # falls through to the queue for other commands
    assert fake.run(["pandoc"]).stdout == b"first"
    # queue exhausted -> default clean result
    assert fake.run(["pandoc"]).returncode == 0


def test_fake_runner_raises_programmed_exception():
    fake = fakes.FakeProcessRunner(
        by_command={"git": subprocess.CalledProcessError(1, "git")}
    )
    with pytest.raises(subprocess.CalledProcessError):
        fake.run(["git", "ls-files"])


# --------------------------------------------------------------------------
# Environment: production and fake
# --------------------------------------------------------------------------


def test_os_environment_reads_live_values(monkeypatch):
    monkeypatch.setenv("PRESS_ADAPTER_PROBE", "yes")
    env = production.OsEnvironment()
    assert env.get("PRESS_ADAPTER_PROBE") == "yes"
    assert env.get("PRESS_ADAPTER_ABSENT_XYZ") is None
    assert env.copy()["PRESS_ADAPTER_PROBE"] == "yes"


def test_os_environment_which_matches_shutil():
    env = production.OsEnvironment()
    assert env.which("python-no-such-xyz") is None
    assert env.which(sys.executable.split("/")[-1]) == shutil.which(
        sys.executable.split("/")[-1]
    )


def test_fake_environment_answers_from_map_and_records_reads():
    env = fakes.FakeEnvironment(
        values={"OPENAI_API_KEY": "sk-test"}, present_tools=["claude"]
    )
    assert env.get("OPENAI_API_KEY") == "sk-test"
    assert env.get("MISSING", "fallback") == "fallback"
    assert env.which("claude") == "/usr/bin/claude"
    assert env.which("pandoc") is None
    assert env.reads == ["OPENAI_API_KEY", "MISSING"]
    assert env.which_calls == ["claude", "pandoc"]


# --------------------------------------------------------------------------
# HttpImageClient: fake records requests; production maps errors to HttpError
# --------------------------------------------------------------------------


def test_fake_image_client_records_json_request_and_answers():
    client = fakes.FakeImageClient(responses=[{"data": [{"b64_json": "AAA="}]}])
    body = client.post_json(
        "https://api.openai.com/v1/images/generations",
        {"model": "gpt-image-2", "prompt": "a cat"},
        {"Authorization": "Bearer x"},
    )
    assert body == {"data": [{"b64_json": "AAA="}]}
    assert len(client.requests) == 1
    request = client.requests[0]
    assert request.kind == "json"
    assert request.url.endswith("/generations")
    assert request.payload["prompt"] == "a cat"
    assert request.headers["Authorization"] == "Bearer x"


def test_fake_image_client_records_multipart_and_raises_when_exhausted():
    client = fakes.FakeImageClient(responses=[])
    with pytest.raises(PolicyError):
        client.post_json("https://x/y", {}, {})
    # the request was still recorded before the (missing) answer
    assert client.requests[0].url == "https://x/y"


def test_http_error_is_a_tool_error_with_source_and_code():
    err = production.HttpError("api.openai.com", 429, "rate limited")
    assert isinstance(err, ToolError)
    assert err.host == "api.openai.com"
    assert err.code == 429
    assert err.detail == "rate limited"
    assert err.source == "api.openai.com"


def test_fake_image_client_can_raise_http_error():
    boom = production.HttpError("generativelanguage.googleapis.com", 400, "bad")
    client = fakes.FakeImageClient(responses=[boom])
    with pytest.raises(production.HttpError):
        client.post_json("https://generativelanguage.googleapis.com/x", {}, {})


# --------------------------------------------------------------------------
# Retry: deterministic, budget-bounded, no clock
# --------------------------------------------------------------------------


def test_retry_resolves_on_first_terminal_state_and_stops_early():
    source = fakes.ScriptedRetrySource(states=["pending", "pending", "ready", "late"])
    result = retry.resolve(
        source, retry.RetryBudget(10), is_terminal=lambda s: s == "ready"
    )
    assert result == "ready"
    # it stopped as soon as "ready" arrived; "late" was never polled
    assert source.remaining() == 1


def test_retry_exhausts_budget_before_source_and_raises_policyerror():
    source = fakes.ScriptedRetrySource(states=["pending"] * 5)
    with pytest.raises(PolicyError):
        retry.resolve(
            source, retry.RetryBudget(3), is_terminal=lambda s: s == "ready"
        )
    # only the budgeted number of polls happened
    assert source.remaining() == 2


def test_retry_source_past_end_is_policyerror_not_a_hang():
    source = fakes.ScriptedRetrySource(states=["pending"])
    with pytest.raises(PolicyError):
        retry.resolve(
            source, retry.RetryBudget(3), is_terminal=lambda s: s == "ready"
        )


def test_retry_budget_must_permit_at_least_one_attempt():
    with pytest.raises(PolicyError):
        retry.RetryBudget(0)


def test_retry_is_deterministic_across_runs():
    def once():
        source = fakes.ScriptedRetrySource(states=[1, 2, 3, 4])
        return retry.resolve(source, retry.RetryBudget(10), is_terminal=lambda s: s == 3)

    assert once() == once() == 3


# --------------------------------------------------------------------------
# Package-level exports and default singletons
# --------------------------------------------------------------------------


def test_default_singletons_are_the_production_adapters():
    assert isinstance(adapters.process_runner, production.SubprocessRunner)
    assert isinstance(adapters.environment, production.OsEnvironment)
    assert isinstance(adapters.image_client, production.UrllibImageClient)
