"""`press config` end to end on a real scaffolded book (#155).

Every test runs the CLI against a freshly scaffolded book (the fixture
sets BOOK_ROOT), exercising the full path: coerce, secret scan, route
through the real validator, round-trip, atomic write. The load-bearing
safety property — a rejected edit changes not one byte — is asserted by
comparing the file before and after.
"""

from __future__ import annotations

import json

import pytest

from press import config_cli as cli
from press import config_store as store

pytestmark = pytest.mark.layer("integration")


def _meta_bytes(book):
    return (book / "config" / "metadata.yaml").read_bytes()


# ---- get / list ------------------------------------------------------

def test_get_reads_a_scalar(scaffolded_book, capsys):
    assert cli.main(["config", "get", "title"]) == cli.EXIT_OK
    assert capsys.readouterr().out.strip() == scaffolded_book.name


def test_get_of_an_unknown_field_is_exit_three(scaffolded_book, capsys):
    assert cli.main(["config", "get", "nope"]) == cli.EXIT_UNKNOWN_FIELD
    assert "unknown field" in capsys.readouterr().out


def test_get_of_an_unset_optional_is_exit_five(scaffolded_book):
    assert cli.main(["config", "get", "motto"]) == cli.EXIT_MISSING


def test_get_of_a_structured_area_points_at_its_manager(scaffolded_book, capsys):
    assert cli.main(["config", "get", "authorities"]) == cli.EXIT_UNKNOWN_FIELD
    assert "authorities-research" in capsys.readouterr().out


def test_get_json_is_machine_readable(scaffolded_book, capsys):
    cli.main(["config", "get", "title", "--json"])
    assert json.loads(capsys.readouterr().out) == scaffolded_book.name


def test_list_names_paths_and_parses_as_json(scaffolded_book, capsys):
    assert cli.main(["config", "list", "--json"]) == cli.EXIT_OK
    rows = json.loads(capsys.readouterr().out)
    paths = {r["path"] for r in rows}
    assert "title" in paths and "commerce.print-ordering.enabled" in paths
    assert "trim" in paths  # the immutable field is listed, classified


# ---- set: the happy path --------------------------------------------

def test_set_then_get_round_trips_and_preserves_comments(scaffolded_book, capsys):
    before = (scaffolded_book / "config" / "metadata.yaml").read_text()
    assert "# Press facts" in before  # the template's guidance comments
    assert cli.main(["config", "set", "subtitle", "A New Subtitle"]) == cli.EXIT_OK
    capsys.readouterr()
    assert cli.main(["config", "get", "subtitle"]) == cli.EXIT_OK
    assert capsys.readouterr().out.strip() == "A New Subtitle"
    after = (scaffolded_book / "config" / "metadata.yaml").read_text()
    assert "# Press facts" in after           # comments survived the write
    assert "A New Subtitle" in after


def test_dry_run_shows_a_diff_but_writes_nothing(scaffolded_book, capsys):
    before = _meta_bytes(scaffolded_book)
    assert cli.main(["config", "set", "subtitle", "X", "--dry-run"]) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "dry run" in out and "+subtitle: X" in out.replace('"', "")
    assert _meta_bytes(scaffolded_book) == before  # untouched


def test_a_list_field_takes_json_and_a_bare_string_is_refused(scaffolded_book, capsys):
    assert cli.main(["config", "set", "keywords", "a,b"]) == cli.EXIT_REFUSED
    assert "--json" in capsys.readouterr().out
    assert cli.main(
        ["config", "set", "keywords", '["essays", "press"]', "--json"]) == cli.EXIT_OK
    capsys.readouterr()
    cli.main(["config", "get", "keywords", "--json"])
    assert json.loads(capsys.readouterr().out) == ["essays", "press"]


# ---- set: refusals leave every byte unchanged ------------------------

def test_an_out_of_range_enum_is_refused_and_changes_nothing(scaffolded_book, capsys):
    before = _meta_bytes(scaffolded_book)
    assert cli.main(["config", "set", "print.paper", "glossy"]) == cli.EXIT_REFUSED
    assert "white, cream" in capsys.readouterr().out
    assert _meta_bytes(scaffolded_book) == before


def test_a_non_https_url_is_refused(scaffolded_book):
    before = _meta_bytes(scaffolded_book)
    assert cli.main(
        ["config", "set", "commerce.print-ordering.storefront-url",
         "http://insecure.test"]) == cli.EXIT_REFUSED
    assert _meta_bytes(scaffolded_book) == before


@pytest.mark.parametrize("value", ["no", "true", "2026"])
def test_a_retypeable_value_survives_as_the_string_set(scaffolded_book, value):
    # `config set subtitle true` must not become the boolean True (and then
    # the literal "True") when the build reads the file back.
    from press import bookmodel, yamlio

    assert cli.main(["config", "set", "subtitle", value]) == cli.EXIT_OK
    raw = (scaffolded_book / "config" / "metadata.yaml").read_text()
    assert yamlio.loads(raw)["subtitle"] == value
    # And the typed model the build uses agrees.
    book = bookmodel.load(scaffolded_book, yamlio.loads(raw))
    assert book.subtitle == value


