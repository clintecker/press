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
from press.providers.transport import TransportError, TransportTimeout


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
        "POST", "https://provider.test/jobs", headers={"X-Test": "yes"},
        body=b"payload", timeout=7.5)

    assert response.status == 201
    assert response.body == b'{"ok": true}'
    assert response.headers["X-Request-Id"] == "req-1"
    assert observed["request"].get_method() == "POST"
    assert observed["request"].data == b"payload"
    assert observed["request"].get_header("X-test") == "yes"
    assert observed["timeout"] == 7.5


def test_http_error_is_a_real_response_not_a_transport_failure(monkeypatch):
    error = urllib.error.HTTPError(
        "https://provider.test/jobs", 422, "invalid", {"X-Error": "typed"},
        io.BytesIO(b'{"detail": "invalid"}'))

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(http.urllib.request, "urlopen", fail)
    response = http.urlopen_transport("GET", "https://provider.test/jobs")
    assert response.status == 422
    assert response.body == b'{"detail": "invalid"}'
    assert response.headers["X-Error"] == "typed"


@pytest.mark.parametrize(("error", "translated"), [
    (socket.timeout("response lost"), TransportTimeout),
    (urllib.error.URLError("dns failed"), TransportError),
])
def test_network_failures_are_translated_to_typed_transport_signals(
        error, translated, monkeypatch):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(http.urllib.request, "urlopen", fail)
    with pytest.raises(translated, match=str(error)):
        http.urlopen_transport("GET", "https://provider.test/jobs")
