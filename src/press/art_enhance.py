"""Finish commissioned art for print and web: upscale, quantize, compress.

A generated plate is a modest raster; a book wants it large and crisp for the
print interior and small and clean for the reader. This finishes one in three
stages, each matched to the art's own style:

1. **Upscale** through a Real-ESRGAN model chosen for the medium -- a
   line/illustration model (remacri) for an engraving, not a photo model that
   would invent smooth gradients an engraving does not have. The upscaler is
   an external tool (Upscayl's ``upscayl-bin`` or a standalone
   ``realesrgan-ncnn-vulkan``); it is detected, never bundled, and its absence
   downgrades to a plain resample rather than failing.
2. **Quantize** to a small palette. An engraving is ink on paper -- a handful
   of grays, not sixteen million -- so collapsing it to N grays is visually
   lossless and turns a 5 MB truecolor PNG into a ~1 MB one. This is what lets
   a plate ship as a lossless PNG instead of a lossy JPEG (retiring the scar in
   CLAUDE.md that PNG "barely compresses engraving grain": it does once the
   grain is quantized).
3. **Compress** losslessly (PIL's optimizer, and pngquant/oxipng when present).

Stages 2 and 3 are pure and always available; only stage 1 needs the external
model. The medium in ``config/aesthetic.yaml`` picks the model and the palette,
so an engraving book and a watercolor book each finish in their own grain.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import adapters

# The external upscaler, by the names it ships under, plus the fixed locations
# it lives at outside PATH: the toolchain image installs it to /usr/local/bin,
# and a macOS author most often has Upscayl.app. Detection tries PATH first
# (through the environment adapter) and then these, so a book finishes the
# same way in the container and on a laptop.
_UPSCALER_NAMES = ("realesrgan-ncnn-vulkan", "upscayl-bin")
_UPSCALER_PATHS = (
    "/usr/local/bin/realesrgan-ncnn-vulkan",
    "/Applications/Upscayl.app/Contents/Resources/bin/upscayl-bin",
)
# Where a detected binary's models live, relative to it or as a sibling dir.
_MODEL_DIRS = (
    "/usr/local/share/realesrgan/models",
    "/Applications/Upscayl.app/Contents/Resources/models",
)

# medium (a substring of the aesthetic's plate/cover medium) -> (model, colors).
# An engraving is line art in few grays; a wash or photo keeps more of them.
_MEDIUM_PROFILE = {
    "engrav": ("remacri-4x", 16),
    "woodcut": ("remacri-4x", 16),
    "wood engraving": ("remacri-4x", 16),
    "line": ("remacri-4x", 16),
    "pen": ("remacri-4x", 24),
    "etch": ("remacri-4x", 24),
    "wash": ("ultrasharp-4x", 64),
    "watercolour": ("ultrasharp-4x", 64),
    "watercolor": ("ultrasharp-4x", 64),
}
_DEFAULT_PROFILE = ("remacri-4x", 16)


@dataclass(frozen=True)
class Upscaler:
    """A resolved external upscaler and the directory holding its models."""

    binary: str
    models_dir: str


def find_upscaler() -> Upscaler | None:
    """Resolve an installed Real-ESRGAN upscaler, or None if none is present.

    PATH first (through the environment adapter, so the boundary stays typed),
    then the fixed install locations the toolchain image and Upscayl.app use.
    """

    binary = None
    for name in _UPSCALER_NAMES:
        found = adapters.environment.which(name)
        if found:
            binary = found
            break
    if binary is None:
        for candidate in _UPSCALER_PATHS:
            if Path(candidate).is_file():
                binary = candidate
                break
    if binary is None:
        return None
    for models in _MODEL_DIRS:
        if Path(models).is_dir():
            return Upscaler(binary=binary, models_dir=models)
    # A models dir beside the binary (the layout of a hand-installed release).
    sibling = Path(binary).resolve().parent.parent / "models"
    return Upscaler(binary=binary, models_dir=str(sibling))


def profile_for(medium: str) -> tuple[str, int]:
    """The (upscale model, palette size) a medium description resolves to."""

    lowered = (medium or "").lower()
    for needle, profile in _MEDIUM_PROFILE.items():
        if needle in lowered:
            return profile
    return _DEFAULT_PROFILE


def available_model(upscaler: Upscaler, preferred: str) -> str:
    """The preferred model if the install has it, else a sensible fallback so
    an upscale still happens rather than failing on a missing model file."""

    have = {p.stem for p in Path(upscaler.models_dir).glob("*.param")}
    if preferred in have:
        return preferred
    for fallback in ("remacri-4x", "ultrasharp-4x", "realesrgan-x4plus",
                     "upscayl-standard-4x"):
        if fallback in have:
            return fallback
    return preferred  # let the tool report the missing model plainly


def upscale(src: Path, dst: Path, *, model: str, scale: int,
            upscaler: Upscaler) -> None:
    """Upscale src to dst with the given model, through the process adapter."""

    adapters.process_runner.run(
        [upscaler.binary, "-i", str(src), "-o", str(dst),
         "-n", model, "-m", upscaler.models_dir, "-s", str(scale)],
        check=True, capture=True, timeout=600,
    )


def quantize(image, colors: int, *, grayscale: bool = True):
    """Collapse an image to a small palette of ``colors`` shades.

    A single-ink interior is honestly grayscale -- an engraving is one ink --
    so the default converts to gray first; a colour interior (profile ink:
    color, #214) keeps its hues, quantized to a colour palette that still
    compresses hard. Median-cut keeps the tones the art actually uses. Returns
    a paletted image whose distinct colors are at most ``colors``.
    """

    from PIL import Image

    if colors < 2:
        raise ValueError("a palette needs at least 2 colors")
    source = image.convert("L") if grayscale else image.convert("RGB")
    return source.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)


def _write_lossless_png(image, dst: Path) -> None:
    """Write a paletted PNG, optimized. pngquant/oxipng squeeze further when
    present, but PIL's optimizer alone already beats a truecolor encode."""

    image.save(dst, format="PNG", optimize=True)
    for tool, argv in (
        ("oxipng", ["oxipng", "-o", "4", "--quiet", str(dst)]),
        ("pngcrush", ["pngcrush", "-ow", "-q", str(dst)]),
    ):
        if adapters.environment.which(tool):
            adapters.process_runner.run(argv, check=False, capture=True, timeout=120)
            break


@dataclass(frozen=True)
class Result:
    """What an enhance produced: the path written, its size, and whether the
    external upscaler ran or the pure fallback did."""

    path: Path
    width: int
    height: int
    colors: int
    upscaled: bool


# The default long edge to finish to: 2400px covers a full-page plate on a
# 6x9 interior at 300 DPI and is ample for the reader. Upscaling well past it
# and resampling back down is deliberate -- the extra detail from the model
# survives as clean anti-aliased line, which is exactly what an engraving wants.
_DEFAULT_MAX_EDGE = 2400


def enhance(src: Path, dst: Path, *, model: str | None = None,
            colors: int = 16, scale: int = 4, medium: str = "",
            max_edge: int = _DEFAULT_MAX_EDGE, grayscale: bool = True) -> Result:
    """Finish one image: upscale (if a model is installed), resample to a
    print-grade target long edge, quantize, and write a lossless PNG. With no
    upscaler present the image is resampled with a plain high-quality filter
    instead, so the quantize/compress win still lands and the call never fails
    for want of the external tool. ``grayscale`` false keeps a colour interior's
    plates in colour (#214); it defaults true, the single-ink honest space.
    """

    from PIL import Image

    if medium and model is None:
        model, colors = profile_for(medium)
    model = model or _DEFAULT_PROFILE[0]

    upscaler = find_upscaler()
    upscaled = False
    big: Image.Image
    tmp = dst.with_suffix(".upscaled.png")
    if upscaler is not None:
        upscale(src, tmp, model=available_model(upscaler, model),
                scale=scale, upscaler=upscaler)
        big = Image.open(tmp)
        upscaled = True
    else:
        big = Image.open(src)

    # Resample to the target long edge. The model overshoots on purpose; a book
    # never wants a 10000px plate, and the downsample carries the model's detail
    # into a clean, anti-aliased line at a size the print and the reader use.
    # Never upscale here beyond what we have -- only cap the long edge down.
    longest = max(big.width, big.height)
    if longest > max_edge:
        ratio = max_edge / longest
        big = big.resize((round(big.width * ratio), round(big.height * ratio)),
                         Image.Resampling.LANCZOS)

    paletted = quantize(big, colors, grayscale=grayscale)
    dst.parent.mkdir(parents=True, exist_ok=True)
    _write_lossless_png(paletted, dst)
    if tmp.exists():
        tmp.unlink()

    final = Image.open(dst)
    counted = final.convert("L") if grayscale else final.convert("RGB")
    distinct = len(counted.getcolors(maxcolors=colors * 4) or [])
    return Result(path=dst, width=final.width, height=final.height,
                  colors=distinct, upscaled=upscaled)
