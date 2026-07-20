"""The `press config` mechanics (#155): round-trip, atomic write, dotted
paths, and unambiguous coercion. These are the invariant-bearing
primitives; the CLI and schema are proven separately.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from press import config_store as cs

# ---- dotted-path parsing ---------------------------------------------

@pytest.mark.parametrize("bad", ["", "   ", ".", "a.", ".a", "a..b", "a. b", "a b.c"])
def test_a_malformed_path_is_refused(bad):
    with pytest.raises(cs.ConfigError):
        cs.split_path(bad)


@pytest.mark.parametrize("good,expected", [
    ("title", ["title"]),
    ("commerce.print-ordering.enabled", ["commerce", "print-ordering", "enabled"]),
    ("registrations.isbn.print", ["registrations", "isbn", "print"]),
])
def test_a_well_formed_path_splits(good, expected):
    assert cs.split_path(good) == expected


@given(st.lists(st.from_regex(r"[a-zA-Z0-9_-]+", fullmatch=True), min_size=1, max_size=6))
def test_split_join_round_trips(segments):
    dotted = ".".join(segments)
    assert cs.split_path(dotted) == segments


# ---- get / set / unset ------------------------------------------------

def test_set_creates_intermediate_mappings_then_get_reads_them():
    data: dict = {}
    cs.set_path(data, "commerce.print-ordering.enabled", True)
    assert cs.get_path(data, "commerce.print-ordering.enabled") is True
    assert cs.has_path(data, "commerce.print-ordering")
    assert not cs.has_path(data, "commerce.print-ordering.missing")


def test_get_of_a_missing_path_raises():
    with pytest.raises(cs.ConfigError, match="not set"):
        cs.get_path({"a": {}}, "a.b")


def test_set_refuses_to_bury_a_scalar():
    data = {"title": "hi"}
    with pytest.raises(cs.ConfigError, match="not a mapping"):
        cs.set_path(data, "title.sub", 1)


def test_get_through_a_scalar_raises():
    with pytest.raises(cs.ConfigError, match="not a mapping"):
        cs.get_path({"title": "hi"}, "title.sub")


def test_unset_is_idempotent_and_reports_whether_it_removed():
    data = {"a": {"b": 1}}
    assert cs.del_path(data, "a.b") is True
    assert cs.del_path(data, "a.b") is False       # already gone
    assert cs.del_path(data, "x.y.z") is False      # never existed
    assert cs.has_path(data, "a")                    # empty parent left in place


# ---- coercion: never guess a type from the string --------------------

def test_a_string_field_keeps_the_literal_text():
    assert cs.coerce("true", "str") == "true"
    assert cs.coerce("42", "str") == "42"


def test_bool_and_int_and_float_coerce_by_declared_type():
    assert cs.coerce("yes", "bool") is True
    assert cs.coerce("off", "bool") is False
    assert cs.coerce("24", "int") == 24
    assert cs.coerce("0.0025", "float") == 0.0025


@pytest.mark.parametrize("value,type_name", [
    ("maybe", "bool"), ("3.5", "int"), ("twelve", "int"), ("wide", "float"),
])
def test_a_scalar_that_does_not_fit_its_type_is_refused(value, type_name):
    with pytest.raises(cs.ConfigError):
        cs.coerce(value, type_name)


def test_a_collection_field_requires_explicit_json():
    with pytest.raises(cs.ConfigError, match="--json"):
        cs.coerce("a,b", "list[str]")
    assert cs.coerce('["a", "b"]', "list[str]", as_json=True) == ["a", "b"]
    assert cs.coerce('{"k": "v"}', "mapping", as_json=True) == {"k": "v"}


def test_a_json_list_of_the_wrong_shape_is_refused():
    with pytest.raises(cs.ConfigError, match="array of strings"):
        cs.coerce('[1, 2]', "list[str]", as_json=True)
    with pytest.raises(cs.ConfigError, match="object"):
        cs.coerce('[]', "mapping", as_json=True)


def test_json_scalar_keeps_bool_and_int_distinct():
    # bool is an int subclass; --json true must not satisfy an int field.
    with pytest.raises(cs.ConfigError):
        cs.coerce("true", "int", as_json=True)
    assert cs.coerce("true", "bool", as_json=True) is True


# ---- round-trip: comments and untouched keys survive -----------------

ROUNDTRIP_SAMPLE = """\
# The book's identity.
title: "Old Title"      # keep this comment
author:
  - A. Author
