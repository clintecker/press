"""The production urllib transport translated through injected responses.

No test opens a socket. These proofs exercise the real boundary adapter with
smart stand-ins for each active signal: response, HTTP response, timeout, and
connection failure.
"""

from __future__ import annotations

import io
import socket
import urllib.error

import pytest

from press.adapters import http
from press.providers.transport import Response, TransportError, TransportTimeout


# --- Response.json and the typed transport signals (transport.py) -------------


def test_response_json_guards_empty_body_parses_and_types_are_distinct():
    # An empty body is the "no content" answer (204, or a bodiless 200); it
    # decodes to {} rather than blowing up json.loads on the empty string.
    assert Response(200, b"").json() == {}
    # A real body parses to its mapping.
    assert Response(200, b'{"job": "queued", "n": 2}').json() == {"job": "queued", "n": 2}

    # Timeout ("may have landed") and error ("did not") are separate types,
    # neither a subclass of the other, so a caller can treat the ambiguous
    # case differently from a demonstrable failure. Collapse them and this
    # asymmetry vanishes.
    assert issubclass(TransportTimeout, Exception)
    assert issubclass(TransportError, Exception)
    assert not issubclass(TransportTimeout, TransportError)
    assert not issubclass(TransportError, TransportTimeout)


class _Reply:
    status = 201
    headers = {"X-Request-Id": "req-1"}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return b'{"ok": true}'


def test_http_transport_returns_status_body_headers_and_request(monkeypatch):
    observed = {}

    def open_request(request, *, timeout):
        observed["request"] = request
        observed["timeout"] = timeout
        return _Reply()

    monkeypatch.setattr(http.urllib.request, "urlopen", open_request)
    response = http.urlopen_transport(
        "POST",
        "https://provider.test/jobs",
        headers={"X-Test": "yes"},
        body=b"payload",
        timeout=7.5,
    )

    assert response.status == 201
    assert response.body == b'{"ok": true}'
    assert response.headers["X-Request-Id"] == "req-1"
    assert observed["request"].get_method() == "POST"
    assert observed["request"].data == b"payload"
    assert observed["request"].get_header("X-test") == "yes"
    assert observed["timeout"] == 7.5


def test_http_error_is_a_real_response_not_a_transport_failure(monkeypatch):
    error = urllib.error.HTTPError(
        "https://provider.test/jobs",
        422,
        "invalid",
        {"X-Error": "typed"},
        io.BytesIO(b'{"detail": "invalid"}'),
    )

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(http.urllib.request, "urlopen", fail)
    response = http.urlopen_transport("GET", "https://provider.test/jobs")
    assert response.status == 422
    assert response.body == b'{"detail": "invalid"}'
    assert response.headers["X-Error"] == "typed"


@pytest.mark.parametrize(
    ("error", "translated"),
    [
        (socket.timeout("response lost"), TransportTimeout),
        (urllib.error.URLError("dns failed"), TransportError),
    ],
)
def test_network_failures_are_translated_to_typed_transport_signals(error, translated, monkeypatch):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(http.urllib.request, "urlopen", fail)
    with pytest.raises(translated, match=str(error)):
        http.urlopen_transport("GET", "https://provider.test/jobs")


# --- the body bound is applied AT THE READ (#209) -----------------------------


class _BoundedReply:
    """A reply that records the limit the transport asks for, and would hand
    back far more than the bound if asked for everything -- so a transport
    that reads unbounded is caught by the size of what it gets, not merely by
    the absence of an argument."""

    status = 200
    headers = {"Content-Type": "application/xml"}

    def __init__(self) -> None:
        self.asked: list[int | None] = []

    def read(self, amount=None):
        self.asked.append(amount)
        return b"x" * (amount if amount is not None else 10_000_000)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _serve(monkeypatch, reply):
    monkeypatch.setattr(http.urllib.request, "urlopen", lambda request, *, timeout: reply)


def test_max_bytes_bounds_the_read_itself(monkeypatch):
    reply = _BoundedReply()
    _serve(monkeypatch, reply)
    response = http.urlopen_transport("GET", "https://provider.test/record", max_bytes=1024)
    # One past the bound, so an overrun is detectable; never the whole body.
    assert reply.asked == [1025]
    assert len(response.body) == 1025


def test_without_max_bytes_the_read_stays_unbounded(monkeypatch):
    """The other callers -- a cover image, a provider payload -- legitimately
    read whatever the server sends; the bound must be opt-in or this would
    silently truncate them."""

    reply = _BoundedReply()
    _serve(monkeypatch, reply)
    http.urlopen_transport("GET", "https://provider.test/image")
    assert reply.asked == [None]


def test_an_error_body_is_bounded_too(monkeypatch):
    """An HTTP error status is a real response, and its body is as unbounded
    as a successful one -- a 500 that streams forever must not be a way past
    the bound."""

    class _Error(urllib.error.HTTPError):
        def __init__(self):
            self.asked: list[int | None] = []
            super().__init__(
                "https://provider.test/x", 500, "boom", {"Content-Type": "text/plain"}, None
            )

        def read(self, amount=None):
            self.asked.append(amount)
            return b"e" * (amount if amount is not None else 10_000_000)

    error = _Error()

    def raise_error(request, *, timeout):
        raise error

    monkeypatch.setattr(http.urllib.request, "urlopen", raise_error)
    response = http.urlopen_transport("GET", "https://provider.test/x", max_bytes=512)
    assert error.asked == [513]
    assert response.status == 500
    assert len(response.body) == 513
