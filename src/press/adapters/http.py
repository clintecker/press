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


def urlopen_transport(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = 30.0,
    max_bytes: int | None = None,
) -> Response:
    """Perform one request. ``max_bytes``, when given, bounds the body *as it
    is read* rather than after the fact.

    A caller that must not take an unbounded body into memory cannot get that
    guarantee from a size check on the returned response: by then the whole
    body has already been read, and a server that omits or lies about
    Content-Length decides how much memory was spent. It is opt-in and
    unbounded by default because the other callers -- a cover image, a
    provider's job payload -- legitimately read whatever the server sends, and
    a blanket cap here would silently truncate them.

    One byte beyond the bound is read on purpose, so the caller can tell a
    body that exactly fills the bound from one that overruns it. Nothing is
    truncated silently: the caller sees the overrun and fails closed.
    """

    request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    limit = None if max_bytes is None else max_bytes + 1
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (adapter boundary)
            payload = response.read() if limit is None else response.read(limit)
            return Response(response.status, payload, dict(response.headers))
    except urllib.error.HTTPError as exc:
        # An HTTP error status is a real response, not a transport failure --
        # and an error body is as unbounded as a successful one.
        payload = exc.read() if limit is None else exc.read(limit)
        return Response(exc.code, payload, dict(exc.headers))
    except socket.timeout as exc:
        raise TransportTimeout(str(exc)) from exc
    except urllib.error.URLError as exc:
        # The request did not reach the server (connection refused, DNS).
        raise TransportError(str(exc)) from exc