# a trailing note the user wrote
verify-min-pages: 40
"""


def test_editing_one_key_preserves_comments_and_other_keys(tmp_path):
    path = tmp_path / "metadata.yaml"
    path.write_text(ROUNDTRIP_SAMPLE, encoding="utf-8")
    data = cs.load(path)
    cs.set_path(data, "title", "New Title")
    cs.write_atomic(path, data)
    out = path.read_text(encoding="utf-8")
    assert "New Title" in out and "Old Title" not in out
    assert "# The book's identity." in out       # leading comment survives
    assert "keep this comment" in out             # inline comment survives
    assert "a trailing note the user wrote" in out
    assert "verify-min-pages: 40" in out          # untouched key survives


def test_a_missing_file_loads_empty_and_a_first_set_creates_it(tmp_path):
    path = tmp_path / "new.yaml"
    data = cs.load(path)
    cs.set_path(data, "a.b", "c")
    cs.write_atomic(path, data)
    assert cs.get_path(cs.load(path), "a.b") == "c"


def test_a_malformed_file_is_a_config_error_not_a_traceback(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("title: [unterminated\n", encoding="utf-8")
    with pytest.raises(cs.ConfigError, match="not valid YAML"):
        cs.load(path)


# ---- write-safety: agree with the build's YAML 1.1 loader --------------

@pytest.mark.parametrize("text", ["no", "yes", "on", "off", "true", "2026", "3.5", "null", "~"])
def test_a_string_typed_value_survives_as_the_string_set(text, tmp_path):
    from press import yamlio

    path = tmp_path / "m.yaml"
    data = cs.load(path)
    cs.set_path(data, "subtitle", cs.write_safe(text))
    cs.write_atomic(path, data)
    # Read back through the package's own loader: whether write_safe quoted
    # it or not, the value must be the string the user set, never a
    # bool/int/None.
    reloaded = yamlio.loads(path.read_text(encoding="utf-8"))
    assert reloaded["subtitle"] == text
    assert isinstance(reloaded["subtitle"], str)


def test_write_safe_quotes_only_what_the_loader_would_retype():
    from ruamel.yaml.scalarstring import DoubleQuotedScalarString

    def quoted(v):
        return isinstance(cs.write_safe(v), DoubleQuotedScalarString)

    # Under YAML 1.2, no/yes/on are already strings -- no quoting needed.
    assert not quoted("Hello World") and not quoted("no") and not quoted("yes")
    # But a value the loader would read as a bool/number/null is quoted.
    assert quoted("true") and quoted("2026") and quoted("3.5") and quoted("~")
    # An already-quoted scalar is left as is (not double-wrapped).
    assert cs.write_safe(DoubleQuotedScalarString("x")) == "x"
    # A value that will not even parse as bare YAML is quoted, not crashed.
    assert quoted("[unterminated")
    # Non-string leaves pass through untouched.
    assert cs.write_safe(24) == 24 and cs.write_safe(True) is True


def test_as_build_reads_returns_parsed_types_and_tolerates_non_mappings():
    m = {"verify-min-pages": 24, "flag": cs.write_safe("true")}
    # The quoted "true" reads back as a string; the bare 24 as an int.
    assert cs.as_build_reads(m) == {"verify-min-pages": 24, "flag": "true"}
    from ruamel.yaml.comments import CommentedSeq
    assert cs.as_build_reads(CommentedSeq()) == {}


def test_write_safe_reaches_string_leaves_in_collections(tmp_path):
    from press import yamlio

    path = tmp_path / "m.yaml"
    data = cs.load(path)
    cs.set_path(data, "keywords", cs.write_safe(["true", "plain", "2026"]))
    cs.write_atomic(path, data)
    # Every retypeable element survives as a string through the loader.
    assert yamlio.loads(path.read_text())["keywords"] == ["true", "plain", "2026"]


def test_write_is_atomic_leaving_no_temp_behind(tmp_path):
    path = tmp_path / "metadata.yaml"
    path.write_text(ROUNDTRIP_SAMPLE, encoding="utf-8")
    data = cs.load(path)
    cs.set_path(data, "title", "X")
    cs.write_atomic(path, data)
    siblings = [p.name for p in tmp_path.iterdir()]
    assert siblings == ["metadata.yaml"]          # no .press-tmp residue
