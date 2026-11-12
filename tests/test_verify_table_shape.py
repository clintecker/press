"""verify_tables: every table on an HTML surface is a wrapped grid with
labelled cells or a ledger with entries (INV-table-shape)."""

import subprocess
from pathlib import Path

import pytest

from press import verify_table_shape, webmeta
from tests import lua_coverage

FILTER = (
    Path(__file__).resolve().parent.parent / "src" / "press" / "data" / "lua" / "table-shapes.lua"
)


def _pipeline(markdown: str) -> str:
    """Markdown through pandoc, the table-shapes filter, and the labeller:
    the markup an HTML surface ships."""

    result = subprocess.run(
        ["pandoc", "-f", "markdown+smart", "-t", "html", lua_coverage.filter_arg(FILTER)],
        input=markdown,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return webmeta.label_table_cells(result.stdout)


@pytest.mark.invariant("INV-table-shape")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_an_unwrapped_table_is_refused():
    with pytest.raises(SystemExit, match="outside a grid wrapper"):
        verify_table_shape.verify_tables(
            "<table><tbody><tr><td>x</td></tr></tbody></table>", "HTML"
        )


@pytest.mark.invariant("INV-table-shape")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_headed_grid_row_without_labels_is_refused():
    html = (
        '<div class="grid"><table><thead><tr><th>A</th></tr></thead>'
        '<tbody><tr class="odd"><td>x</td></tr></tbody></table></div>'
    )
    with pytest.raises(SystemExit, match="without data-label"):
        verify_table_shape.verify_tables(html, "HTML")


@pytest.mark.invariant("INV-table-shape")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_an_empty_ledger_is_refused():
    with pytest.raises(SystemExit, match="without an entry"):
        verify_table_shape.verify_tables('<div class="ledger"><dl></dl></div>', "HTML")


@pytest.mark.invariant("INV-table-shape")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_a_wrapped_labelled_grid_and_a_ledger_pass():
    html = (
        '<div class="grid"><table><thead><tr><th>A</th></tr></thead>'
        '<tbody><tr class="odd"><td data-label="A">x</td></tr></tbody></table></div>'
        '<div class="ledger"><dl><dt>k</dt><dd>v</dd></dl></div>'
    )
    assert verify_table_shape.verify_tables(html, "HTML") is None


@pytest.mark.invariant("INV-table-shape")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_a_headless_grid_needs_no_labels():
    html = '<div class="grid"><table><tbody><tr><td>k</td><td>v</td></tr></tbody></table></div>'
    assert verify_table_shape.verify_tables(html, "HTML") is None


@pytest.mark.invariant("INV-table-shape")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_a_surface_without_cards_still_owes_the_wrapper():
    headed = (
        '<div class="grid"><table><thead><tr><th>A</th></tr></thead>'
        "<tbody><tr><td>x</td></tr></tbody></table></div>"
    )
    assert verify_table_shape.verify_tables(headed, "EPUB", labels=False) is None
    with pytest.raises(SystemExit, match="outside a grid wrapper"):
        verify_table_shape.verify_tables(
            "<table><tbody><tr><td>x</td></tr></tbody></table>", "EPUB", labels=False
        )


@pytest.mark.invariant("INV-table-shape")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_an_authors_ledger_around_the_press_ledger_is_not_empty():
    html = (
        '<div class="ledger"><p>Prose.</p><div class="ledger"><dl><dt>k</dt>'
        "<dd>v</dd></dl></div></div>"
    )
    assert verify_table_shape.verify_tables(html, "HTML") is None


FORCED_LEDGER = (
    "::: {.ledger}\n| Term | Meaning |\n|---|---|\n"
    "| a | the first letter of a long alphabet that runs on |\n:::\n"
)
FORCED_GRID = "::: {.grid}\n| A | B |\n|---|---|\n| x | y |\n:::\n"


@lua_coverage.needs_pandoc
@pytest.mark.invariant("INV-table-shape")
@pytest.mark.layer("integration")
@pytest.mark.proof("positive")
@pytest.mark.parametrize("markdown", [FORCED_LEDGER, FORCED_GRID], ids=["ledger", "grid"])
def test_an_author_forced_shape_passes_through_the_real_pipeline(markdown):
    html = _pipeline(markdown)
    assert html.count('class="ledger"') + html.count('class="grid"') == 1
    assert verify_table_shape.verify_tables(html, "HTML") is None
