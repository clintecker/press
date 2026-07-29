"""The scene-break ornament: a Markdown thematic break becomes a centered
asterism (``scene-break: asterism``) or the staggered three-row fairy-dust
array (``scene-break: fairy-dust``) when the book's aesthetic asks for it, and
is left an unchanged horizontal rule otherwise. The unit test covers the
aesthetic reading; the filter tests run pandoc directly (no LaTeX) to prove the
emitted markup in each format.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

FILTER = (
    Path(__file__).resolve().parent.parent / "src" / "press" / "data" / "lua" / "scene-break.lua"
)

_needs_pandoc = pytest.mark.skipif(
    shutil.which("pandoc") is None, reason="requires capability: pandoc"
)

# A chapter with one thematic break -- Alice's shrink/grow marker.
_MD = "# A chapter\n\nBefore the shift.\n\n---\n\nAfter the shift.\n"


@pytest.mark.layer("unit")
def test_scene_break_ornament_reads_the_aesthetic(monkeypatch):
    from press import aesthetic, build

    monkeypatch.setattr(aesthetic, "effective", lambda: {"scene-break": "asterism"})
    assert build._scene_break_ornament() == "asterism"
    monkeypatch.setattr(aesthetic, "effective", lambda: {"scene-break": "fairy-dust"})
    assert build._scene_break_ornament() == "fairy-dust"
    # The default, and any typo, is the unchanged rule -- a bad value degrades,
    # it does not break a build.
    monkeypatch.setattr(aesthetic, "effective", lambda: {})
    assert build._scene_break_ornament() == "rule"
    monkeypatch.setattr(aesthetic, "effective", lambda: {"scene-break": "fleuron"})
    assert build._scene_break_ornament() == "rule"


def _render(markdown: str, to: str = "latex", ornament: str | None = None) -> str:
    args = ["pandoc", "-f", "markdown", "-t", to, f"--lua-filter={FILTER}"]
    if ornament is not None:
        args += ["-M", f"scene-break-ornament={ornament}"]
    result = subprocess.run(args, input=markdown, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


@_needs_pandoc
@pytest.mark.layer("integration")
def test_asterism_replaces_the_rule_in_latex():
    out = _render(_MD, ornament="asterism")
    # a centered row of asterisks, and the bare rule is gone
    assert "\\quad" in out and "*" in out
    assert "\\rule" not in out


@_needs_pandoc
@pytest.mark.layer("integration")
def test_asterism_in_html():
    out = _render(_MD, to="html", ornament="asterism")
    assert 'class="asterism"' in out
    assert "<hr" not in out


@_needs_pandoc
@pytest.mark.layer("integration")
def test_fairy_dust_replaces_the_rule_in_latex():
    out = _render(_MD, ornament="fairy-dust")
    # the staggered-array macro, and the bare rule is gone
    assert "\\PressFairyDust" in out
    assert "\\rule" not in out


@_needs_pandoc
@pytest.mark.layer("integration")
def test_fairy_dust_in_html():
    out = _render(_MD, to="html", ornament="fairy-dust")
    # a three-row block (four / three / four asterisks), no rule
    assert 'class="fairy-dust"' in out
    assert out.count("<span>") == 3
    assert "<hr" not in out


@_needs_pandoc
@pytest.mark.layer("integration")
@pytest.mark.proof("negative")
def test_default_leaves_the_rule_unchanged():
    # No ornament metadata (the 'rule' default): the thematic break stays a
    # horizontal rule in both formats, exactly as before the filter existed.
    assert "\\rule" in _render(_MD)  # latex
    html = _render(_MD, to="html")
    assert "<hr" in html and 'class="asterism"' not in html
