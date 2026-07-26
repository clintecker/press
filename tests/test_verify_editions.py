"""Cross-edition content agreement (INV-format-agreement).

The single-witness check proves one longest line survives per document; a
format could drop every other line and still pass. verify_editions_agree
holds the FULL per-chapter witness set against every edition at once, so a
format that silently loses a chapter disagrees with the ones that kept it.
These prove the pure agreement logic and, crucially, that it stays robust to
the two extraction artifacts that would otherwise raise a false alarm: a
PDF's per-page running furniture injected mid-line, and a DOCX's
paragraph-seam word-glue. All toolchain-free -- synthetic edition text.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from press import verify_formats

_DETERMINISTIC = settings(derandomize=True, deadline=None, max_examples=200)

# Two chapters with distinctive witness lines; long enough to yield several
# sliding fragments.
_WITNESSES = {
    "01-one.md": (
        "the first chapter keeps a small press honest and speaks of the "
        "composing stick and the imposing stone in plain unhurried words"
    ),
    "02-two.md": (
        "the second chapter follows the devil to the hell box where every "
        "lied-about page waits to be caught again before anything real is read"
    ),
}


def _all_present() -> dict[str, str]:
    body = " ".join(_WITNESSES.values())
    return {
        "HTML": f"the title front matter {body} back matter",
        "EPUB": f"cover {body} colophon",
    }


@pytest.mark.invariant("INV-format-agreement")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_editions_that_carry_every_chapter_agree():
    # A clean return (no SystemExit) is agreement.
    assert verify_formats.verify_editions_agree(_all_present(), _WITNESSES) is None


@pytest.mark.invariant("INV-format-agreement")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_empty_witness_set_is_a_no_op():
    # require_witnesses already refuses a witnessless book; agreement proves
    # nothing here and must not raise on an empty set.
    assert verify_formats.verify_editions_agree({"HTML": "anything at all"}, {}) is None


@pytest.mark.invariant("INV-format-agreement")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_an_edition_that_drops_a_chapter_is_named_and_refused():
    editions = _all_present()
    editions["EPUB"] = _WITNESSES["01-one.md"] + " and then nothing else survives"
    with pytest.raises(SystemExit) as excinfo:
        verify_formats.verify_editions_agree(editions, _WITNESSES)
    message = str(excinfo.value)
    assert "EPUB" in message
    assert "02-two.md" in message
    assert "01-one.md" not in message  # the chapter it kept is not blamed


@pytest.mark.invariant("INV-format-agreement")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_pdf_page_furniture_injected_mid_line_still_agrees():
    """A witness line that straddles a page carries the running head and foot
    (page number, book title, chapter title) spliced into its middle. A
    distinctive fragment on either side of the seam still matches, so the
    chapter is not read as dropped."""

    editions = _all_present()
    one = _WITNESSES["01-one.md"]
    seam = one.replace(
        "and speaks of",
        "and speaks 12 make ready chapter one of",  # furniture spliced mid-line
    )
    editions["PDF"] = f"opening {seam} {_WITNESSES['02-two.md']} closing"
    assert verify_formats.verify_editions_agree(editions, _WITNESSES) is None


@pytest.mark.invariant("INV-format-agreement")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_docx_paragraph_seam_word_glue_still_agrees():
    """A DOCX can glue a witness's first word to the previous paragraph's
    last word when their runs carry no separating space ("feast.the first").
    The corrupted edge word costs only the boundary fragments; an interior
    fragment still matches."""

    editions = _all_present()
    glued = "printersfeast." + _WITNESSES["01-one.md"]  # first word glued at the seam
    editions["docx"] = f"{glued} {_WITNESSES['02-two.md']}"
    assert verify_formats.verify_editions_agree(editions, _WITNESSES) is None


@pytest.mark.invariant("INV-format-agreement")
@pytest.mark.layer("property")
@pytest.mark.proof("positive")
@_DETERMINISTIC
@given(pad=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", max_size=60))
def test_a_witness_verbatim_in_an_edition_always_agrees(pad):
    """However an edition pads around the manuscript, a chapter whose witness
    line is present verbatim always registers as present -- the fragment
    match never invents a false absence."""

    editions = {"HTML": f"{pad} {' '.join(_WITNESSES.values())} {pad}"}
    assert verify_formats.verify_editions_agree(editions, _WITNESSES) is None


@pytest.mark.invariant("INV-format-agreement")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_fragments_are_distinctive_multi_word_windows():
    """The fragments are multi-word windows (no single common word stands in
    for a chapter), and a short witness is its own single fragment."""

    fragments = verify_formats._witness_fragments(_WITNESSES["01-one.md"])
    assert fragments
    assert all(len(f.split()) >= 2 for f in fragments)
    short = verify_formats._witness_fragments("only four short words")
    assert short == ["only four short words"]
    assert verify_formats._witness_fragments("") == []
