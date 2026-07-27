"""`press check` refuses a malformed figure-placement vocabulary before any
render. The grammar is relative and parity-aware by law; a manuscript that
breaks it must turn the source check red with a located diagnostic, which is
the negative fixture this checker owes.
"""

from __future__ import annotations

import pytest

from tests import factories
from press import booklib, check_source


def _book(tmp_path, chapter_body: str):
    return factories.minimal().with_chapter("01-figs.md", chapter_body).build(tmp_path)


@pytest.mark.layer("integration")
@pytest.mark.proof("positive")
def test_a_clean_placement_vocabulary_passes(tmp_path):
    handle = _book(
        tmp_path,
        "# Figures\n\nProse that is long enough to be a real paragraph here.\n\n"
        "![The press](assets/fig/press.jpg){#fig:press .figure "
        "width=half-measure place=wrap-outer outset=1em}\n",
    )
    with handle.use():
        assert check_source._figure_failures(booklib.root(), set(booklib.chapter_files())) == []


@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_an_absolute_width_on_an_inflow_figure_is_refused(tmp_path):
    handle = _book(
        tmp_path,
        "# Figures\n\nProse that is long enough to be a real paragraph here.\n\n"
        "![The press](assets/fig/press.jpg){.figure place=inline width=2.4in}\n",
    )
    with handle.use():
        problems = check_source._figure_failures(booklib.root(), set(booklib.chapter_files()))
        assert problems and "absolute" in problems[0]
        # And the whole source check turns red, not just this helper.
        assert check_source.main() == 1


@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_left_right_placement_is_refused_for_parity(tmp_path):
    handle = _book(
        tmp_path,
        "# Figures\n\nProse that is long enough to be a real paragraph here.\n\n"
        "![The press](assets/fig/press.jpg){.figure place=right}\n",
    )
    with handle.use():
        problems = check_source._figure_failures(booklib.root(), set(booklib.chapter_files()))
        assert problems and "parity-aware" in problems[0]
