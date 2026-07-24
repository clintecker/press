"""`press add` end to end: the command that creates a book part and owns
the placement prefix instead of handing the author a `printf > file`
that clobbers and breaks on apostrophes (#205).

The book-backed tests run the CLI against a real scaffolded book (the
fixture sets BOOK_ROOT), so a test and the shipped command exercise the
same booklib machinery. The load-bearing safety property -- the command
never overwrites an existing file -- is asserted the honest way, by
comparing the target's bytes before and after a colliding call.
"""

from __future__ import annotations

import pytest

from press import add

integration = pytest.mark.layer("integration")
unit = pytest.mark.layer("unit")


# ---- slugify (normalizer: folding and idempotence) -------------------

@unit
@pytest.mark.parametrize("raw, expected", [
    ("about-the-author", "about-the-author"),
    ("The Long Winter's End", "the-long-winter-s-end"),
    ("  Also, By  ", "also-by"),
    ("A Chapter -- Two", "a-chapter-two"),
])
def test_slugify_folds_to_a_filename_safe_slug(raw, expected):
    assert add.slugify(raw) == expected


@unit
@pytest.mark.parametrize("raw", [
    "The Long Winter's End", "about-the-author", "Also, By!!",
])
def test_slugify_is_idempotent(raw):
    once = add.slugify(raw)
    assert add.slugify(once) == once


@unit
@pytest.mark.parametrize("raw", ["", "   ", "!!!", "---"])
def test_slugify_refuses_a_name_with_no_letter_or_digit(raw):
    with pytest.raises(SystemExit):
        add.slugify(raw)


# ---- heading ---------------------------------------------------------

@unit
def test_heading_keeps_a_human_title_verbatim():
    assert add.heading("The Long Winter's End") == "The Long Winter's End"


@unit
def test_heading_sentence_cases_a_bare_slug():
    assert add.heading("about-the-author") == "About the author"


# ---- placement: the prefixes the command owns ------------------------

@integration
def test_appendices_take_descending_back_matter_letters(scaffolded_book):
    root = scaffolded_book
    assert add.main(["appendix", "about-the-author"]) == 0
    assert add.main(["appendix", "also-by"]) == 0
    assert add.main(["appendix", "glossary"]) == 0
    names = sorted(p.name for p in (root / "book" / "appendices").glob("*.md"))
    assert names == [
        "x-glossary.md", "y-also-by.md", "z-about-the-author.md",
    ]


@integration
def test_front_appendix_takes_an_ascending_letter(scaffolded_book):
    root = scaffolded_book
    assert add.main(["appendix", "preamble", "--front"]) == 0
    assert (root / "book" / "appendices" / "a-preamble.md").is_file()


@integration
def test_front_chapter_is_prefixed_zero_zero_and_unnumbered(scaffolded_book):
    root = scaffolded_book
    assert add.main(["chapter", "foreword", "--front"]) == 0
    page = root / "book" / "chapters" / "00-foreword.md"
    assert page.is_file()
    assert page.read_text(encoding="utf-8").startswith("# Foreword {.unnumbered}")


@integration
def test_plain_chapter_takes_the_next_numbered_slot(scaffolded_book):
    # The scaffold ships 00-preface.md, so the first real chapter is 01.
    root = scaffolded_book
    assert add.main(["chapter", "The Long Winter's End"]) == 0
    first = root / "book" / "chapters" / "01-the-long-winter-s-end.md"
    assert first.is_file()
    # An apostrophe in the title never reaches the shell or the filename,
    # and it is preserved verbatim in the heading.
    assert first.read_text(encoding="utf-8").startswith(
        "# The Long Winter's End\n")
    assert add.main(["chapter", "After The Thaw"]) == 0
    assert (root / "book" / "chapters" / "02-after-the-thaw.md").is_file()


@integration
def test_the_stub_is_valid_non_empty_markdown(scaffolded_book):
    root = scaffolded_book
    assert add.main(["appendix", "glossary"]) == 0
    body = (root / "book" / "appendices" / "z-glossary.md").read_text(
        encoding="utf-8")
    assert body.startswith("# Glossary\n")
    assert body.strip().count("\n") >= 1  # heading plus a placeholder line


# ---- the known-bad: it must refuse to clobber ------------------------

@integration
def test_add_refuses_to_overwrite_an_existing_file(scaffolded_book, capsys):
    """The whole reason the command exists: unlike `printf > file`, a
    second call that would land on an existing page is refused with a
    non-zero exit and the file is left byte-for-byte intact."""

    root = scaffolded_book
    preface = root / "book" / "chapters" / "00-preface.md"
    original = preface.read_bytes()  # the scaffold's own preface

    code = add.main(["chapter", "preface", "--front"])

    assert code != 0
    assert preface.read_bytes() == original  # not one byte changed
    assert "already exists" in capsys.readouterr().out


# ---- usage errors ----------------------------------------------------

@integration
@pytest.mark.parametrize("argv", [
    [],
    ["chapter"],
    ["nonsense", "x"],
    ["chapter", "one", "--bogus"],
])
def test_bad_invocation_is_a_usage_error(scaffolded_book, argv):
    assert add.main(argv) == 2
