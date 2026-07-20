"""A single-child process controller with exact verdict semantics.

The desk (issue #105) must stream a long-running press command without
blocking its UI, but subprocess lifecycle, output framing, cancellation, and
the single-child invariant are a correctness boundary -- not something to
scatter through widgets. This module owns that boundary and nothing else: it
runs exactly one ``python -m press <target>`` child at a time in an explicit
book root, streams each output line to an injected sink with its channel
identity intact, and reports the child's **exact** return code as the verdict.
The return code is copied verbatim; it is never re-derived from output text,
and a cancelled run can never be reported as success.

The launch is injectable. The controller depends only on a ``Spawn`` callable
that yields a ``SpawnedProcess``; production supplies :func:`default_spawn`
(the one place a real ``subprocess`` is touched, since a process controller is
its rightful home), while every test injects a scripted fake process -- never
a real child, never a sleep, never a wall clock. All correctness comes from
completion signals (the stream's end-of-output sentinel and the child's exit
code), so the tests are fully deterministic.

The controller imports no UI framework. A Textual worker (issue #109) may
drive it, but the dependency runs one way.
"""

from __future__ import annotations

import os
import queue
import signal
import sys
import threading
from dataclasses import dataclass
from enum import Enum
from subprocess import PIPE, Popen
from typing import Callable, Mapping, Optional, Protocol, Sequence

from .catalog import canonical_targets
from .results import ConfigError, PolicyError, ToolError

__all__ = [
    "OutputChannel",
    "RunState",
    "CancelStage",
    "Invocation",
    "Outcome",
    "SpawnedProcess",
    "Spawn",
    "LineSink",
    "SingleChildError",
    "SpawnError",
    "ControllerStateError",
    "ProcessController",
    "default_spawn",
]


class OutputChannel(str, Enum):
    """Which of the child's streams a line came from. Channel identity is
    part of the record: it is retained across arbitrary chunk boundaries and
    never collapsed into one undifferentiated stream."""

    STDOUT = "stdout"
    STDERR = "stderr"


class RunState(str, Enum):
    """The controller's lifecycle. ``IDLE`` and ``DONE`` are the two rest
    states from which a fresh run may start; ``STARTING``/``RUNNING``/
    ``CANCELLING`` are the active states that refuse a second child."""

    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    CANCELLING = "cancelling"
    DONE = "done"


class CancelStage(Enum):
    """How far a cancellation got. ``NONE`` means no cancel was asked for.
    The others are the explicit, non-collapsible stages the desk renders:
    the operator's request was recorded, the signal was acknowledged by the
    OS, the child actually terminated, or the attempt failed. A cancel is
    never silently upgraded to success."""

    NONE = "none"
    REQUESTED = "requested"
    ACKNOWLEDGED = "acknowledged"
    TERMINATED = "terminated"
    FAILED = "failed"


class SingleChildError(PolicyError):
    """A second mutating child was requested while one is already active.
    Raised *before* any launch, so the invariant -- at most one child per
    book root -- holds by construction."""


class SpawnError(ToolError):
    """The child could not be launched at all (the interpreter or the press
    module was unreachable). No verdict exists because no child ran; the
    controller returns to ``IDLE`` so a corrected attempt may follow."""


class ControllerStateError(PolicyError):
    """A controller method was called in a state that cannot honor it
    (polling before a start, finishing a run that never began). A misuse of
    the API, distinct from any child outcome."""


@dataclass(frozen=True)
class Invocation:
    """One cataloged press command, built into an argv array -- never a shell
    string. ``target`` must be a canonical catalog target, so an arbitrary
    program can never be smuggled through; ``args`` are passed verbatim as
    array elements, so no quoting, globbing, or word-splitting occurs."""

    target: str
    args: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.target not in canonical_targets():
            raise ConfigError(f"not a cataloged press target: {self.target!r}")
        for arg in self.args:
            if not isinstance(arg, str):
                raise ConfigError("invocation args must be strings")
            if "\x00" in arg:
                raise ConfigError("invocation args must not contain NUL")

    @classmethod
    def of(cls, target: str, *args: str) -> "Invocation":
        return cls(target=target, args=tuple(args))

    def argv(self, python: str) -> list[str]:
        """The exact array handed to the launcher: the interpreter, ``-m
        press``, the target, then each argument as its own element."""

        return [python, "-m", "press", self.target, *self.args]

    @property
    def cli(self) -> str:
        """The human-facing ``press ...`` equivalent, for display only. It is
        never parsed back into an argv or handed to a shell."""

        return " ".join(["press", self.target, *self.args])


