"""The single-ink syntax theme the print profile highlights with (#273).

skylighting's default pygments style colours a fenced block tagged
``yaml``/``python``/``sh``, and ``verify_pdf.verify_black_ink`` refuses a
coloured print interior, so ``print.yaml`` sets ``highlight-style`` to the
packaged ``press-mono.theme``. These tests hold the theme to its promise:
every colour it names is a grey, pandoc accepts it as a highlight style, the
LaTeX it emits for a tagged fence carries no coloured ink, and the print
defaults resolve to the installed copy. The default style is rendered beside
it as the negative: the same fence under pygments puts colour on the page,
which is what the grey check must be able to tell apart. The real build and
``verify_black_ink`` run in the coverwrap integration runner, whose factory
book carries a tagged fence for this reason.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from press import booklib, build
from tests import lua_coverage

THEME = booklib.DATA / "press-mono.theme"
PRINT_DEFAULTS = booklib.DATA / "defaults" / "print.yaml"

_FENCES = (
    "# Listing\n\n"
    "```python\n# a comment\ndef f(x):\n    return 'string' + str(1)\n```\n\n"
    "```yaml\nkey: value\nlist:\n  - 1\n```\n\n"
    "```sh\nexport NAME=value && press all\n```\n"
)
_RGB = re.compile(r"\\textcolor\[rgb\]\{([0-9.]+),([0-9.]+),([0-9.]+)\}")


def _is_grey(hex_colour: str) -> bool:
    body = hex_colour.lstrip("#")
    return len(body) == 6 and body[0:2] == body[2:4] == body[4:6]


def _latex(style: str | None) -> str:
    args = ["pandoc", "-f", "markdown", "-t", "latex", "--standalone"]
    if style is not None:
        args.append(f"--highlight-style={style}")
    result = subprocess.run(args, input=_FENCES, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.mark.layer("unit")
def test_theme_is_json_naming_only_greys():
    theme = json.loads(THEME.read_text(encoding="utf-8"))
    styles = theme["text-styles"]
    assert {"Keyword", "Comment", "String", "DataType"} <= set(styles)
    colours = [theme["text-color"], theme["background-color"], theme["line-number-color"]]
    colours += [
        style[key] for style in styles.values() for key in ("text-color", "background-color")
    ]
    named = [colour for colour in colours if colour is not None]
    assert named, "the theme should grey at least one token, not merely drop colour"
    assert all(_is_grey(colour) for colour in named), named
    # A visible cue survives the loss of colour: weight or slant on the
    # tokens a reader scans for.
    assert styles["Keyword"]["bold"] and styles["Comment"]["italic"]


@pytest.mark.layer("unit")
def test_print_defaults_highlight_with_the_packaged_theme():
    import yaml

    defaults = yaml.safe_load(PRINT_DEFAULTS.read_text(encoding="utf-8"))
    assert defaults["highlight-style"] == "@press/press-mono.theme"
    resolved = build._resolve_paths({"highlight-style": defaults["highlight-style"]})
    assert Path(resolved["highlight-style"]) == THEME
    assert THEME.is_file()


@pytest.mark.layer("unit")
@lua_coverage.needs_pandoc
def test_pandoc_accepts_the_theme_and_emits_grey_ink_only():
    latex = _latex(str(THEME))
    assert r"\begin{Highlighting}" in latex, "tagged fences must still highlight"
    triples = _RGB.findall(latex)
    assert triples, "the theme greys tokens, so some textcolor must be emitted"
    assert all(r == g == b for r, g, b in triples), triples
    assert r"\textbf" in latex and r"\textit" in latex


@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
@lua_coverage.needs_pandoc
def test_the_default_style_puts_colour_on_the_page():
    # The condition #273 reports: without the theme the same fences carry
    # coloured ink, which verify_black_ink refuses in a print interior.
    triples = _RGB.findall(_latex(None))
    assert any(not (r == g == b) for r, g, b in triples), triples


@pytest.mark.layer("unit")
@lua_coverage.needs_pandoc
def test_the_theme_is_accepted_through_a_defaults_file(tmp_path):
    # The build hands the theme to pandoc through the resolved defaults
    # file, not the command line; the key must be one this pandoc reads.
    defaults = tmp_path / "d.yaml"
    defaults.write_text(
        f"from: markdown\nto: latex\nstandalone: true\nhighlight-style: {THEME}\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["pandoc", "-d", str(defaults)], input=_FENCES, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "WARNING" not in result.stderr, result.stderr
    assert all(r == g == b for r, g, b in _RGB.findall(result.stdout))
