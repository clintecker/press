"""The production adapters: the only place in ``press`` that is allowed to
call ``subprocess``, read ``os.environ``, resolve PATH, or open a socket.

Each is a thin, honest wrapper. ``SubprocessRunner`` defers to
``subprocess.run`` and lets its exceptions propagate untouched, because the
CLI boundary's exit-code translation depends on catching
``CalledProcessError``. ``OsEnvironment`` reads the live environment and
PATH. ``UrllibImageClient`` performs the real HTTP POST with ``urllib`` and
raises ``HttpError`` (a ``ToolError``) when the API answers with an error
status, carrying the host, code, and truncated detail the console relays.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from typing import Any, Mapping, Sequence

from ..results import ToolError
from .protocols import ProcessResult


class HttpError(ToolError):
    """An image API answered with an HTTP error status. Carries the host,
    status code, and truncated response body so the caller can reproduce
    the exact console message the press has always printed."""

    def __init__(self, host: str, code: int, detail: str) -> None:
        super().__init__(
            f"{host} refused ({code})", source=host, code=code, detail=detail
        )
        self.host = host


class SubprocessRunner:
    """Runs commands through ``subprocess.run``. The production
    ``ProcessRunner``."""

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
        completed = subprocess.run(
            list(argv),
            cwd=cwd,
            env=dict(env) if env is not None else None,
            capture_output=capture,
            check=check,
            timeout=timeout,
        )
        return ProcessResult(
            returncode=completed.returncode,
            stdout=completed.stdout if capture else b"",
            stderr=completed.stderr if capture else b"",
        )


class OsEnvironment:
    """Reads the live process environment and PATH. The production
    ``Environment``."""

    def get(self, key: str, default: str | None = None) -> str | None:
        return os.environ.get(key, default)

    def copy(self) -> dict[str, str]:
        return os.environ.copy()

    def which(self, tool: str) -> str | None:
        return shutil.which(tool)


class UrllibImageClient:
    """POSTs to image-generation APIs with ``urllib``. The production
    ``HttpImageClient``."""

    def post_json(
        self, url: str, payload: Mapping[str, Any], headers: Mapping[str, str]
    ) -> dict:
        request = urllib.request.Request(
            url,
            data=json.dumps(dict(payload)).encode("utf-8"),
            headers={"Content-Type": "application/json", **dict(headers)},
        )
        return self._send(url, request)

    def post_multipart(
        self, url: str, body: bytes, headers: Mapping[str, str]
    ) -> dict:
        request = urllib.request.Request(url, data=body, headers=dict(headers))
        return self._send(url, request)

    def _send(self, url: str, request: "urllib.request.Request") -> dict:
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise HttpError(url.split("/")[2], exc.code, detail) from exc


# Module-level production singletons. Call sites bind these by default and
# tests swap them for the deterministic fakes in ``adapters.fakes``.
process_runner = SubprocessRunner()
environment = OsEnvironment()
image_client = UrllibImageClient()
