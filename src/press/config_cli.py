"""`press config` — read and write a book's configuration safely.

    press config list [--file F] [--json]
    press config get  <path> [--json]
    press config set  <path> <value> [--json] [--dry-run]
    press config unset <path> [--dry-run]
    press config validate [--json]

A write is validated against the proposed document by the real loader for
that file before a byte is touched; a rejected edit changes nothing. The
edit is applied to a comment-preserving round-trip of the file and written
atomically. Secret-looking values are refused rather than stored, and a
value is never printed back on the refusal.

Exit codes are deterministic: 0 success, 2 usage error, 3 unknown or
non-writable field, 4 validation failure (the edit was refused), 5 a
missing key on read.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from . import booklib, config_schema as schema, config_store as store

# A value that looks like a credential has no place in a book's config; the
# commerce validator enforces this too, but the writer refuses before it
# ever reaches disk, and never echoes the offending value.
_SECRET = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|bearer|-----BEGIN|"
    r"sk-[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,})"
)

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_UNKNOWN_FIELD = 3
EXIT_REFUSED = 4
EXIT_MISSING = 5


class _Refusal(Exception):
    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="press config", add_help=True)
    sub = parser.add_subparsers(dest="verb", required=True)

    p_list = sub.add_parser("list", help="every known field and its classification")
    p_list.add_argument("--file", default=None, help="restrict to one config file")
    p_list.add_argument("--json", action="store_true")

    p_get = sub.add_parser("get", help="read a field")
    p_get.add_argument("path")
    p_get.add_argument("--json", action="store_true")

    p_set = sub.add_parser("set", help="write a field")
    p_set.add_argument("path")
    p_set.add_argument("value")
    p_set.add_argument("--json", action="store_true", help="value is JSON (lists/mappings)")
    p_set.add_argument("--dry-run", action="store_true", help="show the diff, write nothing")

    p_unset = sub.add_parser("unset", help="remove a field")
    p_unset.add_argument("path")
    p_unset.add_argument("--dry-run", action="store_true")

    p_val = sub.add_parser("validate", help="run every config validator")
    p_val.add_argument("--json", action="store_true")

    return parser


def main(args: list[str]) -> int:
    parser = _parser()
    ns = parser.parse_args(args[1:])  # args[0] is "config"
    try:
        root = booklib.root()
    except SystemExit as exc:
        print(str(exc))
        return EXIT_USAGE
    try:
        return _dispatch(ns, root)
    except store.ConfigError as exc:
        print(str(exc))
        return EXIT_REFUSED
    except _Refusal as exc:
        print(str(exc))
        return exc.code


def _dispatch(ns: argparse.Namespace, root: Path) -> int:
    if ns.verb == "list":
        return _list(ns)
    if ns.verb == "get":
        return _get(ns, root)
    if ns.verb == "set":
        return _set(ns, root)
    if ns.verb == "unset":
        return _unset(ns, root)
    if ns.verb == "validate":
        return _validate(ns, root)
    return EXIT_USAGE  # unreachable: argparse requires a verb


# ---- list ------------------------------------------------------------

def _list(ns: argparse.Namespace) -> int:
    fields = [f for f in schema.REGISTRY if ns.file in (None, f.file)]
    if ns.json:
        print(json.dumps([
            {"path": f.path, "file": f.file, "kind": f.kind,
             "type": f.type if f.writable else None, "help": f.help,
             "required": f.required, "choices": list(f.choices) or None,
             "manager": f.manager or None}
            for f in fields
        ], indent=2))
        return EXIT_OK
    width = max((len(f.path) for f in fields), default=0)
    for f in fields:
        tag = f.type if f.writable else f.kind.upper()
        req = " (required)" if f.required else ""
        print(f"  {f.path:<{width}}  {tag:<9} {f.help}{req}")
        if not f.writable and f.manager:
            print(f"  {'':<{width}}  {'':<9} -> {f.manager}")
    return EXIT_OK


# ---- get -------------------------------------------------------------

def _get(ns: argparse.Namespace, root: Path) -> int:
    field = schema.field_for(ns.path)
    if field is None:
        raise _Refusal(f"unknown field {ns.path!r}; see `press config list`",
                       EXIT_UNKNOWN_FIELD)
    if not field.file or field.whole_file:
        raise _Refusal(f"{ns.path} is a {field.kind} area, not a single key; "
                       f"{field.manager}", EXIT_UNKNOWN_FIELD)
    data = store.load(root / field.file)
    try:
        value = store.get_path(data, ns.path)
    except store.ConfigError:
        raise _Refusal(f"{ns.path}: not set", EXIT_MISSING) from None
    if ns.json:
        print(json.dumps(_plain(value)))
    else:
        print(_render_scalar(value))
    return EXIT_OK


# ---- set -------------------------------------------------------------

def _set(ns: argparse.Namespace, root: Path) -> int:
    field = _writable_or_refuse(ns.path)
    # Scan the raw input before coercion, so a coercion error can never echo
    # a secret-looking value back to the terminal.
    _refuse_secret(field, ns.value)
    value = store.coerce(ns.value, field.type, as_json=ns.json)
    _refuse_secret(field, value)
    _refuse_bad_shape(field, value)

    path = root / field.file
    before = store.load(path)
    after = store.load(path)
    store.set_path(after, ns.path, store.write_safe(value))

    problems = schema.validate_file(root, field.file, after)
    if problems:
        raise _Refusal(_problem_report(field.file, problems), EXIT_REFUSED)

    return _commit(path, before, after, ns.dry_run)


# ---- unset -----------------------------------------------------------

def _unset(ns: argparse.Namespace, root: Path) -> int:
    field = _writable_or_refuse(ns.path)
    if field.required:
        raise _Refusal(f"{ns.path} is required and cannot be unset", EXIT_REFUSED)
    path = root / field.file
    before = store.load(path)
    after = store.load(path)
    if not store.del_path(after, ns.path):
        print(f"{ns.path}: already unset")
        return EXIT_OK

    problems = schema.validate_file(root, field.file, after)
    if problems:
        raise _Refusal(_problem_report(field.file, problems), EXIT_REFUSED)

    return _commit(path, before, after, ns.dry_run)


# ---- validate --------------------------------------------------------

def _validate(ns: argparse.Namespace, root: Path) -> int:
    report: dict[str, list[str]] = {}
    for file in schema.FILE_VALIDATORS:
        data = store.load(root / file)
        report[file] = schema.validate_file(root, file, data)
    total = sum(len(v) for v in report.values())
    if ns.json:
        print(json.dumps(report, indent=2))
    else:
        for file, problems in report.items():
            mark = "ok" if not problems else f"{len(problems)} problem(s)"
            print(f"{file}: {mark}")
            for problem in problems:
                print(f"  - {problem}")
    return EXIT_OK if total == 0 else EXIT_REFUSED


# ---- helpers ---------------------------------------------------------

def _writable_or_refuse(path: str) -> schema.Field:
    field = schema.field_for(path)
    if field is None:
        raise _Refusal(f"unknown field {path!r}; see `press config list`",
                       EXIT_UNKNOWN_FIELD)
    if not field.writable:
        why = field.manager or f"it is {field.kind}"
        raise _Refusal(f"{path} is not writable through `press config`: {why}",
                       EXIT_UNKNOWN_FIELD)
    return field


def _refuse_secret(field: schema.Field, value) -> None:
    # Scan every string leaf, including inside a --json list or mapping, so a
    # credential cannot ride in through a collection value.
    if _has_secret_leaf(value):
        # Never echo the value: the refusal names the field only.
        raise _Refusal(
            f"refusing to write {field.path}: the value looks like a secret. "
            "A book's config holds no credential; keep it in your environment "
            "or the provider's dashboard.", EXIT_REFUSED)


def _has_secret_leaf(value) -> bool:
    if isinstance(value, str):
        return bool(_SECRET.search(value))
    if isinstance(value, dict):
        return any(_has_secret_leaf(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_secret_leaf(v) for v in value)
    return False


def _refuse_bad_shape(field: schema.Field, value) -> None:
    if field.choices and value not in field.choices:
        raise _Refusal(
            f"{field.path} must be one of {', '.join(field.choices)}", EXIT_REFUSED)
    if field.https and isinstance(value, str) and not value.startswith("https://"):
        raise _Refusal(f"{field.path} must be an https URL", EXIT_REFUSED)


def _commit(path: Path, before, after, dry_run: bool) -> int:
    diff = _diff(store.dumps(before), store.dumps(after), path.name)
    if not diff:
        print(f"{path.name}: no change")
        return EXIT_OK
    print(diff, end="")
    if dry_run:
        print("(dry run: nothing written)")
        return EXIT_OK
    try:
        store.write_atomic(path, after)
    except OSError as exc:
        raise _Refusal(f"could not write {path.name}: {exc}", EXIT_REFUSED) from exc
    return EXIT_OK


def _diff(before: str, after: str, name: str) -> str:
    import difflib

    lines = list(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=f"a/{name}", tofile=f"b/{name}"))
    return "".join(lines)


def _problem_report(file: str, problems: list[str]) -> str:
    body = "\n".join(f"  - {p}" for p in problems)
    return f"refused: the edit would make {file} invalid:\n{body}"


def _render_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(_plain(value))
    return str(value)


def _plain(value):
    """A ruamel round-trip node as plain JSON-serializable data."""

    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float, str)):
        return value
    return str(value)
