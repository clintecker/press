"""`press check` must refuse a trim + ink + provider combination the chosen
printer will not make, before any render (#222). The source-check pass reads
the book's selected design profile (trim, ink), its provider spec, and its
binding, and turns red on an unsupported combination -- the negative fixture
this verifier owes. A book that names no provider keeps the house spec, which
declares no catalog and refuses nothing, so the default scaffold is unaffected.
"""

from __future__ import annotations

import pytest

from press import check_source, config_cli, selftest


def _set(root, edits) -> None:
    preview = config_cli.preview_edits(root, "config/metadata.yaml", edits)
    assert not preview.problems, preview.problems
    config_cli.commit(preview)
    selftest.clear_book_caches()


@pytest.mark.layer("integration")
def test_the_default_scaffold_passes_the_format_gate(scaffolded_book):
    # House provider, house profile, perfect-bound: no catalog, no refusal.
    assert check_source._print_format_failures() == []


@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_check_refuses_a_binding_the_provider_does_not_offer(scaffolded_book, capsys):
    # KDP offers no dust jacket at any trim; the source check must refuse it.
    _set(scaffolded_book, [
        ("print.provider", "kdp"),
        ("print.binding", "dust-jacket"),
    ])
    problems = check_source._print_format_failures()
    assert any("does not offer" in p for p in problems), problems

    assert check_source.main() == 1
    out = capsys.readouterr().out
    assert "6 x 9" in out and "dust-jacket" in out


@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_check_refuses_a_color_interior_at_a_single_ink_provider(scaffolded_book):
    # A color design profile at Lulu (no color caliper) is refused at check
    # time, not deep in the spine math at render.
    _set(scaffolded_book, [
        ("print.profile", "house-6x9-color"),
        ("print.provider", "lulu"),
    ])
    problems = check_source._print_format_failures()
    assert any("does not print a color interior" in p for p in problems), problems


@pytest.mark.layer("integration")
def test_check_accepts_a_supported_combination(scaffolded_book):
    # 6x9 perfect-bound colour at KDP is a combination KDP makes: no refusal.
    _set(scaffolded_book, [
        ("print.profile", "house-6x9-color"),
        ("print.provider", "kdp"),
    ])
    assert check_source._print_format_failures() == []
