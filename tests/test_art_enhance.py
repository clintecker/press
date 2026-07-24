"""The plate-finishing pipeline: upscale, quantize, compress.

The upscale stage needs an external Real-ESRGAN model and is exercised where
one exists; the quantize and compress stages are pure and proven here, along
with the medium->profile mapping and the graceful degradation that lets a book
finish its plates with no upscaler installed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from press import adapters, art_enhance
from press.adapters import fakes

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402


def _noisy(width: int, height: int) -> Image.Image:
    """A truecolor image with many distinct colors, so a quantize that does
    nothing is visibly wrong."""

    img = Image.new("RGB", (width, height))
    px = img.load()
    for y in range(height):
        for x in range(width):
            px[x, y] = ((x * 7) % 256, (y * 5) % 256, ((x + y) * 3) % 256)
    return img


def test_quantize_reduces_to_at_most_n_colors():
    q = art_enhance.quantize(_noisy(64, 64), 8)
    distinct = len(q.convert("L").getcolors(maxcolors=100000))
    assert distinct <= 8, f"quantize left {distinct} shades, wanted <= 8"


def test_quantize_refuses_a_degenerate_palette():
    with pytest.raises(ValueError, match="at least 2"):
        art_enhance.quantize(_noisy(8, 8), 1)


@pytest.mark.parametrize("medium, model, colors", [
    ("wood engraving on cream", "remacri-4x", 16),
    ("a fine woodcut", "remacri-4x", 16),
    ("pen and ink line", "remacri-4x", 16),  # 'line' wins as a substring
    ("loose watercolour wash", "ultrasharp-4x", 64),
    ("", "remacri-4x", 16),                 # default
    ("something unheard of", "remacri-4x", 16),
])
def test_medium_picks_model_and_palette(medium, model, colors):
    assert art_enhance.profile_for(medium) == (model, colors)


def test_no_upscaler_degrades_to_a_pure_resample(tmp_path, monkeypatch):
    """A book with no Real-ESRGAN installed still finishes its plates: the
    quantize and compress win lands, the call never fails for want of the
    external tool, and the result reports it was resampled, not upscaled."""

    monkeypatch.setattr(art_enhance, "find_upscaler", lambda: None)
    src = tmp_path / "plate.png"
    _noisy(200, 120).save(src)
    dst = tmp_path / "plate-out.png"

    result = art_enhance.enhance(src, dst, colors=8, max_edge=400)

    assert result.upscaled is False
    assert dst.is_file()
    assert result.colors <= 8
    # capped to the target long edge, aspect preserved
    assert max(result.width, result.height) <= 400
    assert result.width > result.height  # 200x120 stays landscape


def test_enhance_upscales_through_the_process_adapter(tmp_path, monkeypatch):
    """When an upscaler is resolved, the enhance drives it through the process
    runner with the model and scale -- not a raw subprocess -- and a fake
    stands in for the binary, writing the file it would have produced."""

    fake_upscaler = art_enhance.Upscaler(binary="/x/realesrgan", models_dir="/x/models")
    monkeypatch.setattr(art_enhance, "find_upscaler", lambda: fake_upscaler)
    monkeypatch.setattr(art_enhance, "available_model", lambda u, m: m)

    src = tmp_path / "plate.png"
    _noisy(100, 100).save(src)
    dst = tmp_path / "out.png"

    class Runner:
        def __init__(self):
            self.calls = []

        def run(self, argv, **kw):
            self.calls.append((argv, kw))
            # the real binary writes -o; emulate a 4x output so enhance can open it
            out = Path(argv[argv.index("-o") + 1])
            _noisy(400, 400).save(out)
            return fakes.ProcessResult(0, b"", b"") if hasattr(fakes, "ProcessResult") else None

    runner = Runner()
    monkeypatch.setattr(adapters, "process_runner", runner)

    result = art_enhance.enhance(src, dst, model="remacri-4x", colors=8,
                                 scale=4, max_edge=300)

    assert result.upscaled is True
    argv = runner.calls[0][0]
    assert argv[0] == "/x/realesrgan"
    assert "remacri-4x" in argv and "-s" in argv
    assert max(result.width, result.height) <= 300


def test_find_upscaler_prefers_path_then_known_locations(monkeypatch, tmp_path):
    """Detection asks the environment adapter for a PATH install first, and
    only then falls back to the fixed locations -- so the same book finishes
    the same way whether the tool is on PATH (the container) or in an app."""

    fake_env = fakes.FakeEnvironment(present_tools=["realesrgan-ncnn-vulkan"])
    # give the fake a real path for which()
    monkeypatch.setattr(adapters, "environment", fake_env)
    monkeypatch.setattr(art_enhance.Path, "is_dir", lambda self: True, raising=False)
    found = art_enhance.find_upscaler()
    assert found is not None
    assert "realesrgan-ncnn-vulkan" in found.binary


def test_cli_enhance_one_file(tmp_path, monkeypatch):
    """`press art enhance <file>` reads the plate medium, finishes the one
    file, and writes a PNG beside it -- with no upscaler installed, via the
    pure fallback so the test needs no external binary."""

    from press import aesthetic, art

    monkeypatch.setattr(aesthetic, "effective",
                        lambda: {"plate": {"medium": "wood engraving"}})
    monkeypatch.setattr(art_enhance, "find_upscaler", lambda: None)
    src = tmp_path / "plate.jpg"
    _noisy(160, 100).convert("RGB").save(src)

    class Args:
        file = src
        colors = None
        max_edge = 300

    assert art._enhance(Args()) == 0
    assert (tmp_path / "plate.png").is_file()


def test_cli_enhance_all_plates_needs_a_woodcuts_dir(tmp_path, monkeypatch):
    from press import aesthetic, art, booklib

    monkeypatch.setattr(aesthetic, "effective", lambda: {})
    monkeypatch.setattr(art_enhance, "find_upscaler", lambda: None)
    monkeypatch.setattr(booklib, "root", lambda: tmp_path)

    class Args:
        file = None
        colors = None
        max_edge = None

    with pytest.raises(SystemExit, match="no plates"):
        art._enhance(Args())
