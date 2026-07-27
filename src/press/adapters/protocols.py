"""Typed boundaries the press talks to the outside world through.

Every subprocess, every environment read, every HTTP call, and every
retry decision the orchestration makes crosses one of these Protocols.
Production code depends on the Protocol, not on ``subprocess`` or
``os.environ`` or ``urllib`` directly, so a test can inject a deterministic
fake that records exactly what was asked and answers exactly what the
scenario needs -- no live network, no ambient credentials, no clock.

A ``ProcessResult`` is the one typed shape a process run returns; the raw
``subprocess`` exceptions (``CalledProcessError``, ``TimeoutExpired``,
``OSError``) still propagate unchanged, because the CLI boundary's exit-code
translation depends on seeing them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional, Protocol, Sequence


@dataclass(frozen=True)
class ProcessResult:
    """What a process run yields. ``stdout``/``stderr`` are populated only
    when the run captured them; an inheriting run leaves them empty."""

    returncode: int
    stdout: bytes = b""
    stderr: bytes = b""


class ProcessRunner(Protocol):
    """Runs an external command. Mirrors the subset of ``subprocess.run``
    the press actually uses, and preserves its exception contract: with
    ``check=True`` a nonzero exit raises ``subprocess.CalledProcessError``,
    a ``timeout`` breach raises ``subprocess.TimeoutExpired``, and a missing
    binary raises ``OSError`` -- exactly what the CLI boundary catches."""

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Any | None = None,
        env: Mapping[str, str] | None = None,
        capture: bool = False,
        check: bool = False,
        timeout: float | None = None,
    ) -> ProcessResult: ...


class Environment(Protocol):
    """Reads and writes the ambient process environment and PATH. Reads are
    the common case (credentials and tool locations enter here); the writes
    exist for the few sites that must redirect a child process or a memoized
    lookup -- ``borrow_book`` pointing ``BOOK_ROOT`` at a fixture, for one --
    through the same seam they read, so a fake observes both and no test
    depends on the machine it runs on."""

    def get(self, key: str, default: str | None = None) -> str | None: ...

    def copy(self) -> dict[str, str]: ...

    def which(self, tool: str) -> str | None: ...

    def set(self, key: str, value: str) -> None: ...

    def unset(self, key: str) -> None: ...


class HttpImageClient(Protocol):
    """Posts to an image-generation HTTP API and returns the decoded JSON.
    A protocol error (the API answered with an HTTP error status) raises
    ``adapters.HttpError``; the caller translates it for the console."""

    def post_json(
        self, url: str, payload: Mapping[str, Any], headers: Mapping[str, str]
    ) -> dict: ...

    def post_multipart(self, url: str, body: bytes, headers: Mapping[str, str]) -> dict: ...


class OutputChannel(str, Enum):
    """Which of a spawned child's streams a line came from. Channel identity
    is part of the record: it is retained across arbitrary chunk boundaries
    and never collapsed into one undifferentiated stream."""

    STDOUT = "stdout"
    STDERR = "stderr"


class SpawnedProcess(Protocol):
    """A launched child, seen through the only four operations a streaming
    controller needs. The production implementation wraps ``subprocess.Popen``
    (see ``adapters.streaming``); a test scripts the same four. All
    process/OS access lives behind this seam, so the controller's own logic
    never touches a real subprocess."""

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


class Spawn(Protocol):
    """A launcher: given the argv, the explicit working directory (the book
    root), and an optional environment, it returns a started
    ``SpawnedProcess``. Production supplies ``adapters.streaming.default_spawn``
    (the one real ``subprocess`` touch); every test injects a fake."""

    def __call__(
        self,
        argv: Sequence[str],
        cwd: str,
        env: Optional[Mapping[str, str]] = None,
    ) -> SpawnedProcess: ...


class RetrySource(Protocol):
    """Supplies the next observation in a poll/retry loop and the remaining
    attempt budget. Production polls the real world; a fake replays a finite,
    injected sequence of states, so a retry test asserts on transitions and
    budgets without a single ``sleep``."""

    def poll(self) -> Any: ...

    def remaining(self) -> int: ...
