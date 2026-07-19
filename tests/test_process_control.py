"""Deterministic tests for the single-child process controller.

Every test injects a scripted fake process -- never a real child, never a
sleep, never a wall clock. Correctness is asserted from active signals: the
argv the launcher was handed, the lines delivered to the sink with their
channel, the exact verdict, the cancellation stage, and the refusal raised
before a second launch. The fake's end-of-output sentinel and scripted exit
code stand in for the completion signals a real child would emit.
"""

from __future__ import annotations

from collections import deque
from typing import Mapping, Optional, Sequence

import pytest

from press.process_control import (
    CancelStage,
    ControllerStateError,
    Invocation,
    OutputChannel,
    Outcome,
    ProcessController,
    RunState,
    SingleChildError,
    SpawnError,
    SpawnedProcess,
)
from press.results import ConfigError

STDOUT = OutputChannel.STDOUT
STDERR = OutputChannel.STDERR


# --------------------------------------------------------------------------
# Fakes: a scripted process and a recording launcher. No real subprocess.
# --------------------------------------------------------------------------


class FakeProcess:
    """A ``SpawnedProcess`` that replays scripted lines and a scripted exit.

    ``lines`` are handed out one per :meth:`read_line`; once exhausted it
    returns ``None`` (the end-of-output signal). :meth:`interrupt` may run an
    injected ``on_interrupt`` hook (to model the child reacting -- emitting a
    last line and flipping its exit code) or raise ``interrupt_error`` (to
    model the OS refusing the signal). Every signal is recorded so a test
    asserts on what the controller actually did."""

    def __init__(
        self,
        lines: Sequence[tuple[OutputChannel, str]] = (),
        returncode: int = 0,
        *,
        on_interrupt: Optional[object] = None,
        interrupt_error: Optional[BaseException] = None,
        terminate_error: Optional[BaseException] = None,
    ) -> None:
        self._lines: deque[tuple[OutputChannel, str]] = deque(lines)
        self.returncode = returncode
        self._on_interrupt = on_interrupt
        self._interrupt_error = interrupt_error
        self._terminate_error = terminate_error
        self.interrupts = 0
        self.terminates = 0
        self.waited = False

    def set_lines(self, lines: Sequence[tuple[OutputChannel, str]]) -> None:
        self._lines = deque(lines)

    def read_line(self) -> Optional[tuple[OutputChannel, str]]:
        if self._lines:
            return self._lines.popleft()
        return None

    def interrupt(self) -> None:
        self.interrupts += 1
        if self._interrupt_error is not None:
            raise self._interrupt_error
        if self._on_interrupt is not None:
            self._on_interrupt(self)

    def terminate(self) -> None:
        self.terminates += 1
        if self._terminate_error is not None:
            raise self._terminate_error

    def wait(self) -> int:
        self.waited = True
        return self.returncode


class RecordingSpawn:
    """A ``Spawn`` that records each launch and returns a scripted process,
    or raises a scripted error to model a launch failure."""

    def __init__(
        self,
        process: Optional[SpawnedProcess] = None,
        *,
        error: Optional[BaseException] = None,
    ) -> None:
        self.process = process
        self.error = error
        self.calls: list[tuple[tuple[str, ...], str, Optional[dict[str, str]]]] = []

    def __call__(
        self,
        argv: Sequence[str],
        cwd: str,
        env: Optional[Mapping[str, str]] = None,
    ) -> SpawnedProcess:
        self.calls.append((tuple(argv), cwd, dict(env) if env is not None else None))
        if self.error is not None:
            raise self.error
        assert self.process is not None
        return self.process


class Sink:
    """Records every streamed line with its channel, in arrival order."""

    def __init__(self) -> None:
        self.lines: list[tuple[OutputChannel, str]] = []

    def __call__(self, channel: OutputChannel, text: str) -> None:
        self.lines.append((channel, text))


def controller(spawn: RecordingSpawn, *, root: str = "/book") -> ProcessController:
    return ProcessController(root, python="/usr/bin/python3", spawn=spawn)


# --------------------------------------------------------------------------
# Invocation: cataloged, array-built, never a shell string.
# --------------------------------------------------------------------------


def test_invocation_builds_an_argv_array_not_a_shell_string():
    inv = Invocation.of("publish", "kdp", "--report-only")
    assert inv.argv("/usr/bin/python3") == [
        "/usr/bin/python3", "-m", "press", "publish", "kdp", "--report-only",
    ]
    assert inv.cli == "press publish kdp --report-only"


