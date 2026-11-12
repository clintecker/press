"""The table-shapes Lua filter on the pandoc AST: a key column plus one prose
column becomes a ledger (a native DefinitionList inside Div.ledger, with its
caption and header legend kept), anything else stays a Table wrapped in
Div.grid with explicit relative column widths. A `.ledger` or `.grid` fenced
div forces the shape of every table inside it, and a document with no tables
renders byte-for-byte as before. These run pandoc directly (no LaTeX).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from tests import lua_coverage

FILTER = (
    Path(__file__).resolve().parent.parent / "src" / "press" / "data" / "lua" / "table-shapes.lua"
)

pytestmark = lua_coverage.needs_pandoc


def _render(markdown: str, to: str = "latex", filtered: bool = True) -> str:
    args = [
        "pandoc",
        "-f",
        "markdown+smart",
        "-t",
        to,
        "--top-level-division=chapter",
        "--number-sections",
    ]
    if filtered:
        args.append(lua_coverage.filter_arg(FILTER))
    result = subprocess.run(args, input=markdown, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


LEDGER = (
    "# Ch\n\n| Skill | Meaning |\n|---|---|\n"
    "| `hemingway` | It asks for concrete detail, compression, omission, and restraint"
    " without imitation. |\n"
    "| `humanizer` | It drafts, revises, and audits prose so that it reads as one"
    " writer's deliberate choices. |\n\n"
    "Table: Table 15.5. The skills that come with press\n"
)
LEDGER3 = (
    LEDGER.replace("| Skill | Meaning |\n|---|---|", "| Area | Modules | Meaning |\n|---|---|---|")
    .replace("| `hemingway` |", "| Build | `build.py`, `figures.py` |")
    .replace("| `humanizer` |", "| Verifiers | `verify_pdf.py` |")
)
GRID = (
    "# Ch\n\n| Profile | Trim | Margin |\n|---|---|---|\n"
    "| house | 6 x 9 | 0.78in |\n| pocket | 5 x 8 | 0.6in |\n"
)
# A pipe table cannot omit its header row (pandoc reads a header-less pipe
# table as a paragraph), so the header-less case is a simple table, which can.
NO_HEAD = (
    "# Ch\n\n-----  ----------\n"
    "`a`    one two three four five six seven eight nine ten\n"
    "-----  ----------\n"
)
CONTINUATION = LEDGER.replace("| `humanizer` |", "| |")
NESTED = "# Ch\n\n::: {.tip}\n" + LEDGER.split("\n\n", 1)[1] + ":::\n"


@pytest.mark.layer("integration")
@pytest.mark.proof("positive")
def test_a_key_plus_prose_table_becomes_a_ledger_in_latex():
    out = _render(LEDGER)
    assert "\\begin{PressLedger}" in out and "\\begin{description}" in out
    assert "\\item[\\texttt{hemingway}]" in out and "longtable" not in out


@pytest.mark.layer("integration")
@pytest.mark.proof("positive")
def test_a_ledger_keeps_its_caption_and_legend():
    out = _render(LEDGER, to="html")
    assert '<div class="ledger">' in out and 'class="ledger-caption"' in out
    assert "Skill \u00b7 Meaning" in out and "<dl>" in out and "<dt>" in out


@pytest.mark.layer("integration")
@pytest.mark.proof("positive")
def test_a_three_column_ledger_sets_the_middle_cell_as_sub():
    out = _render(LEDGER3, to="html")
    sub = re.search(r'<div class="ledger-sub">(.*?)</div>', out, re.S)
    assert sub is not None
    assert "<code>build.py</code>, <code>figures.py</code>" in sub.group(1)


@pytest.mark.layer("integration")
@pytest.mark.proof("positive")
def test_a_grid_stays_a_table_with_relative_widths():
    out = _render(GRID)
    assert "\\PressGridBegin" in out and "longtable" in out
    assert "\\real{" in out and "\\PressGridEnd" in out


@pytest.mark.layer("integration")
@pytest.mark.proof("positive")
def test_a_grid_is_wrapped_on_the_web():
    out = _render(GRID, to="html")
    assert '<div class="grid">' in out and "<table" in out


@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_a_grid_wrapper_forces_a_table():
    out = _render("# Ch\n\n::: {.grid}\n" + LEDGER.split("\n\n", 1)[1] + ":::\n", to="html")
    assert "<table" in out and 'class="ledger"' not in out


@pytest.mark.layer("integration")
@pytest.mark.proof("positive")
def test_a_ledger_wrapper_forces_a_list():
    out = _render("# Ch\n\n::: {.ledger}\n" + GRID.split("\n\n", 1)[1] + ":::\n", to="html")
    assert "<dl>" in out and "<table" not in out


@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_a_table_with_no_header_row_classifies_without_a_legend():
    out = _render(NO_HEAD, to="html")
    assert "<dl>" in out and "ledger-legend" not in out


@pytest.mark.layer("integration")
@pytest.mark.proof("positive")
def test_an_empty_key_cell_continues_the_previous_entry():
    out = _render(CONTINUATION, to="html")
    assert out.count("<dt>") == 1 and out.count("<dd>") == 1


@pytest.mark.layer("integration")
@pytest.mark.proof("positive")
def test_a_table_inside_an_admonition_is_still_rewritten():
    assert '<div class="ledger">' in _render(NESTED, to="html")


@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_a_document_with_no_tables_is_byte_identical():
    doc = "# Ch\n\nProse only.\n\n- a list\n"
    for fmt in ("latex", "html", "plain"):
        assert _render(doc, to=fmt, filtered=False) == _render(doc, to=fmt)


@pytest.mark.layer("integration")
@pytest.mark.proof("positive")
def test_docx_gets_a_definition_list():
    out = _render(LEDGER, to="native")
    assert "DefinitionList" in out


@pytest.mark.layer("integration")
@pytest.mark.proof("positive")
def test_every_grid_column_keeps_its_floor_after_normalising():
    # Mean cell lengths 1 / 2 / 59: a plain max-then-normalise leaves the two
    # short columns near 0.10. Every final width must hold the 0.12 floor.
    long = "x" * 59
    md = f"# Ch\n\n| A | B | C |\n|---|---|---|\n| a | bb | {long} |\n"
    out = _render(md, to="native")
    widths = [float(w) for w in re.findall(r"ColWidth ([0-9.eE+-]+)", out)]
    assert len(widths) == 3
    assert abs(sum(widths) - 1.0) < 1e-6
    assert all(w >= 0.12 - 1e-9 for w in widths), widths


@pytest.mark.layer("integration")
@pytest.mark.proof("positive")
def test_a_grid_too_wide_for_the_floor_shares_the_measure_equally():
    # Nine columns at 0.12 overfill the measure, so every column takes 1/9.
    head = "|" + "|".join(f" c{i} " for i in range(9)) + "|\n"
    rule = "|" + "|".join("---" for _ in range(9)) + "|\n"
    row = "|" + "|".join(" " + "x" * (i + 1) + " " for i in range(9)) + "|\n"
    out = _render("# Ch\n\n" + head + rule + row, to="native")
    widths = [float(w) for w in re.findall(r"ColWidth ([0-9.eE+-]+)", out)]
    assert len(widths) == 9
    assert all(abs(w - 1 / 9) < 1e-9 for w in widths), widths