@dataclass(frozen=True)
class Outcome:
    """The terminal result of one run. ``returncode`` is the child's exact
    exit status (negative for a signal, per the OS convention), copied
    verbatim. ``cancelled`` records whether the operator asked to stop it,
    and ``cancel_stage`` how far that got. A run counts as success only when
    the child exited zero *and* was not cancelled."""

    returncode: int
    cancelled: bool
    cancel_stage: CancelStage

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0 and not self.cancelled

    @property
    def terminated_by_signal(self) -> bool:
        """True when the child died from a signal (return code below zero).
        The verdict is still the raw return code; this only names it."""

        return self.returncode < 0


class SpawnedProcess(Protocol):
    """A launched child, seen through the only four operations the controller
    needs. The real implementation wraps ``subprocess.Popen``; a test's fake
    scripts the same four. All process/OS access lives behind this seam, so
    the controller's own logic never touches a real subprocess."""

    def read_line(self) -> Optional[tuple[OutputChannel, str]]:
        """Block until the next output line is available and return it with
        its channel, or ``None`` once both streams have closed (the
        end-of-output completion signal). Never times out on a wall clock."""
        ...

    def interrupt(self) -> None:
        """Send SIGINT to the child's process group (the polite cancel)."""
        ...

    def terminate(self) -> None:
        """Send SIGTERM to the child's process group (the escalation)."""
        ...

    def wait(self) -> int:
        """Return the child's final exit status once it has ended."""
        ...


# A launcher: given the argv, the explicit working directory (the book root),
# and an optional environment, it returns a started ``SpawnedProcess``.
class Spawn(Protocol):
    def __call__(
        self,
        argv: Sequence[str],
        cwd: str,
        env: Optional[Mapping[str, str]] = None,
    ) -> SpawnedProcess: ...


# The sink an output line is streamed to as it arrives.
LineSink = Callable[[OutputChannel, str], None]


class ProcessController:
    """Runs at most one press child at a time in a fixed book root.

    Bind one controller to one book root; its state machine then guarantees a
    second run cannot launch while one is active. Drive it either with the
    convenience :meth:`run` (start, pump every line to the sink, finish) or
    with the explicit :meth:`start`/:meth:`poll`/:meth:`finish` steps when a
    caller needs to interleave a :meth:`cancel`.
    """

    def __init__(
        self,
        book_root: str | os.PathLike[str],
        *,
        python: str | None = None,
        spawn: Spawn | None = None,
    ) -> None:
        self._book_root = os.fspath(book_root)
        self._python = python if python is not None else sys.executable
        self._spawn: Spawn = spawn if spawn is not None else default_spawn
        self._state = RunState.IDLE
        self._process: SpawnedProcess | None = None
        self._invocation: Invocation | None = None
        self._cancel_stage = CancelStage.NONE

    @property
    def state(self) -> RunState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state in (RunState.STARTING, RunState.RUNNING, RunState.CANCELLING)

    @property
    def cancel_stage(self) -> CancelStage:
        return self._cancel_stage

    @property
    def invocation(self) -> Invocation | None:
        return self._invocation

    @property
    def book_root(self) -> str:
        return self._book_root

    def start(self, invocation: Invocation, *, env: Optional[Mapping[str, str]] = None) -> None:
        """Launch the child. Refuses -- without launching anything -- if a run
        is already active, so the single-child invariant holds by
        construction. A launch failure returns the controller to ``IDLE`` and
        raises :class:`SpawnError`."""

        if self.is_running:
            raise SingleChildError(
                f"a press child is already {self._state.value} in {self._book_root}; "
                "refuse to launch a second"
            )
        self._state = RunState.STARTING
        self._process = None
        self._invocation = invocation
        self._cancel_stage = CancelStage.NONE
        argv = invocation.argv(self._python)
        try:
            process = self._spawn(argv, self._book_root, env)
        except OSError as exc:
            self._state = RunState.IDLE
            raise SpawnError(
                f"could not launch {invocation.cli!r}: {exc}",
                source="process_control",
                detail=str(exc),
            ) from exc
        self._process = process
        self._state = RunState.RUNNING

    def poll(self, sink: LineSink) -> bool:
        """Deliver the next output line to ``sink`` and report whether the
        stream is still open. Returns ``False`` at the end-of-output signal,
        after which :meth:`finish` yields the verdict."""

        if self._process is None or self._state not in (RunState.RUNNING, RunState.CANCELLING):
            raise ControllerStateError("poll() called with no active child")
        item = self._process.read_line()
        if item is None:
            return False
        sink(item[0], item[1])
        return True

    def cancel(self) -> None:
        """Ask the running child to stop. The first call records the request
        and sends SIGINT (moving to ``ACKNOWLEDGED``); a second call escalates
        to SIGTERM. If the OS refuses the signal, the stage becomes
        ``FAILED`` -- never quietly dropped."""

        if self._process is None or self._state not in (RunState.RUNNING, RunState.CANCELLING):
            raise ControllerStateError("cancel() called with no active child")
        escalating = self._state == RunState.CANCELLING
        self._state = RunState.CANCELLING
        if not escalating:
            self._cancel_stage = CancelStage.REQUESTED
            try:
                self._process.interrupt()
            except OSError:
                self._cancel_stage = CancelStage.FAILED
                return
            self._cancel_stage = CancelStage.ACKNOWLEDGED
        else:
            try:
                self._process.terminate()
            except OSError:
                self._cancel_stage = CancelStage.FAILED

    def finish(self) -> Outcome:
        """Read the child's exact exit status and build the terminal
        :class:`Outcome`. Call once the stream has closed (:meth:`poll`
        returned ``False``). The return code is copied verbatim; a cancelled
        run is marked cancelled regardless of what code it exited with."""

        if self._process is None or self._state not in (RunState.RUNNING, RunState.CANCELLING):
            raise ControllerStateError("finish() called with no active child")
        returncode = self._process.wait()
        cancelled = self._state == RunState.CANCELLING
        stage = self._cancel_stage
        if cancelled and stage in (CancelStage.REQUESTED, CancelStage.ACKNOWLEDGED):
            stage = CancelStage.TERMINATED
        self._cancel_stage = stage
        self._state = RunState.DONE
        return Outcome(returncode=returncode, cancelled=cancelled, cancel_stage=stage)

    def run(self, invocation: Invocation, sink: LineSink, *,
            env: Optional[Mapping[str, str]] = None) -> Outcome:
        """Start, stream every line to ``sink``, and return the verdict. A
        caller wanting to cancel mid-run drives :meth:`start`/:meth:`poll`/
        :meth:`finish` directly (or calls :meth:`cancel` from a worker while
        this loop pumps)."""

        self.start(invocation, env=env)
        while self.poll(sink):
            pass
        return self.finish()