def test_invocation_rejects_an_uncataloged_target():
    with pytest.raises(ConfigError):
        Invocation.of("rm -rf /")


def test_invocation_rejects_a_nul_in_args():
    with pytest.raises(ConfigError):
        Invocation.of("check", "a\x00b")


# --------------------------------------------------------------------------
# The happy path: stream, then the exact verdict.
# --------------------------------------------------------------------------


def test_run_streams_lines_then_reports_the_exact_return_code():
    process = FakeProcess(
        [(STDOUT, "building"), (STDERR, "a warning"), (STDOUT, "done")],
        returncode=0,
    )
    spawn = RecordingSpawn(process)
    ctl = controller(spawn)
    sink = Sink()

    outcome = ctl.run(Invocation.of("check"), sink)

    assert outcome == Outcome(returncode=0, cancelled=False, cancel_stage=CancelStage.NONE)
    assert outcome.succeeded is True
    assert sink.lines == [
        (STDOUT, "building"), (STDERR, "a warning"), (STDOUT, "done"),
    ]
    assert ctl.state == RunState.DONE
    assert process.waited is True


def test_launch_carries_the_argv_book_root_and_env():
    process = FakeProcess([], returncode=0)
    spawn = RecordingSpawn(process)
    ctl = controller(spawn, root="/somewhere/book")

    ctl.run(Invocation.of("pdf"), Sink(), env={"TERM": "dumb"})

    argv, cwd, env = spawn.calls[0]
    assert argv == ("/usr/bin/python3", "-m", "press", "pdf")
    assert cwd == "/somewhere/book"
    assert env == {"TERM": "dumb"}


def test_a_nonzero_child_is_not_success_but_the_code_is_verbatim():
    process = FakeProcess([(STDERR, "boom")], returncode=7)
    ctl = controller(RecordingSpawn(process))

    outcome = ctl.run(Invocation.of("verify"), Sink())

    assert outcome.returncode == 7
    assert outcome.succeeded is False
    assert outcome.terminated_by_signal is False


def test_a_signalled_child_reports_the_negative_code_verbatim():
    process = FakeProcess([], returncode=-signal_int())
    ctl = controller(RecordingSpawn(process))

    outcome = ctl.run(Invocation.of("all"), Sink())

    assert outcome.returncode == -signal_int()
    assert outcome.terminated_by_signal is True
    assert outcome.succeeded is False


def signal_int() -> int:
    # SIGINT, named without importing signal into the test's assertions.
    return 2


def test_partial_final_line_with_no_newline_is_still_delivered():
    # The controller streams whatever lines the process yields; a trailing
    # fragment without a newline is a line like any other.
    process = FakeProcess([(STDOUT, "half a line")], returncode=0)
    ctl = controller(RecordingSpawn(process))
    sink = Sink()

    ctl.run(Invocation.of("wordcount"), sink)

    assert sink.lines == [(STDOUT, "half a line")]


def test_interleaved_channels_retain_order_and_identity():
    lines = [
        (STDOUT, "1"), (STDERR, "2"), (STDERR, "3"), (STDOUT, "4"), (STDERR, "5"),
    ]
    process = FakeProcess(lines, returncode=0)
    ctl = controller(RecordingSpawn(process))
    sink = Sink()

    ctl.run(Invocation.of("style"), sink)

    assert sink.lines == lines


# --------------------------------------------------------------------------
# The single-child invariant: a second launch is refused before spawning.
# --------------------------------------------------------------------------


def test_second_start_while_running_is_refused_without_launching():
    process = FakeProcess([(STDOUT, "one")], returncode=0)
    spawn = RecordingSpawn(process)
    ctl = controller(spawn)

    ctl.start(Invocation.of("check"))
    assert ctl.state == RunState.RUNNING
    assert len(spawn.calls) == 1

    with pytest.raises(SingleChildError):
        ctl.start(Invocation.of("pdf"))

    # Refused before any launch: still exactly one spawn, first run intact.
    assert len(spawn.calls) == 1
    assert ctl.state == RunState.RUNNING
    assert ctl.invocation == Invocation.of("check")


def test_controller_is_reusable_after_a_run_completes():
    first = FakeProcess([(STDOUT, "a")], returncode=0)
    second = FakeProcess([(STDOUT, "b")], returncode=3)
    spawn = RecordingSpawn(first)
    ctl = controller(spawn)

    assert ctl.run(Invocation.of("check"), Sink()).returncode == 0
    assert ctl.state == RunState.DONE

    spawn.process = second
    assert ctl.run(Invocation.of("verify"), Sink()).returncode == 3
    assert len(spawn.calls) == 2


