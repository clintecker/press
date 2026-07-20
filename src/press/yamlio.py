"""The one YAML door for the whole package: ruamel.yaml at YAML 1.2.

Press used to read config with PyYAML (YAML 1.1, where a bare `no`, `yes`,
`on`, or `off` is a boolean) while the `press config` writer used ruamel
(YAML 1.2, where those are strings). The two disagreed about the document
itself, so a written `no` could be read back as `False`. One library, one
version closes that gap: every read and write in the package goes through
ruamel's 1.2 core schema here, so a bare `no` is the string "no" wherever
it is read, and the writer and the reader can never drift apart again.

Read-only consumers call `load`/`loads`/`dump`/`write`. The
comment-preserving `press config` writer keeps its own round-trip document
in `config_store`, also ruamel at 1.2; this module is the plain-data door
for everyone else. Import YAML only through here (a boundary test forbids a
raw `import yaml` elsewhere in the package).
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML, YAMLError

__all__ = ["loads", "load", "dump", "write", "YAMLError"]


def _reader() -> YAML:
    # Safe mode returns plain dict/list, matching what every consumer
    # expects; the explicit 1.2 pin documents the schema the package reads.
    # pure=True uses ruamel's Python parser, which (like PyYAML before it)
    # accepts a plain scalar containing a colon in flow context, e.g.
    # `[fixture:jargon.md]`; the C parser rejects it.
    yaml = YAML(typ="safe", pure=True)
    yaml.version = (1, 2)
    return yaml


def _writer() -> YAML:
    # Round-trip mode preserves insertion order (block style, no sorting),
    # matching the prior PyYAML `sort_keys=False` output. No version pin, so
    # no `%YAML` directive is emitted into the file.
    yaml = YAML(pure=True)
    yaml.default_flow_style = False
    yaml.allow_unicode = True
    yaml.width = 4096
    return yaml


def loads(text: str) -> Any:
    """Parse YAML text into plain data (dict/list/scalars)."""

    return _reader().load(text)


def load(path: Path | str) -> Any:
    """Parse a YAML file into plain data."""

    return _reader().load(Path(path).read_text(encoding="utf-8"))


def dump(data: Any) -> str:
    """Serialize plain data to YAML text, key order preserved."""

    buffer = io.StringIO()
    _writer().dump(data, buffer)
    return buffer.getvalue()


def write(path: Path | str, data: Any) -> None:
    """Write plain data to a YAML file."""

    Path(path).write_text(dump(data), encoding="utf-8")
