"""Generate the print cover wrap: back cover, spine, front cover, one PDF.

Spine width is a generator, never a hand-entered number: page count is
read from the built interior PDF (the CLI builds it first; a wrap must
never be computed from a stale interior) and multiplied by the paper's
per-page thickness. The wrap is laid out in TeX and compiled by the
same toolchain that builds the book, so the cover art, imprint device,
and barcode are placed as vectors and embedded fonts, not a flattened
raster.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import barcode, booklib

# Cover bleed is universal across print vendors (0.125in on the outer edges);
# only the spine caliper and wrap geometry are provider-specific, and those
# live in the provider spec (press.provider_specs).
BLEED_IN = 0.125


def interior_page_count(interior: Path) -> int:
    from pypdf import PdfReader

    return len(PdfReader(str(interior)).pages)


def spine_width(pages: int) -> float:
    """Spine width from the active provider spec's caliper model, honoring a
    per-book ``print.page-thickness`` override. The house spec reproduces the
    v1 value exactly; a real provider spec carries that vendor's calipers."""

    from . import provider_specs

    conf = booklib.metadata().get("print") or {}
    override = conf.get("page-thickness")
    return provider_specs.active().spine(
        pages,
        conf.get("paper"),
        override=float(override) if override is not None else None,
    )


@dataclass(frozen=True)
class WrapLayout:
    """The cover wrap's geometry for one binding: total size and the panel
    edges the content is placed against. Perfect-bound reproduces the v1
    numbers exactly; other bindings change the topology (no spine, a board
    turn-in, or jacket flaps)."""

    wrap_w: float
    wrap_h: float
    spine: float
    has_spine: bool
    margin: float          # outer allowance: bleed (soft cover) or turn-in (board)
    flap: float            # jacket flap width, else 0
    back_x: float          # left edge of the back panel
    front_x: float         # left edge of the front panel
    front_art_w: float     # width the front art fills
    cloth_field: bool      # paint the cloth-colored field (off for linen)


# Bindings press knows how to lay out without a vendor spec: a soft-cover flat
# wrap, with or without a spine. Hardcover bindings (a board turn-in or a
# jacket) need the provider spec to supply the turn-in or flap width, so an
# unsupported binding is refused rather than guessed.
_SOFT_BINDINGS = {
    "perfect-bound": True,    # has a spine
    "saddle-stitch": False,
    "coil": False,
}


def _binding_geometry(spec, binding: str, material: str) -> tuple[bool, float, float]:
    """(has_spine, margin, flap) for a binding, from the provider spec's cover
    section, falling back to the soft-cover defaults."""

    bindings = (spec.data.get("cover") or {}).get("bindings") or {}
    if binding in bindings:
        entry = bindings[binding]
        has_spine = bool(entry.get("spine", True))
        margin = float(entry.get("turn-in", spec.bleed))
        flap = float(entry.get("flap", 0.0))
        return has_spine, margin, flap
    if binding in _SOFT_BINDINGS:
        return _SOFT_BINDINGS[binding], spec.bleed, 0.0
    raise SystemExit(
        f"provider {spec.id!r} does not define the {binding!r} binding; "
        f"add a cover.bindings.{binding} entry to its spec"
    )


def wrap_geometry(
    trim_w: float, trim_h: float, spine: float, has_spine: bool,
    margin: float, flap: float, material: str,
) -> WrapLayout:
    """Compose the wrap from trim, spine, outer margin, and flap. Pure: the
    left-to-right panels are [margin][flap][back][spine][front][flap][margin].
    Perfect-bound (flap 0, margin = bleed) yields the exact v1 numbers."""

    wrap_w = 2 * margin + 2 * flap + 2 * trim_w + spine
    wrap_h = 2 * margin + trim_h
    back_x = margin + flap
    front_x = back_x + trim_w + spine
    # A flapless wrap bleeds the front art into the outer edge; a jacket keeps
    # the art to the front panel and leaves the flap blank.
    front_art_w = trim_w if flap else trim_w + margin
    return WrapLayout(
        wrap_w, wrap_h, spine, has_spine, margin, flap,
        back_x, front_x, front_art_w, cloth_field=material != "linen",
    )