def test_a_bad_type_value_that_looks_secret_is_not_echoed(scaffolded_book, capsys):
    secret = "api_key=sk-abcdefghijklmnop0123456789"
    # retail is a bool field; the value fails coercion, but the secret scan
    # runs on the raw input first, so the value is never printed.
    assert cli.main(
        ["config", "set", "registrations.retail", secret]) == cli.EXIT_REFUSED
    assert secret not in capsys.readouterr().out


def test_a_secret_value_is_refused_and_never_echoed(scaffolded_book, capsys):
    before = _meta_bytes(scaffolded_book)
    secret = "sk-abcdefghijklmnop0123456789"
    assert cli.main(
        ["config", "set", "commerce.print-ordering.seller-of-record", secret]
    ) == cli.EXIT_REFUSED
    out = capsys.readouterr().out
    assert "looks like a secret" in out
    assert secret not in out                       # the value is not printed back
    assert _meta_bytes(scaffolded_book) == before


def test_a_secret_inside_a_json_collection_is_also_refused(scaffolded_book):
    before = (scaffolded_book / "config" / "aesthetic.yaml")
    original = before.read_text() if before.is_file() else None
    assert cli.main(
        ["config", "set", "web-palette",
         '{"cloth": "sk-abcdefghijklmnop0123456789"}', "--json"]
    ) == cli.EXIT_REFUSED
    now = before.read_text() if before.is_file() else None
    assert now == original  # nothing written


def test_a_write_that_breaks_whole_file_validation_is_refused(scaffolded_book, capsys):
    before = _meta_bytes(scaffolded_book)
    # A slug with a space fails bookmodel's slug law; the real validator,
    # not the CLI, refuses it, and the file is untouched.
    assert cli.main(["config", "set", "slug", "Not A Slug"]) == cli.EXIT_REFUSED
    assert "slug" in capsys.readouterr().out.lower()
    assert _meta_bytes(scaffolded_book) == before


def test_setting_a_non_writable_field_is_refused(scaffolded_book, capsys):
    assert cli.main(["config", "set", "trim", "7"]) == cli.EXIT_UNKNOWN_FIELD
    assert "not writable" in capsys.readouterr().out


def test_hostile_path_shapes_are_refused(scaffolded_book):
    for bad in ["title.", ".title", "a..b"]:
        assert cli.main(["config", "set", bad, "x"]) in (
            cli.EXIT_UNKNOWN_FIELD, cli.EXIT_REFUSED)


# ---- unset -----------------------------------------------------------

def test_unset_removes_an_optional_field(scaffolded_book, capsys):
    cli.main(["config", "set", "motto", "festina lente"])
    capsys.readouterr()
    assert cli.main(["config", "unset", "motto"]) == cli.EXIT_OK
    assert cli.main(["config", "get", "motto"]) == cli.EXIT_MISSING


def test_unset_of_a_required_field_is_refused(scaffolded_book, capsys):
    before = _meta_bytes(scaffolded_book)
    assert cli.main(["config", "unset", "title"]) == cli.EXIT_REFUSED
    assert "required" in capsys.readouterr().out
    assert _meta_bytes(scaffolded_book) == before


# ---- validate --------------------------------------------------------

def test_validate_passes_a_fresh_book(scaffolded_book, capsys):
    assert cli.main(["config", "validate"]) == cli.EXIT_OK
    assert "metadata.yaml: ok" in capsys.readouterr().out


def test_validate_reports_a_hand_broken_file(scaffolded_book, capsys):
    path = scaffolded_book / "config" / "metadata.yaml"
    data = store.load(path)
    store.set_path(data, "registrations.isbn.print", "9780306406150")  # bad check digit
    store.write_atomic(path, data)
    assert cli.main(["config", "validate"]) == cli.EXIT_REFUSED
    assert "isbn" in capsys.readouterr().out.lower()


# ---- the acceptance flow: stand up ordering with no hand-editing -----

def test_seller_of_record_ordering_is_configured_entirely_by_cli(scaffolded_book, capsys):
    # Fill the block while it is still disabled (each step stays valid),
    # then enable it last: enabling an incomplete block is correctly
    # refused, so this is the natural order.
    steps = [
        ("commerce.print-ordering.edition", "paperback", []),
        ("commerce.print-ordering.storefront-url", "https://www.lulu.com/shop/x", []),
        ("commerce.print-ordering.seller-of-record", "Lulu", []),
        ("commerce.print-ordering.enabled", "true", ["--json"]),
    ]
    for path, value, flags in steps:
        assert cli.main(["config", "set", path, value, *flags]) == cli.EXIT_OK, path
        capsys.readouterr()
    assert cli.main(["config", "validate"]) == cli.EXIT_OK


def test_enabling_an_incomplete_ordering_block_is_refused_with_the_missing_fields(
    scaffolded_book, capsys):
    before = _meta_bytes(scaffolded_book)
    assert cli.main(
        ["config", "set", "commerce.print-ordering.enabled", "true", "--json"]
    ) == cli.EXIT_REFUSED
    out = capsys.readouterr().out
    assert "storefront-url" in out and "seller-of-record" in out
    assert _meta_bytes(scaffolded_book) == before
    # And the real commerce validator agrees the block is complete.
    from press import commerce
    meta = store.load(scaffolded_book / "config" / "metadata.yaml")
    assert commerce.validate(commerce.load(dict(meta))) == []
