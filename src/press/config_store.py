"""The mechanics behind `press config`: read, edit, and write a book's
YAML without losing a byte the user did not touch.

Three invariants live here, independent of which field is being edited:

- **Round-trip.** Editing is done on a ruamel round-trip document, so
  comments, key order, and any key press does not know about survive the
  write unchanged. Only the addressed key moves.
- **Atomic.** A write goes to a temporary file in the same directory and
  is renamed over the target, so a crash or a rejected edit can never
  leave a half-written config; the original bytes stand until the rename.
- **Unambiguous typing.** A shell string is never guessed at. The caller
  passes the field's declared type; a scalar is coerced by that type and
  a list or mapping must arrive as explicit JSON. `"true"` is the string
  "true" for a text field and the boolean True only for a boolean field.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


class ConfigError(Exception):
    """A user-facing, already-explained failure. The CLI prints its
    message and returns a non-zero code; it is not a traceback."""


def _yaml() -> YAML:
    yaml = YAML(pure=True)  # round-trip mode: comments and order preserved
    yaml.preserve_quotes = True
    yaml.width = 4096  # do not rewrap long scalars we did not touch
    # Match the scaffold template's house style ("  - item") so writing one
    # key does not reindent sequences the edit never touched.
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def load(path: Path) -> Any:
    """Parse a YAML file into a round-trip document. A missing file is an
    empty mapping so a first `set` can create it; a malformed file is a
    ConfigError naming the file, never a raw parse traceback."""

    from ruamel.yaml.comments import CommentedMap

    if not path.is_file():
        return CommentedMap()
    text = path.read_text(encoding="utf-8")
    try:
        data = _yaml().load(text)
    except Exception as exc:  # ruamel raises several parse error types
        raise ConfigError(f"{path}: not valid YAML ({exc})") from exc
    if data is None:
        # A comment-only or empty file: ruamel attaches its comments to no
        # node and drops them on a null document. Preserve the guidance as
        # the new map's start comment so a first `set` does not wipe it.
        data = CommentedMap()
        if text.strip():
            data.yaml_set_start_comment(text.rstrip("\n"))
    return data


def dumps(data: Any) -> str:
    """Serialize a round-trip document back to text."""

    buffer = io.StringIO()
    _yaml().dump(data, buffer)
    text = buffer.getvalue()
    if isinstance(data, dict) and not data:
        # An empty mapping that still carries a start comment dumps a stray
        # "{}"; drop it so a comment-only file round-trips to itself.
        stripped = text.rstrip()
        if stripped.endswith("{}"):
            text = stripped[:-2].rstrip("\n")
            text = (text + "\n") if text else ""
    return text


def _ambiguous(text: str) -> bool:
    """True when the package's YAML 1.2 loader would read this bare string
    as something other than the same string: '3' becomes an int, 'true' a
    bool, '2026-01-01' a date, '~' null. A string-typed field holding such
    a value must be quoted on write so it stays the string the user set."""

    from . import yamlio

    try:
        parsed = yamlio.loads(text)
    except Exception:
        return True  # unparseable bare; quoting makes it an unambiguous string
    return not (isinstance(parsed, str) and parsed == text)


def write_safe(value: Any) -> Any:
    """Prepare a coerced value for writing so a string-typed field stays a
    string: any string leaf the loader would otherwise read as a bool,
    number, date, or null is emitted double-quoted. Booleans and numbers
    pass through unchanged."""

    from ruamel.yaml.scalarstring import DoubleQuotedScalarString

    if isinstance(value, str) and not isinstance(value, DoubleQuotedScalarString):
        return DoubleQuotedScalarString(value) if (value == "" or _ambiguous(value)) else value
    if isinstance(value, list):
        return [write_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: write_safe(v) for k, v in value.items()}
    return value


def as_build_reads(data: Any) -> dict:
    """The document exactly as the build will parse the written bytes:
    serialize the round-trip doc and re-read it with the package's plain
    loader, so validation sees the parsed types (a quoted "24" as a string,
    a bare 24 as an int), not ruamel's round-trip nodes."""

    from . import yamlio

    parsed = yamlio.loads(dumps(data))
    return parsed if isinstance(parsed, dict) else {}


def write_atomic(path: Path, data: Any) -> None:
    """Write the document over ``path`` atomically: a sibling temp file
    renamed into place, so the original stands until the write is whole."""

    path.parent.mkdir(parents=True, exist_ok=True)
    text = dumps(data)
    tmp = path.with_name(f".{path.name}.press-tmp")
    try:
        with tmp.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


# ---- dotted-path navigation ------------------------------------------

def split_path(dotted: str) -> list[str]:
    """A dotted config path into its segments, rejecting the malformed
    forms a shell makes easy to type: empty, leading/trailing/doubled
    dots, or whitespace in a segment."""

    if not dotted or not dotted.strip():
        raise ConfigError("empty config path")
    segments = dotted.split(".")
    for segment in segments:
        if not segment:
            raise ConfigError(
                f"malformed path {dotted!r}: empty segment "
                "(no leading, trailing, or doubled dots)"
            )
        if segment != segment.strip() or " " in segment:
            raise ConfigError(f"malformed path {dotted!r}: whitespace in {segment!r}")
    return segments