# --------------------------------------------------------------------------
# The one production launcher. A process controller is the rightful home of a
# real subprocess, so this is where -- and the only place -- one is touched.
# The controller above depends only on the ``Spawn``/``SpawnedProcess`` seam,
# so it stays subprocess-free and every test injects a fake in this function's
# place.
# --------------------------------------------------------------------------


class _PopenProcess:
    """Wraps a live ``Popen`` as a :class:`SpawnedProcess`.

    Two reader threads drain stdout and stderr independently and push each
    tagged line onto one queue, so channel identity survives arbitrary chunk
    boundaries and the two streams interleave in arrival order. When both
    readers reach EOF a single ``None`` sentinel is queued -- the completion
    signal :meth:`read_line` returns. Signals go to the child's own process
    group (it is launched in a new session) so an interrupt reaches the whole
    tree, not just the interpreter."""

    def __init__(self, popen: "Popen[str]") -> None:
        assert popen.stdout is not None and popen.stderr is not None
        self._popen = popen
        self._queue: queue.Queue[Optional[tuple[OutputChannel, str]]] = queue.Queue()
        self._lock = threading.Lock()
        self._open_streams = 2
        self._threads = [
            threading.Thread(
                target=self._drain, args=(popen.stdout, OutputChannel.STDOUT), daemon=True
            ),
            threading.Thread(
                target=self._drain, args=(popen.stderr, OutputChannel.STDERR), daemon=True
            ),
        ]
        for thread in self._threads:
            thread.start()

    def _drain(self, pipe: object, channel: OutputChannel) -> None:
        readline = getattr(pipe, "readline")
        try:
            for raw in iter(readline, ""):
                self._queue.put((channel, raw.rstrip("\n")))
        finally:
            with self._lock:
                self._open_streams -= 1
                if self._open_streams == 0:
                    self._queue.put(None)

    def read_line(self) -> Optional[tuple[OutputChannel, str]]:
        return self._queue.get()

    def _signal_group(self, sig: int) -> None:
        os.killpg(os.getpgid(self._popen.pid), sig)

    def interrupt(self) -> None:
        self._signal_group(signal.SIGINT)

    def terminate(self) -> None:
        self._signal_group(signal.SIGTERM)

    def wait(self) -> int:
        return self._popen.wait()


def default_spawn(
    argv: Sequence[str],
    cwd: str,
    env: Optional[Mapping[str, str]] = None,
) -> SpawnedProcess:
    """Launch ``argv`` as a real child in ``cwd`` with its own session.

    ``env`` of ``None`` inherits the parent environment; a supplied mapping
    replaces it wholesale. The child gets a new session (its own process
    group) so cancellation can signal the whole tree. A launch failure raises
    ``OSError``, which :meth:`ProcessController.start` translates into a
    :class:`SpawnError`."""

    popen = Popen(
        list(argv),
        cwd=cwd,
        env=dict(env) if env is not None else None,
        stdout=PIPE,
        stderr=PIPE,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    return _PopenProcess(popen)
