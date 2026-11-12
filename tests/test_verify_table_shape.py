"""verify_tables: every table on an HTML surface is a wrapped grid with
labelled cells or a ledger with entries (INV-table-shape)."""

import pytest

from press import verify_table_shape


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
