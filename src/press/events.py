"""A versioned structured event protocol for child press commands.

Human stdout is not an API. When the operator desk runs a press command
as a child, it needs structured signals (a stage started, a diagnostic
was raised, an artifact was produced, the run completed) without
scraping printed text, while still keeping the child's raw output
verbatim. A child opts into the channel by emitting event lines, each a
single JSON object on its own line behind a fixed sentinel prefix, so a
consumer separates events from ordinary output by the prefix alone.

The protocol is versioned and strict: an event line whose JSON is
malformed, whose version is unknown, or whose type is unrecognized is a
visible protocol failure, surfaced to the consumer. It can never turn a
failed child green (the return code remains the verdict) nor make raw
output disappear (a non-event line is always raw output).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = 1
SENTINEL = "\x1e\x1epress-event\x1e"  # record-separator framed, never in prose

EVENT_TYPES = frozenset({"stage_start", "stage_end", "diagnostic", "artifact", "complete"})


@dataclass(frozen=True)
class Event:
    version: int
    type: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class ProtocolError:
    """A line that claimed to be an event but was not a valid one. It is
    surfaced, never silently dropped."""

    reason: str
    raw: str


def emit_line(event_type: str, **payload: Any) -> str:
    """One event as a sentinel-framed JSON line a child prints."""

    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event type: {event_type!r}")
    body = json.dumps(
        {"version": PROTOCOL_VERSION, "type": event_type, "payload": payload},
        sort_keys=True, separators=(",", ":"),
    )
    return SENTINEL + body


def is_event_line(line: str) -> bool:
    return line.startswith(SENTINEL)


def parse_line(line: str) -> Event | ProtocolError | None:
    """None for ordinary output (never an event), an Event for a valid
    one, a ProtocolError for a line that framed itself as an event but
    is malformed, unknown-version, or unknown-type."""

    if not is_event_line(line):
        return None
    body = line[len(SENTINEL):]
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        return ProtocolError(f"malformed event JSON: {exc}", line)
    if not isinstance(data, dict):
        return ProtocolError("event is not a JSON object", line)
    if data.get("version") != PROTOCOL_VERSION:
        return ProtocolError(f"unknown protocol version: {data.get('version')!r}", line)
    event_type = data.get("type")
    if event_type not in EVENT_TYPES:
        return ProtocolError(f"unknown event type: {event_type!r}", line)
    payload = data.get("payload")
    if not isinstance(payload, dict):
        return ProtocolError("event payload is not a JSON object", line)
    return Event(version=PROTOCOL_VERSION, type=event_type, payload=payload)


@dataclass
class Demux:
    """Split a child's output stream into raw lines, events, and protocol
    failures, preserving every raw line so nothing disappears."""

    raw: list[str]
    events: list[Event]
    failures: list[ProtocolError]

    @classmethod
    def empty(cls) -> Demux:
        return cls(raw=[], events=[], failures=[])

    def feed(self, line: str) -> None:
        parsed = parse_line(line)
        if parsed is None:
            self.raw.append(line)
        elif isinstance(parsed, Event):
            self.events.append(parsed)
        else:
            self.failures.append(parsed)
