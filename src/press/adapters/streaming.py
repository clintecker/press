"""The production streaming spawner: a real ``subprocess.Popen`` child whose
two output streams are drained live, tagged by channel, and delivered in
arrival order.

This is the streaming sibling of ``SubprocessRunner`` (which runs a command
to completion): a long-running press child the desk pumps line by line while
its UI stays responsive. As a boundary touch it lives here, in the one
approved home, behind the ``SpawnedProcess``/``Spawn`` protocols -- so
``press.process_control.ProcessController`` depends only on those seams and
stays subprocess-free, and every test injects a scripted fake in
``default_spawn``'s place.
"""

from __future__ import annotations

import os
import queue
import signal
import subprocess
import threading
from typing import Mapping, Optional, Sequence

from .protocols import OutputChannel, SpawnedProcess


class _PopenProcess:
    """Wraps a live ``Popen`` as a :class:`SpawnedProcess`.

    Two reader threads drain stdout and stderr independently and push each
    tagged line onto one queue, so channel identity survives arbitrary chunk
    boundaries and the two streams interleave in arrival order. When both
    readers reach EOF a single ``None`` sentinel is queued -- the completion
    signal :meth:`read_line` returns. Signals go to the child's own process
    group (it is launched in a new session) so an interrupt reaches the whole
    tree, not just the interpreter."""

    def __init__(self, popen: "subprocess.Popen[str]") -> None:
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
    ``OSError``, which ``ProcessController.start`` translates into a
    ``SpawnError``."""

    popen = subprocess.Popen(
        list(argv),
        cwd=cwd,
        env=dict(env) if env is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    return _PopenProcess(popen)
