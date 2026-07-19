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
from typing import Any, Mapping, Protocol, Sequence


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
    """Reads the ambient process environment and PATH. The one seam through
    which credentials and tool locations enter; a fake supplies a fixed map
    so no test depends on the machine it runs on."""

    def get(self, key: str, default: str | None = None) -> str | None: ...

    def copy(self) -> dict[str, str]: ...

    def which(self, tool: str) -> str | None: ...


class HttpImageClient(Protocol):
    """Posts to an image-generation HTTP API and returns the decoded JSON.
    A protocol error (the API answered with an HTTP error status) raises
    ``adapters.HttpError``; the caller translates it for the console."""

    def post_json(
        self, url: str, payload: Mapping[str, Any], headers: Mapping[str, str]
    ) -> dict: ...

    def post_multipart(
        self, url: str, body: bytes, headers: Mapping[str, str]
    ) -> dict: ...


class RetrySource(Protocol):
    """Supplies the next observation in a poll/retry loop and the remaining
    attempt budget. Production polls the real world; a fake replays a finite,
    injected sequence of states, so a retry test asserts on transitions and
    budgets without a single ``sleep``."""

    def poll(self) -> Any: ...

    def remaining(self) -> int: ...
