"""The example gallery is real: every book under examples/ is a valid press
book (its config passes the same typed model a build does), and the set
genuinely varies the design surfaces, so the gallery proves "same pipeline,
only the config differs" rather than asserting it.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from press import bookmodel, yamlio

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _example_dirs() -> list[Path]:
    if not EXAMPLES.is_dir():
        return []
    return sorted(d for d in EXAMPLES.iterdir()
                  if (d / "config" / "metadata.yaml").is_file())


def _metadata(example: Path) -> dict:
    return yamlio.load(example / "config" / "metadata.yaml")


@pytest.mark.layer("unit")
@pytest.mark.parametrize("example", _example_dirs(), ids=lambda d: d.name)
def test_example_is_a_valid_book(example):
    # bookmodel.load raises SystemExit listing every defect; a clean load is
    # the same validity a real build demands.
    book = bookmodel.load(example, _metadata(example))
    assert book.title and book.authors and book.slug == example.name


@pytest.mark.layer("unit")
def test_gallery_has_several_examples():
    assert len(_example_dirs()) >= 4, "the gallery should show several books"


@pytest.mark.layer("unit")
def test_examples_vary_the_design_surfaces():
    examples = _example_dirs()
    profiles = set()
    has_aesthetic = has_front_matter = has_web_override = has_index = False
    for example in examples:
        meta = _metadata(example)
        profiles.add((meta.get("print") or {}).get("profile", "house-6x9"))
        has_aesthetic |= (example / "config" / "aesthetic.yaml").is_file()
        has_front_matter |= (example / "config" / "front-matter.yaml").is_file()
        has_web_override |= (example / "assets" / "web" / "extra.css").is_file() or \
            (example / "assets" / "web" / "reader.css").is_file()
        has_index |= (example / "config" / "index-terms.yaml").is_file()
    # The whole point of the gallery: the surfaces actually differ across it.
    assert len(profiles) >= 2, f"examples should span >1 trim/profile, got {profiles}"
    assert has_aesthetic, "no example customizes the aesthetic"
    assert has_front_matter, "no example customizes front matter"
    assert has_web_override, "no example overrides the web reader stylesheet"
    assert has_index, "no example exercises the subject index"


@pytest.mark.layer("unit")
def test_example_slugs_are_unique():
    slugs = [_metadata(e).get("slug") for e in _example_dirs()]
    assert len(slugs) == len(set(slugs)), "example slugs collide"


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("pandoc") is None,
                    reason="requires capability: pandoc")
@pytest.mark.parametrize("example", _example_dirs(), ids=lambda d: d.name)
def test_example_passes_editorial_law(example):
    # `press check` runs the source checks, style audit, and jargon lint --
    # the same editorial law every real book faces. Each gallery book must
    # pass it, or the gallery ships a book the press would reject.
    result = subprocess.run(
        [sys.executable, "-m", "press", "check"],
        cwd=example, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
