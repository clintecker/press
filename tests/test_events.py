"""The structured event protocol: valid events round-trip, and every
malformed variant is a surfaced protocol failure, never silent.
"""

from __future__ import annotations

from press import events


def test_valid_event_round_trips():
    line = events.emit_line("stage_start", name="pdf")
    parsed = events.parse_line(line)
    assert isinstance(parsed, events.Event)
    assert parsed.type == "stage_start"
    assert parsed.payload == {"name": "pdf"}


def test_ordinary_output_is_not_an_event():
    assert events.parse_line("+ pandoc --defaults=...") is None
    assert events.parse_line("Verified make-ready.pdf") is None


def test_malformed_json_is_a_protocol_failure():
    bad = events.SENTINEL + "{not json"
    result = events.parse_line(bad)
    assert isinstance(result, events.ProtocolError)
    assert "malformed" in result.reason


def test_unknown_version_is_a_protocol_failure():
    import json
    bad = events.SENTINEL + json.dumps({"version": 999, "type": "complete", "payload": {}})
    result = events.parse_line(bad)
    assert isinstance(result, events.ProtocolError)
    assert "version" in result.reason


def test_unknown_type_is_a_protocol_failure():
    import json
    bad = events.SENTINEL + json.dumps(
        {"version": events.PROTOCOL_VERSION, "type": "explode", "payload": {}})
    result = events.parse_line(bad)
    assert isinstance(result, events.ProtocolError)
    assert "type" in result.reason


def test_emit_rejects_unknown_type():
    import pytest
    with pytest.raises(ValueError, match="unknown event type"):
        events.emit_line("explode")


def test_demux_preserves_every_raw_line():
    demux = events.Demux.empty()
    demux.feed("real output one")
    demux.feed(events.emit_line("stage_end", name="pdf", ok=True))
    demux.feed("real output two")
    demux.feed(events.SENTINEL + "{broken")
    assert demux.raw == ["real output one", "real output two"]
    assert len(demux.events) == 1
    assert len(demux.failures) == 1


def test_a_protocol_failure_does_not_hide_output():
    """A broken event line is recorded as a failure and does not consume
    or replace the real output around it."""

    demux = events.Demux.empty()
    demux.feed("before")
    demux.feed(events.SENTINEL + "garbage")
    demux.feed("after")
    assert demux.raw == ["before", "after"]
    assert demux.failures
