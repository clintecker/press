"""The HTTP transport seam.

An adapter never opens a socket itself -- that keeps the network at the
boundary and lets a test drive a canned exchange. A transport is a
callable that takes a method, URL, headers, and body and returns a
:class:`Response`, raising :class:`TransportTimeout` when a request may
have been received but its response was lost (the ambiguous case a caller
must treat as an unknown outcome, never a failure).

The real urllib-backed transport lives in :mod:`press.adapters`, the one
approved home for outward calls. The fakes here are for tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> dict:
        return json.loads(self.body.decode("utf-8")) if self.body else {}


class TransportTimeout(Exception):
    """The request may have been delivered but the response was lost."""


class TransportError(Exception):
    """A request that demonstrably did not complete (connection refused)."""


# method, url -> keyword headers/body -> Response
Transport = Callable[..., Response]


@dataclass
class CannedTransport:
    """A test transport that answers each (method, url) from a script and
    records the exact requests made, so a conformance test can assert the
    outgoing calls."""

    routes: dict[tuple[str, str], Response]
    calls: list[dict] = field(default_factory=list)
    fail_next: Exception | None = None

    def __call__(self, method: str, url: str, *, headers: dict[str, str] | None = None,
                 body: bytes | None = None) -> Response:
        self.calls.append({"method": method, "url": url,
                           "headers": headers or {}, "body": body})
        if self.fail_next is not None:
            error, self.fail_next = self.fail_next, None
            raise error
        # Match on (method, path-without-query) so query strings do not matter.
        path = url.split("?", 1)[0]
        for (m, u), response in self.routes.items():
            if m == method and path.endswith(u):
                return response
        return Response(404, b'{"detail": "Not found."}')
