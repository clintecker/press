"""The real HTTP transport, on the boundary where outward calls belong.

A provider adapter is written against an injected transport so it can be
tested with a canned exchange; this is the production transport it is
given for a live call. It lives in the adapters package -- the one
approved home for HTTP -- and maps a lost response to
:class:`TransportTimeout`, so the caller treats an ambiguous submission
as unknown rather than failed. It is exercised only against a real
provider (the sandbox end-to-end proof), never in the fast suite.
"""

from __future__ import annotations

import socket
import urllib.error
import urllib.request

from ..providers.transport import Response, TransportError, TransportTimeout


def urlopen_transport(method: str, url: str, *, headers: dict[str, str] | None = None,
                      body: bytes | None = None, timeout: float = 30.0) -> Response:
    request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (adapter boundary)
            return Response(response.status, response.read(), dict(response.headers))
    except urllib.error.HTTPError as exc:
        # An HTTP error status is a real response, not a transport failure.
        return Response(exc.code, exc.read(), dict(exc.headers))
    except socket.timeout as exc:
        raise TransportTimeout(str(exc)) from exc
    except urllib.error.URLError as exc:
        # The request did not reach the server (connection refused, DNS).
        raise TransportError(str(exc)) from exc
