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


# Environment variables that bind a git subprocess to a specific
# repository, index, or worktree. When press runs `git -C <root> ...` it
# means "operate on <root>", but an ambient one of these -- inherited from,
# say, a running commit hook -- would silently redirect git to the outer
# repo's transient index instead. They are stripped from the inherited
# environment for every git command, so a nested or independent repository
# observes only itself. A caller that is deliberately testing git behavior
# injects an explicit env, which is respected verbatim.
_GIT_REPO_BINDING = (
    "GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE", "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR", "GIT_INDEX_VERSION",
    "GIT_NAMESPACE", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
)


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
        run_env = dict(env) if env is not None else None
        is_git = bool(argv) and os.path.basename(str(argv[0])) == "git"
        if env is None and is_git \
                and any(v in os.environ for v in _GIT_REPO_BINDING):
            run_env = os.environ.copy()
            for var in _GIT_REPO_BINDING:
                run_env.pop(var, None)
        completed = subprocess.run(
            list(argv),
            cwd=cwd,
            env=run_env,
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
