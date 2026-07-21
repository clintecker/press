"""The CLI branding: color only when a terminal wants it, and a banner that
names the version. Piped output must stay plain so scripts see no ANSI.
"""

from __future__ import annotations

import pytest

from press import brand


@pytest.mark.layer("unit")
def test_no_color_env_wins(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("FORCE_COLOR", "1")   # NO_COLOR must still win
    assert brand.use_color() is False
    assert brand.paint("x", brand.VERMILION) == "x"


@pytest.mark.layer("unit")
def test_force_color_paints(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert brand.use_color() is True
    painted = brand.paint("x", brand.VERMILION)
    assert painted.startswith("\033[38;5;203m") and painted.endswith("\033[0m")


@pytest.mark.layer("unit")
def test_banner_names_version_and_tagline_without_ansi_when_plain(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    out = brand.banner("9.9.9")
    assert "v9.9.9 · MIT · run press all" in out
    assert "markdown → a finished book" in out
    assert "\033[" not in out   # no ANSI when color is off


@pytest.mark.layer("unit")
def test_phase_and_ready_lines(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    line = brand.phase("check", "style, source, jargon")
    assert brand.PILCROW in line and "check" in line and "✓ style, source, jargon" in line
    assert "press. your book is ready → dist/" in brand.ready("dist/")
