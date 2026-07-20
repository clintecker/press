"""Deterministic fakes and spies for the boundary Protocols.

Every fake records what it was asked -- argv, cwd, the exact env slice it
was handed, each request URL and payload, each mutation -- and answers from
a script the test supplies. No fake touches the process environment, the
network, the filesystem, or the clock. A test asserts against an active
signal (this argv, in this cwd, with this env) instead of scraping printed
output.

The fakes satisfy the same Protocols as the production adapters, so a
contract test can drive both through one behavioral interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ..results import PolicyError
from .protocols import ProcessResult


@dataclass(frozen=True)
class RecordedRun:
    """One process invocation, exactly as it was requested."""

    argv: tuple[str, ...]
    cwd: str | None
    env: dict[str, str] | None
    capture: bool
    check: bool
    timeout: float | None


class FakeProcessRunner:
    """A ``ProcessRunner`` that records every invocation and answers from a
    programmed script.

    Program it with ``ProcessResult`` values (returned in order, the last
    reused once exhausted) or with an exception instance (raised), keyed by
    the command name (``argv[0]``) or matched positionally. The default is a
    clean ``ProcessResult(0)`` so a happy path needs no setup."""

    def __init__(
        self,
        results: Sequence[ProcessResult | BaseException] | None = None,
        by_command: Mapping[str, ProcessResult | BaseException] | None = None,
        default: ProcessResult | None = None,
    ) -> None:
        self.runs: list[RecordedRun] = []
        self._queue: list[ProcessResult | BaseException] = list(results or [])
        self._by_command = dict(by_command or {})
        self._default = default if default is not None else ProcessResult(0)

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Any | None = None,
        env: Mapping[str, str] | None = None,
        capture: bool = False,
        check: bool = False,
        timeout: float | None = None,
    ) -> ProcessResult:
        argv = tuple(argv)
        self.runs.append(
            RecordedRun(
                argv=argv,
                cwd=str(cwd) if cwd is not None else None,
                env=dict(env) if env is not None else None,
                capture=capture,
                check=check,
                timeout=timeout,
            )
        )
        outcome: ProcessResult | BaseException
        if argv and argv[0] in self._by_command:
            outcome = self._by_command[argv[0]]
        elif self._queue:
            outcome = self._queue.pop(0)
        else:
            outcome = self._default
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    @property
    def argvs(self) -> list[tuple[str, ...]]:
        return [run.argv for run in self.runs]


class FakeEnvironment:
    """An ``Environment`` backed by a fixed dict and a fixed PATH set.

    ``get``/``copy`` read the injected map; ``which`` answers from the set of
    tool names declared present, so a test states exactly which binaries and
    credentials exist with no reference to the host."""

    def __init__(
        self,
        values: Mapping[str, str] | None = None,
        present_tools: Sequence[str] | None = None,
    ) -> None:
        self._values = dict(values or {})
        self._present = set(present_tools or [])
        self.reads: list[str] = []
        self.which_calls: list[str] = []

    def get(self, key: str, default: str | None = None) -> str | None:
        self.reads.append(key)
        return self._values.get(key, default)

    def copy(self) -> dict[str, str]:
        return dict(self._values)

    def which(self, tool: str) -> str | None:
        self.which_calls.append(tool)
        return f"/usr/bin/{tool}" if tool in self._present else None


@dataclass(frozen=True)
class RecordedRequest:
    """One HTTP request, recorded before it would have gone to the wire."""

    kind: str  # "json" or "multipart"
    url: str
    payload: Any
    headers: dict[str, str]


class FakeImageClient:
    """An ``HttpImageClient`` that records each request and answers from a
    programmed list of JSON responses (or raises a programmed exception).
    Never opens a socket."""

    def __init__(
        self, responses: Sequence[dict | BaseException] | None = None
    ) -> None:
        self.requests: list[RecordedRequest] = []
        self._responses: list[dict | BaseException] = list(responses or [])

    def _answer(self) -> dict:
        if not self._responses:
            raise PolicyError("FakeImageClient has no more programmed responses")
        outcome = self._responses.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def post_json(
        self, url: str, payload: Mapping[str, Any], headers: Mapping[str, str]
    ) -> dict:
        self.requests.append(
            RecordedRequest("json", url, dict(payload), dict(headers))
        )
        return self._answer()

    def post_multipart(
        self, url: str, body: bytes, headers: Mapping[str, str]
    ) -> dict:
        self.requests.append(
            RecordedRequest("multipart", url, body, dict(headers))
        )
        return self._answer()


@dataclass
class ScriptedRetrySource:
    """A ``RetrySource`` that replays a finite, injected sequence of states.

    ``poll`` returns the next state and advances; a poll past the end is a
    ``PolicyError`` (the scenario under-provisioned the sequence), never a
    block. ``remaining`` reports how many states are left, so a test can
    assert the loop stopped early on a terminal state."""

    states: list[Any] = field(default_factory=list)
    _index: int = 0

    def poll(self) -> Any:
        if self._index >= len(self.states):
            raise PolicyError("ScriptedRetrySource exhausted its state sequence")
        state = self.states[self._index]
        self._index += 1
        return state

    def remaining(self) -> int:
        return len(self.states) - self._index