def layout(pages: int) -> WrapLayout:
    """Resolve the wrap geometry for the book's selected binding and material.
    Read by both the generator and the verifier so they cannot disagree."""

    from . import provider_specs

    book = booklib.book()
    trim_w, trim_h = book.trim_width, book.trim_height
    print_cfg = booklib.metadata().get("print") or {}
    binding = print_cfg.get("binding", "perfect-bound")
    material = print_cfg.get("material", "paperback")

    spec = provider_specs.active()
    has_spine, margin, flap = _binding_geometry(spec, binding, material)
    spine = spine_width(pages) if has_spine else 0.0
    return wrap_geometry(trim_w, trim_h, spine, has_spine, margin, flap, material)


def isbn_for_print() -> str | None:
    from . import registrations

    return registrations.isbn("print")


def barcode_tex(isbn: str | None) -> str:
    """The barcode panel: real EAN-13 rules, or an honest placeholder."""

    if isbn is None:
        return (
            "\\begin{tikzpicture}\n"
            # The placeholder sits on the same white card a real symbol
            # gets, so the panel geometry does not shift when the ISBN
            # arrives.
            "\\fill[white] (-0.125in,-0.125in) rectangle (2.125in,1.325in);\n"
            "\\draw[black] (0,0) rectangle (2in,1.2in);\n"
            "\\node at (1in,0.6in) {\\small [ISBN pending]};\n"
            "\\end{tikzpicture}"
        )
    digits = barcode.validate(isbn)
    module = 0.0130  # inches; 100% EAN magnification is 0.33mm
    bars = []
    x = 0.0
    for kind, count in barcode.runs(isbn):
        width = count * module
        if kind == "ink":
            bars.append(
                f"\\fill[black] ({x:.4f}in,0) rectangle ({x + width:.4f}in,0.9in);"
            )
        x += width
    # Human-readable digits per the EAN convention: the leading digit
    # sits left of the left guard, outside the symbol; each 6-digit
    # group centers under its own half.
    left_center = ((3 + 45) / 2) * module
    right_center = ((50 + 92) / 2) * module
    return (
        "\\begin{tikzpicture}\n"
        "\\fill[white] (-0.2in,-0.32in) rectangle "
        f"({x + 0.15:.4f}in,1.05in);\n"
        + "\n".join(bars)
        + f"\n\\node[anchor=north east] at (-0.02in,-0.04in) {{\\ttfamily\\small {digits[0]}}};"
        f"\n\\node[anchor=north] at ({left_center:.4f}in,-0.04in) {{\\ttfamily\\small {digits[1:7]}}};"
        f"\n\\node[anchor=north] at ({right_center:.4f}in,-0.04in) {{\\ttfamily\\small {digits[7:13]}}};\n"
        "\\end{tikzpicture}"
    )


def tex_safe_path(path: Path) -> Path:
    """Refuse paths TeX would mis-parse; quoting does not neutralize them."""

    if any(ch in str(path) for ch in "%#$&~{}\\"):
        raise SystemExit(
            f"path contains TeX-active characters and cannot be included: {path}"
        )
    return path


