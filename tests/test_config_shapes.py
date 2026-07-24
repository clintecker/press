"""The build-consumed optional config files are shape-checked at check
time, not with a bare TypeError deep in a generator (#207).

A malformed config/index-terms.yaml (a ``terms:`` wrapper around bare
strings, wrong-shaped entries) once passed ``press check`` and then
crashed gen_index.py at PDF build with ``string indices must be
integers``. Its structured, build-read friends (authorities,
front-matter, house-rules) shared the gap. These tests prove the typed
shape validators reject each malformed shape with a located diagnostic,
and that ``press check`` (check_source) turns red on a scaffolded book
whose index-terms is the exact shape from the bug report.
"""

from __future__ import annotations

from pathlib import Path

from press import check_source
from press import config_schema as schema
from press import config_store as store

ROOT = Path(".")


# ---- index-terms: the reported bug -----------------------------------

def test_index_terms_terms_wrapper_is_refused_by_shape():
    # The exact shape from the issue: a terms: key around bare strings.
    problems = schema.validate_file(ROOT, schema.INDEX_TERMS, {"terms": ["soup", "bread"]})
    assert problems and "must be a list" in problems[0]


def test_index_terms_bare_scalars_name_the_offending_entry():
    problems = schema.validate_file(ROOT, schema.INDEX_TERMS, ["soup", "bread"])
    assert any("entry 1" in p for p in problems)


def test_index_terms_missing_match_is_refused():
    problems = schema.validate_file(ROOT, schema.INDEX_TERMS, [{"term": "soup"}])
    assert any("match" in p for p in problems)


def test_index_terms_empty_term_is_refused():
    problems = schema.validate_file(
        ROOT, schema.INDEX_TERMS, [{"term": "  ", "match": ["soup"]}])
    assert any("term is missing or empty" in p for p in problems)


def test_index_terms_non_string_match_alternative_is_refused():
    problems = schema.validate_file(
        ROOT, schema.INDEX_TERMS, [{"term": "soup", "match": ["soup", 3]}])
    assert any("match alternative" in p for p in problems)


def test_a_well_formed_index_terms_list_passes():
    assert schema.validate_file(
        ROOT, schema.INDEX_TERMS, [{"term": "Soup", "match": ["soup", "soups"]}]) == []


def test_an_absent_index_terms_file_passes():
    # None models the empty/absent document the config path hands the validator.
    assert schema.validate_file(ROOT, schema.INDEX_TERMS, None) == []


# ---- authorities -----------------------------------------------------

def test_authorities_mapping_top_level_is_refused():
    problems = schema.validate_file(ROOT, schema.AUTHORITIES, {"claim": "x"})
    assert problems and "must be a list" in problems[0]


def test_authorities_entry_missing_authority_is_refused():
    problems = schema.validate_file(ROOT, schema.AUTHORITIES, [{"claim": "the sky is blue"}])
    assert any("authority is missing or empty" in p for p in problems)


def test_a_well_formed_authorities_list_passes_the_shape_check():
    assert schema.validate_file(
        ROOT, schema.AUTHORITIES,
        [{"claim": "x", "authority": "Someone, A Book (1900)"}]) == []


# ---- front-matter ----------------------------------------------------

def test_front_matter_list_top_level_is_refused():
    problems = schema.validate_file(ROOT, schema.FRONT_MATTER, ["dedication"])
    assert problems and "must be a YAML mapping" in problems[0]


def test_front_matter_scalar_epigraph_is_refused():
    problems = schema.validate_file(
        ROOT, schema.FRONT_MATTER, {"epigraph": "a bare string"})
    assert any("epigraph must be a mapping" in p for p in problems)


def test_a_well_formed_front_matter_mapping_passes():
    assert schema.validate_file(
        ROOT, schema.FRONT_MATTER,
        {"dedication": "For no one", "epigraph": {"quote": "Q"}}) == []


# ---- house-rules -----------------------------------------------------

def test_house_rules_banned_patterns_as_a_list_is_refused_not_crashed():
    # dict(["a", "b"]) would raise a bare ValueError inside the regex
    # compiler; the shape guard turns it into a located diagnostic.
    problems = schema.validate_file(
        ROOT, schema.HOUSE_RULES, {"banned-patterns": ["a", "b"]})
    assert any("banned-patterns must be a mapping" in p for p in problems)


def test_house_rules_jargon_allow_as_a_mapping_is_refused():
    problems = schema.validate_file(
        ROOT, schema.HOUSE_RULES, {"jargon-allow": {"a": 1}})
    assert any("jargon-allow must be a list of strings" in p for p in problems)


def test_a_bad_house_rules_regex_still_names_the_pattern():
    problems = schema.validate_file(
        ROOT, schema.HOUSE_RULES, {"banned-patterns": {"([": "unbalanced"}})
    assert any("valid regex" in p for p in problems)


# ---- the integration proof: press check turns red --------------------

def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_check_source_passes_a_clean_scaffolded_book(scaffolded_book):
    assert check_source.main() == 0


def test_check_source_rejects_the_reported_index_terms_shape(scaffolded_book, capsys):
    # The exact regression: a terms: wrapper around bare strings. Before the
    # fix this passed check and crashed gen_index at PDF build.
    _write(scaffolded_book / "config" / "index-terms.yaml", "terms:\n  - soup\n  - bread\n")
    assert check_source.main() == 1
    out = capsys.readouterr().out
    assert "config/index-terms.yaml" in out
    assert "must be a list" in out


def test_check_source_rejects_a_malformed_authorities_ledger(scaffolded_book, capsys):
    _write(scaffolded_book / "config" / "authorities.yaml", "- claim: the sky is blue\n")
    assert check_source.main() == 1
    out = capsys.readouterr().out
    assert "config/authorities.yaml" in out and "authority" in out


def test_check_source_rejects_a_scalar_front_matter_epigraph(scaffolded_book, capsys):
    _write(scaffolded_book / "config" / "front-matter.yaml", "epigraph: just a line\n")
    assert check_source.main() == 1
    out = capsys.readouterr().out
    assert "config/front-matter.yaml" in out and "epigraph" in out


def test_check_source_accepts_a_well_formed_index_terms_file(scaffolded_book):
    _write(
        scaffolded_book / "config" / "index-terms.yaml",
        "- term: Soup\n  match: [soup, soups]\n",
    )
    # The scaffolded manuscript need not contain the term for check_source,
    # which validates shape only; the zero-hit rule lives in the build.
    assert check_source.main() == 0


def test_a_hand_broken_index_terms_is_also_caught_by_config_validate(scaffolded_book):
    path = scaffolded_book / "config" / "index-terms.yaml"
    _write(path, "terms:\n  - soup\n")
    data = store.load(path)
    assert schema.validate_file(scaffolded_book, "config/index-terms.yaml", data)