_MISSING = object()


def get_path(data: Any, dotted: str) -> Any:
    """Read the value at a dotted path. A missing key or a walk through a
    non-mapping raises ConfigError; the caller decides whether that is an
    error or an honest 'unset'."""

    node: Any = data
    walked: list[str] = []
    for segment in split_path(dotted):
        if not isinstance(node, dict):
            raise ConfigError(
                f"{'.'.join(walked) or '(root)'} is not a mapping; "
                f"cannot read {dotted!r}"
            )
        if segment not in node:
            raise ConfigError(f"{dotted}: not set")
        node = node[segment]
        walked.append(segment)
    return node


def has_path(data: Any, dotted: str) -> bool:
    try:
        get_path(data, dotted)
        return True
    except ConfigError:
        return False


def set_path(data: Any, dotted: str, value: Any) -> None:
    """Set the value at a dotted path, creating intermediate mappings.
    Refuses to overwrite a scalar with a sub-key (that would silently
    discard the scalar)."""

    segments = split_path(dotted)
    node = data
    for i, segment in enumerate(segments[:-1]):
        if segment not in node or node[segment] is None:
            node[segment] = {}
        node = node[segment]
        if not isinstance(node, dict):
            raise ConfigError(
                f"{'.'.join(segments[: i + 1])} is a value, not a mapping; "
                f"cannot set {dotted!r} beneath it"
            )
    node[segments[-1]] = value


def del_path(data: Any, dotted: str) -> bool:
    """Remove the key at a dotted path. Returns False when the path was
    already absent (so `unset` is idempotent), True when it removed
    something. Empty parent mappings created by a prior `set` are left in
    place; the user can unset them explicitly."""

    segments = split_path(dotted)
    node = data
    for segment in segments[:-1]:
        if not isinstance(node, dict) or segment not in node:
            return False
        node = node[segment]
    if not isinstance(node, dict) or segments[-1] not in node:
        return False
    del node[segments[-1]]
    return True


# ---- typed coercion --------------------------------------------------

# Field type names the registry may declare. Scalars coerce from a shell
# string; collection types must arrive as explicit JSON so no comma or
# bracket is guessed at.
SCALAR_TYPES = {"str", "int", "float", "bool"}
JSON_TYPES = {"list[str]", "mapping", "list"}
KNOWN_TYPES = SCALAR_TYPES | JSON_TYPES

_TRUE = {"true", "yes", "on", "1"}
_FALSE = {"false", "no", "off", "0"}


def coerce(raw: str, type_name: str, *, as_json: bool = False) -> Any:
    """Turn a shell string into the field's declared type, or raise a
    ConfigError naming what was expected. Never guesses: a list or mapping
    field requires ``as_json`` and valid JSON of the right shape."""

    if type_name not in KNOWN_TYPES:
        raise ConfigError(f"unknown field type {type_name!r}")

    if type_name in JSON_TYPES:
        if not as_json:
            raise ConfigError(
                f"a {type_name} value must be given as JSON (use --json), "
                "so a list or mapping is never guessed from a bare string"
            )
        return _coerce_json(raw, type_name)

    # A scalar given --json is still parsed as JSON then type-checked, so
    # `--json 3` and `3` agree for an int field.
    if as_json:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"invalid JSON: {exc}") from exc
        return _check_scalar(parsed, type_name)

    if type_name == "str":
        return raw
    if type_name == "bool":
        lowered = raw.strip().lower()
        if lowered in _TRUE:
            return True
        if lowered in _FALSE:
            return False
        raise ConfigError(f"expected a boolean (true/false), got {raw!r}")
    if type_name == "int":
        try:
            return int(raw.strip())
        except ValueError:
            raise ConfigError(f"expected an integer, got {raw!r}") from None
    if type_name == "float":
        try:
            return float(raw.strip())
        except ValueError:
            raise ConfigError(f"expected a number, got {raw!r}") from None
    raise ConfigError(f"unknown field type {type_name!r}")  # unreachable


def _coerce_json(raw: str, type_name: str) -> Any:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON: {exc}") from exc
    if type_name == "list[str]":
        if not isinstance(parsed, list) or not all(isinstance(x, str) for x in parsed):
            raise ConfigError("expected a JSON array of strings")
        return parsed
    if type_name == "list":
        if not isinstance(parsed, list):
            raise ConfigError("expected a JSON array")
        return parsed
    if type_name == "mapping":
        if not isinstance(parsed, dict):
            raise ConfigError("expected a JSON object")
        return parsed
    raise ConfigError(f"unknown field type {type_name!r}")  # unreachable


def _check_scalar(parsed: Any, type_name: str) -> Any:
    ok: dict[str, type | tuple[type, ...]] = {
        "str": str,
        "bool": bool,
        "int": int,
        "float": (int, float),
    }
    expected = ok[type_name]
    # bool is an int subclass; keep them distinct so --json true is not an int.
    if type_name == "int" and isinstance(parsed, bool):
        raise ConfigError("expected an integer, got a boolean")
    if not isinstance(parsed, expected):
        raise ConfigError(f"expected {type_name}, got {type(parsed).__name__}")
    return parsed