def generate(interior: Path, output: Path) -> Path:
    root = booklib.root()
    meta = booklib.metadata()
    missing = [
        key for key in ("title", "author", "publisher", "publisher-place")
        if not meta.get(key)
    ]
    if missing:
        raise SystemExit(
            "the cover wrap needs these config/metadata.yaml keys: " + ", ".join(missing)
        )
    trim = meta.get("trim") or {}
    trim_w = float(trim.get("width", 6))
    pages = interior_page_count(interior)
    lay = layout(pages)
    spine = lay.spine
    wrap_w, wrap_h = lay.wrap_w, lay.wrap_h

    cover = tex_safe_path(root / "assets" / "cover.jpg")
    if not cover.is_file():
        raise SystemExit("coverwrap needs assets/cover.jpg (the front board art)")
    logo = tex_safe_path(root / "assets" / "press-logo.png")
    authors = list(booklib.book().authors)

    def esc(value: str) -> str:
        from .gen_front_matter import escape

        return escape(value)

    logo_block = (
        f"\\includegraphics[width=1.1in]{{\"{logo}\"}}\\\\[0.18in]" if logo.is_file() else ""
    )
    spine_text = (
        f"{esc(meta['title'])} \\hspace{{0.35in}} {esc(', '.join(authors))}"
    )
    # A spine under 0.25in cannot carry readable text; KDP forbids spine
    # text below 0.0625in x ~100 pages. Drop it rather than shrink it.
    spine_node = (
        "\\node[rotate=-90] at (spinecenter) "
        f"{{\\scshape\\small {spine_text}}};"
        if lay.has_spine and spine >= 0.25 else "% spine too thin (or absent) for text"
    )
    cloth_line = (
        f"\\fill[black!85!red!25!white] (0,0) rectangle ({wrap_w:.4f}in,{wrap_h:.4f}in);"
        if lay.cloth_field
        else "% linen case: the material is the finish; no printed field"
    )
    spine_cx = lay.back_x + trim_w + spine / 2
    back_text_x = lay.back_x + 0.75
    back_text_y = wrap_h - lay.margin - 0.85
    barcode_x = lay.back_x + trim_w - 0.5
    barcode_y = lay.margin + 0.5

    tex = f"""% Generated cover wrap; the source of every number is config or the
% built interior. Regenerated every run.
\\documentclass{{article}}
\\usepackage[paperwidth={wrap_w:.4f}in,paperheight={wrap_h:.4f}in,margin=0in]{{geometry}}
\\usepackage{{graphicx,tikz,xcolor}}
\\usepackage{{libertinus}}
\\pagestyle{{empty}}
\\begin{{document}}
\\thispagestyle{{empty}}%
\\noindent
\\begin{{tikzpicture}}[remember picture,overlay,shift={{(current page.south west)}}]
% cloth-colored field over the full bleed
{cloth_line}
% front cover art, full front panel plus bleed
\\node[anchor=south west,inner sep=0] at ({lay.front_x:.4f}in,0in)
  {{\\includegraphics[width={lay.front_art_w:.4f}in,height={wrap_h:.4f}in]{{"{cover}"}}}};
% spine
\\coordinate (spinecenter) at ({spine_cx:.4f}in,{wrap_h / 2:.4f}in);
{spine_node}
% back cover text block
\\node[anchor=north west,text width={trim_w - 1.5:.4f}in,align=center]
  at ({back_text_x:.4f}in,{back_text_y:.4f}in) {{
  {{\\large\\scshape {esc(meta['title'])}\\par}}\\vspace{{0.3in}}
  {{\\small {esc(meta.get('description', ''))}\\par}}\\vspace{{0.4in}}
  {logo_block}
  {{\\footnotesize\\scshape {esc(meta['publisher'])}, {esc(meta['publisher-place'])}\\par}}
}};
% barcode, back cover lower right with quiet margin
\\node[anchor=south east] at ({barcode_x:.4f}in,{barcode_y:.4f}in) {{
{barcode_tex(isbn_for_print())}
}};
\\end{{tikzpicture}}%
\\end{{document}}
"""
    build = root / "build" / "coverwrap"
    if build.exists():
        shutil.rmtree(build)
    build.mkdir(parents=True)
    source = build / "coverwrap.tex"
    source.write_text(tex, encoding="utf-8")
    compiled = subprocess.run(
        ["latexmk", "-lualatex", "-interaction=nonstopmode", "coverwrap.tex"],
        cwd=build, capture_output=True, text=True,
    )
    if compiled.returncode != 0:
        log = build / "coverwrap.log"
        tail = log.read_text(encoding="utf-8", errors="replace")[-2000:] if log.is_file() else compiled.stdout[-2000:]
        raise SystemExit(f"coverwrap TeX failed; log tail:\n{tail}")
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(build / "coverwrap.pdf", output)

    # The wrap is verified as an object before it is blessed: one page,
    # exactly the computed size.
    from pypdf import PdfReader

    page = PdfReader(str(output)).pages[0]
    width_in = float(page.mediabox.width) / 72
    height_in = float(page.mediabox.height) / 72
    if abs(width_in - wrap_w) > 0.01 or abs(height_in - wrap_h) > 0.01:
        raise SystemExit(
            f"coverwrap is {width_in:.3f} x {height_in:.3f} in; "
            f"expected {wrap_w:.3f} x {wrap_h:.3f}"
        )
    print(
        f"coverwrap: {pages} pages -> {spine:.3f}in spine, "
        f"{wrap_w:.3f} x {wrap_h:.3f}in with bleed -> {output.relative_to(root)}"
    )
    return output
