"""The config registry is complete and internally honest (#155).

The load-bearing guarantee is coverage: every field the configuration
reference documents must be either writable through `press config` or
carry an explicit classification. The drift test walks the reference's own
YAML examples and fails if a documented key has neither, so the CLI cannot
silently fall behind the docs.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from press import config_schema as schema
from press import config_store as store

DOCS = Path(__file__).resolve().parent.parent / "docs" / "CONFIGURATION.md"

WHOLE_FILE_FILES = {f.file for f in schema.REGISTRY if f.whole_file and f.file}


# ---- registry integrity ----------------------------------------------

def test_paths_are_unique():
    paths = [f.path for f in schema.REGISTRY]
    assert len(paths) == len(set(paths))


def test_writable_fields_declare_a_known_type_and_a_validated_file():
    for f in schema.writable_fields():
        assert f.type in store.KNOWN_TYPES, (f.path, f.type)
        # A writable field's file must have a validator route, or a set
        # would skip validation silently.
        assert f.file in schema.FILE_VALIDATORS, (f.path, f.file)


def test_non_writable_fields_tell_the_user_what_to_use_instead():
    for f in schema.REGISTRY:
        if not f.writable:
            assert f.manager, f.path


def test_constraints_only_decorate_writable_string_fields():
    for f in schema.REGISTRY:
        if f.https or f.choices:
            assert f.writable and f.type == "str", f.path


# ---- documentation drift: every documented field is covered ----------

def _sections() -> list[tuple[str | None, str]]:
    """(config-file, body) for each `##` section of the reference."""

    text = DOCS.read_text(encoding="utf-8")
    parts = re.split(r"^## (.+)$", text, flags=re.M)[1:]
    sections = []
    for heading, body in zip(parts[0::2], parts[1::2]):
        match = re.match(r"(config/[\w-]+\.yaml)", heading)
        sections.append((match.group(1) if match else None, body))
    return sections


def _leaf_paths(node, prefix=""):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _leaf_paths(value, f"{prefix}.{key}" if prefix else str(key))
    else:
        if prefix:
            yield prefix


def test_every_documented_yaml_key_is_covered_by_the_registry():
    uncovered: list[str] = []
    for file, body in _sections():
        if file is None or file in WHOLE_FILE_FILES:
            continue  # asset/tex sections have no keys; list files are whole-file
        for block in re.findall(r"```yaml\n(.*?)```", body, re.S):
            parsed = yaml.safe_load(block)
            if not isinstance(parsed, dict):
                continue  # a top-level list is a whole-file structure
            for path in _leaf_paths(parsed):
                if schema.covers(path) is None:
                    uncovered.append(f"{file}: {path}")
    assert not uncovered, (
        "documented config keys with no registry entry (add a Field or a "
        "classification):\n  " + "\n  ".join(sorted(set(uncovered)))
    )


def test_the_whole_file_structures_are_actually_documented():
    # Guard the inverse: each structured/whole-file file the registry names
    # has a section in the reference, so the classification is not stale.
    documented = {file for file, _ in _sections() if file}
    for file in WHOLE_FILE_FILES:
        assert file in documented, file
