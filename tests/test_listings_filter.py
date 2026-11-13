"""The listings Lua filter on the pandoc AST: an example caption, written
either as a bold ``**Example C.N. Title**`` paragraph directly before a code
block or as a ``caption=`` attribute on the fence, is attached to its block
and set as a caption in each edition: ``\\PressExampleCaption`` for LaTeX, a
``Div.example-caption`` for HTML and EPUB, the ``Caption`` paragraph style for
DOCX, and the paragraph as it was for plain text. A bold paragraph before
anything else is left alone, and a book with no captioned block renders
byte-for-byte as before. These run pandoc directly (no LaTeX).
"""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import pytest

from tests import lua_coverage

FILTER = Path(__file__).resolve().parent.parent / "src" / "press" / "data" / "lua" / "listings.lua"

pytestmark = lua_coverage.needs_pandoc


def _render(markdown: str, to: str = "latex", filtered: bool = True) -> str:
    args = ["pandoc", "-f", "markdown+smart", "-t", to, "--wrap=none"]
    if filtered:
        args.append(lua_coverage.filter_arg(FILTER))
    result = subprocess.run(args, input=markdown, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


IMPLICIT = (
    "# Ch\n\n**Example 2.4. Installing the toolchain on macOS**\n\n"
    "```text\n$ brew install pandoc poppler\n```\n"
)
EXPLICIT = (
    "# Ch\n\n```{.text #ex-first-run caption=\"Example 6.1. A first *run* of `press`\"}\n"
    "press check\n```\n"
)
NOT_BEFORE_CODE = "# Ch\n\n**Example 2.4. A bold paragraph**\n\nProse follows it.\n"
NO_FENCES = (
    "# Ch\n\n**Example 2.4. Bold but no code**\n\nSome *prose*, a `span`, and a list:\n\n"
    "- one\n- two\n\n**Not an example.**\n"
)


@pytest.mark.layer("integration")
def test_implicit_caption_in_latex():
    out = _render(IMPLICIT)
    caption = "\\PressExampleCaption{Example 2.4.}{Installing the toolchain on macOS}"
    assert caption in out
    # immediately before the block, and the bold paragraph is gone
    after = out.split(caption, 1)[1].lstrip()
    assert after.startswith("\\begin{"), after[:60]
    assert "\\textbf{Example" not in out


@pytest.mark.layer("integration")
def test_implicit_caption_in_html():
    out = _render(IMPLICIT, to="html")
    assert '<div class="example-caption">' in out
    assert (
        "<p><strong>Example 2.4.</strong> <em>Installing the toolchain on macOS</em></p>" in out
    )
    # the caption comes before the code, and only once
    assert out.index("example-caption") < out.index("<pre")
    assert out.count("Example 2.4.") == 1


@pytest.mark.layer("integration")
@pytest.mark.parametrize(
    ("label", "kind"),
    [("Example 3.", "chapterless"), ("Example A.2.", "appendix"), ("Example 12.10.", "two-digit")],
)
def test_every_number_form_is_a_caption(label, kind):
    md = f"**{label} Title**\n\n```\ncode\n```\n"
    assert f"\\PressExampleCaption{{{label}}}{{Title}}" in _render(md), kind


@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
@pytest.mark.parametrize(
    "bold",
    [
        "Example 6-1. A hyphenated number",  # not the house number form
        "Example 2.4.",  # a label with no title
        "Examples from the docs",
        "Example. A worked case",
        "See Example 2.4. Above",
    ],
)
def test_a_bold_paragraph_that_is_not_a_caption_is_left_alone(bold):
    md = f"**{bold}**\n\n```\ncode\n```\n"
    assert _render(md) == _render(md, filtered=False)


@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_a_caption_with_more_in_its_paragraph_is_left_alone():
    md = "**Example 2.4. Title** and then prose.\n\n```\ncode\n```\n"
    assert _render(md) == _render(md, filtered=False)


@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_a_bold_paragraph_not_followed_by_a_fence_is_untouched():
    for to in ("latex", "html"):
        assert _render(NOT_BEFORE_CODE, to=to) == _render(NOT_BEFORE_CODE, to=to, filtered=False)


@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
@pytest.mark.parametrize("to", ["latex", "html", "epub3", "plain", "markdown"])
def test_a_book_with_no_fences_is_byte_identical(to):
    if to == "epub3":
        # EPUB is a zip with a timestamped package; compare the AST instead.
        assert _render(NO_FENCES, to="native") == _render(NO_FENCES, to="native", filtered=False)
        return
    assert _render(NO_FENCES, to=to) == _render(NO_FENCES, to=to, filtered=False)


@pytest.mark.layer("integration")
def test_explicit_caption_in_latex_keeps_its_markup_and_anchor():
    out = _render(EXPLICIT)
    # the anchor rides in the macro's optional argument, so the header sets it
    # after the caption's keep, not before the space and the page break
    assert (
        "\\PressExampleCaption[ex-first-run]{Example 6.1.}{A first \\emph{run} of \\texttt{press}}"
    ) in out
    assert "\\phantomsection" not in out
    assert "caption=" not in out


@pytest.mark.layer("integration")
def test_explicit_caption_in_html_moves_the_id_to_the_caption():
    out = _render(EXPLICIT, to="html")
    assert '<div id="ex-first-run" class="example-caption">' in out
    assert "<strong>Example 6.1.</strong> <em>A first <em>run</em> of <code>press</code></em>" in out
    # the attribute is consumed, not passed through as data-caption, and the
    # id is not duplicated on the block
    assert "data-caption" not in out and out.count('id="ex-first-run"') == 1


@pytest.mark.layer("integration")
def test_explicit_caption_without_a_number_is_the_title_alone():
    md = '```{caption="A listing with no number"}\ncode\n```\n'
    assert "\\PressExampleCaption{}{A listing with no number}" in _render(md)
    assert "<strong>" not in _render(md, to="html")


@pytest.mark.layer("integration")
def test_an_explicit_caption_wins_over_a_bold_paragraph_before_it():
    # Both spellings on one block: the attribute is the caption, and the bold
    # paragraph, which would only repeat or contradict it, is dropped.
    md = '**Example 1.1. Bold**\n\n```{caption="Example 1.2. Attribute"}\ncode\n```\n'
    out = _render(md)
    assert out.count("\\PressExampleCaption") == 1
    assert "\\PressExampleCaption{Example 1.2.}{Attribute}" in out
    assert "Example 1.1" not in out
    html = _render(md, to="html")
    assert "Example 1.1" not in html and html.count("example-caption") == 1


@pytest.mark.layer("integration")
def test_an_implicit_caption_takes_the_fences_id():
    md = "**Example 2.4. Title**\n\n```{#ex-toolchain}\ncode\n```\n"
    assert "\\PressExampleCaption[ex-toolchain]{Example 2.4.}{Title}" in _render(md)
    html = _render(md, to="html")
    assert '<div id="ex-toolchain" class="example-caption">' in html
    assert html.count('id="ex-toolchain"') == 1


@pytest.mark.layer("integration")
def test_a_caption_wrapped_in_the_source_is_recognised():
    # An author's editor may wrap the bold line anywhere, including between
    # the number and the title: pandoc reads that line end as a SoftBreak.
    for md in (
        "**Example 2.4.\nInstalling the toolchain**\n\n```\ncode\n```\n",
        "**Example\n2.4. Installing the toolchain**\n\n```\ncode\n```\n",
    ):
        assert "\\PressExampleCaption{Example 2.4.}{Installing the toolchain}" in _render(md)


@pytest.mark.layer("integration")
def test_a_caption_inside_a_list_or_div_is_attached():
    md = (
        "::: note\n**Example 4.1. In a div**\n\n```\ncode\n```\n:::\n\n"
        "1.  Step one.\n\n    **Example 4.2. In a list**\n\n    ```\n    code\n    ```\n"
    )
    out = _render(md)
    assert "\\PressExampleCaption{Example 4.1.}{In a div}" in out
    assert "\\PressExampleCaption{Example 4.2.}{In a list}" in out


@pytest.mark.layer("integration")
def test_epub_chapter_has_caption(tmp_path):
    epub = tmp_path / "book.epub"
    result = subprocess.run(
        [
            "pandoc",
            "-f",
            "markdown",
            "-t",
            "epub3",
            "-M",
            "title=T",
            lua_coverage.filter_arg(FILTER),
            "-o",
            str(epub),
        ],
        input=IMPLICIT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    with zipfile.ZipFile(epub) as z:
        text = "".join(z.read(n).decode() for n in z.namelist() if n.endswith(".xhtml"))
    assert 'class="example-caption"' in text
    assert "<strong>Example 2.4.</strong>" in text


@pytest.mark.layer("integration")
def test_docx_caption_takes_the_caption_style(tmp_path):
    docx = tmp_path / "book.docx"
    result = subprocess.run(
        ["pandoc", "-f", "markdown", "-t", "docx", lua_coverage.filter_arg(FILTER), "-o", str(docx)],
        input=IMPLICIT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    with zipfile.ZipFile(docx) as z:
        body = z.read("word/document.xml").decode()
    assert '<w:pStyle w:val="Caption" />' in body or '<w:pStyle w:val="Caption"/>' in body
    assert body.index("Caption") < body.index("brew install")


@pytest.mark.layer("integration")
@pytest.mark.parametrize("to", ["plain", "markdown"])
def test_plain_text_keeps_the_paragraph_as_written(to):
    # The implicit caption already reads as a caption in plain text; the
    # filter leaves it exactly as written.
    assert _render(IMPLICIT, to=to) == _render(IMPLICIT, to=to, filtered=False)
    # The explicit one has no paragraph to keep, so plain text gets one.
    out = _render(EXPLICIT, to="plain")
    assert "Example 6.1. A first run of press" in out
    assert out.index("Example 6.1.") < out.index("press check")