# --------------------------------------------------------------------------
# Spawn failure: no child, no verdict, controller freed for a retry.
# --------------------------------------------------------------------------


def test_spawn_failure_raises_spawn_error_and_frees_the_controller():
    spawn = RecordingSpawn(error=OSError("No such file or directory"))
    ctl = controller(spawn)

    with pytest.raises(SpawnError):
        ctl.start(Invocation.of("check"))

    assert ctl.state == RunState.IDLE
    assert ctl.is_running is False
    # The controller is not wedged: a corrected attempt may follow.
    spawn.error = None
    spawn.process = FakeProcess([(STDOUT, "ok")], returncode=0)
    assert ctl.run(Invocation.of("check"), Sink()).succeeded is True


# --------------------------------------------------------------------------
# Cancellation: explicit stages, and never reported as success.
# --------------------------------------------------------------------------


def test_cancel_requests_sigint_and_reaches_terminated():
    # The child reacts to SIGINT by emitting a last line and exiting -2.
    def react(proc: FakeProcess) -> None:
        proc.set_lines([(STDERR, "interrupted")])
        proc.returncode = -2

    process = FakeProcess([(STDOUT, "working")], returncode=0, on_interrupt=react)
    ctl = controller(RecordingSpawn(process))
    sink = Sink()

    ctl.start(Invocation.of("all"))
    assert ctl.poll(sink) is True          # "working"
    ctl.cancel()
    assert ctl.state == RunState.CANCELLING
    assert ctl.cancel_stage == CancelStage.ACKNOWLEDGED
    assert process.interrupts == 1

    assert ctl.poll(sink) is True          # "interrupted"
    assert ctl.poll(sink) is False         # end-of-output signal
    outcome = ctl.finish()

    assert outcome.cancelled is True
    assert outcome.cancel_stage == CancelStage.TERMINATED
    assert outcome.returncode == -2
    assert outcome.succeeded is False
    assert sink.lines == [(STDOUT, "working"), (STDERR, "interrupted")]


def test_cancel_race_a_zero_exit_after_cancel_is_still_not_success():
    # The child happens to exit 0, but the operator cancelled: not success.
    process = FakeProcess([(STDOUT, "line")], returncode=0)
    ctl = controller(RecordingSpawn(process))
    sink = Sink()

    ctl.start(Invocation.of("check"))
    ctl.cancel()
    while ctl.poll(sink):
        pass
    outcome = ctl.finish()

    assert outcome.returncode == 0
    assert outcome.cancelled is True
    assert outcome.succeeded is False
    assert outcome.cancel_stage == CancelStage.TERMINATED


def test_second_cancel_escalates_to_terminate():
    process = FakeProcess([(STDOUT, "stubborn")], returncode=-15)
    ctl = controller(RecordingSpawn(process))
    sink = Sink()

    ctl.start(Invocation.of("all"))
    ctl.cancel()                            # SIGINT
    ctl.cancel()                            # escalate to SIGTERM
    assert process.interrupts == 1
    assert process.terminates == 1
    assert ctl.state == RunState.CANCELLING

    while ctl.poll(sink):
        pass
    outcome = ctl.finish()
    assert outcome.cancelled is True
    assert outcome.returncode == -15


def test_cancel_whose_signal_is_refused_is_failed_not_success():
    process = FakeProcess(
        [(STDOUT, "gone")], returncode=0, interrupt_error=ProcessLookupError("no such process")
    )
    ctl = controller(RecordingSpawn(process))
    sink = Sink()

    ctl.start(Invocation.of("check"))
    ctl.cancel()
    assert ctl.cancel_stage == CancelStage.FAILED

    while ctl.poll(sink):
        pass
    outcome = ctl.finish()

    assert outcome.cancelled is True
    assert outcome.cancel_stage == CancelStage.FAILED
    assert outcome.succeeded is False


# --------------------------------------------------------------------------
# API misuse is an explicit error, distinct from any child outcome.
# --------------------------------------------------------------------------


def test_poll_before_start_is_a_state_error():
    ctl = controller(RecordingSpawn(FakeProcess()))
    with pytest.raises(ControllerStateError):
        ctl.poll(Sink())


def test_finish_before_start_is_a_state_error():
    ctl = controller(RecordingSpawn(FakeProcess()))
    with pytest.raises(ControllerStateError):
        ctl.finish()


def test_cancel_before_start_is_a_state_error():
    ctl = controller(RecordingSpawn(FakeProcess()))
    with pytest.raises(ControllerStateError):
        ctl.cancel()
