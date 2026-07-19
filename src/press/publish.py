"""Channel checklists: press publish kdp|ingram.

The press cannot upload to retail channels (they have no APIs worth
trusting), so it does the next honest thing: build and verify every
retail artifact now, then emit a checklist where a checked box means
"this artifact passed its verifier in this run", with the items only
a person can do left unchecked. A stale or corrupt file cannot be
blessed, because the checklist never consults mere existence: the
interior, wrap, and EPUB are rebuilt through the registry and
inspected by their own verifiers first. --report-only skips the
build and says so on every line instead of pretending.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from . import booklib, gen_coverwrap

CHANNELS = {
    "kdp": {
        "name": "Amazon KDP",
        "manual": [
            "KDP account with tax interview completed",
            "Category selections (2 allowed; note 10 keyword slots)",
            "Pricing per marketplace and royalty option (60% print)",
            "Order a physical proof before approving publication",
        ],
    },
    "ingram": {
        "name": "IngramSpark",
        "manual": [
            "IngramSpark account and title setup fee",
            "BISAC subject codes (3 allowed)",
            "Wholesale discount and returns policy decisions",
            "Order a physical proof before enabling distribution",
        ],
    },
}


def verify_retail() -> dict[str, tuple[bool, Path, str]]:
    """Build and verify each retail artifact now.

    Returns label -> (passed, path, note); a False entry carries the
    verifier's own refusal as the note.
    """

    from . import registry, verify_coverwrap, verify_formats, verify_pdf

    root = booklib.root()
    slug = booklib.slug()
    dist = root / "dist"
    results: dict[str, tuple[bool, Path, str]] = {}

    def attempt(label: str, path: Path, action) -> None:
        try:
            action()
        except SystemExit as exc:
            results[label] = (False, path, str(exc))
        except subprocess.CalledProcessError as exc:
            results[label] = (False, path, f"build failed with exit {exc.returncode}")
        else:
            results[label] = (True, path, "verified this run")

    interior = dist / f"{slug}-interior.pdf"
    wrap = dist / f"{slug}-coverwrap.pdf"
    epub = dist / f"{slug}.epub"
    cover = root / "assets" / "cover.jpg"

    def interior_check() -> None:
        registry.build("print")
        code = verify_pdf.main([str(interior), "--profile", "print"])
        if code:
            raise SystemExit("interior failed its print verification")

    def wrap_check() -> None:
        registry.build("coverwrap")
        verify_coverwrap.main()

    # Interior and wrap fail separately, each under its own label; a
    # missing cover must never read as an interior defect.
    attempt("Print interior PDF (mirrored margins, black ink)", interior,
            interior_check)
    attempt("Cover wrap PDF (trim + bleed, spine computed)", wrap, wrap_check)

    def epub_verified() -> None:
        registry.build("epub")
        verify_formats.verify_epub(epub)

    attempt("EPUB (KDP eBook / Ingram ebook program)", epub, epub_verified)

    def cover_opens() -> None:
        if not cover.is_file():
            raise SystemExit("assets/cover.jpg missing")
        from PIL import Image

        with Image.open(cover) as art:
            art.verify()

    attempt("Marketing cover image (front board only)", cover, cover_opens)
    return results


def unverified_retail() -> dict[str, tuple[bool, Path, str]]:
    """--report-only: presence noted, verification honestly absent."""

    root = booklib.root()
    slug = booklib.slug()
    dist = root / "dist"
    entries = {
        "Print interior PDF (mirrored margins, black ink)":
            dist / f"{slug}-interior.pdf",
        "Cover wrap PDF (trim + bleed, spine computed)":
            dist / f"{slug}-coverwrap.pdf",
        "EPUB (KDP eBook / Ingram ebook program)": dist / f"{slug}.epub",
        "Marketing cover image (front board only)":
            root / "assets" / "cover.jpg",
    }
    return {
        label: (False, path,
                "present but NOT verified (report-only)" if path.is_file()
                else "missing")
        for label, path in entries.items()
    }


def main(channel: str, report_only: bool = False) -> int:
    if channel not in CHANNELS:
        raise SystemExit(f"unknown channel {channel!r}: {', '.join(CHANNELS)}")
    root = booklib.root()
    meta = booklib.metadata()
    if not meta.get("title") or not meta.get("author"):
        raise SystemExit("the checklist needs title and author in config/metadata.yaml")
    trim = meta.get("trim") or {}
    trim_w, trim_h = float(trim.get("width", 6)), float(trim.get("height", 9))
    isbn = gen_coverwrap.isbn_for_print()
    spec = CHANNELS[channel]

    results = unverified_retail() if report_only else verify_retail()

    lines = [
        f"# {spec['name']} checklist: {meta['title']}",
        "",
        f"Generated by the press from config and dist/. Trim {trim_w:g} x "
        f"{trim_h:g} in, bleed {gen_coverwrap.BLEED_IN} in on the wrap.",
        "A checked box means the artifact passed its verifier in this run.",
        "",
        "## Files the channel needs",
        "",
    ]
    for label, (passed, path, note) in results.items():
        mark = "x" if passed else " "
        lines.append(f"- [{mark}] {label}: {path} ({note})")
    lines += [
        "",
        "## Identity the channel will ask for",
        "",
        f"- [{'x' if isbn else ' '}] Print ISBN: {isbn or '[ISBN pending] in config registrations block'}",
        f"- [x] Title: {meta['title']}",
        f"- [x] Subtitle: {meta.get('subtitle', '')}",
        f"- [x] Author: {', '.join(booklib.book().authors)}",
        f"- [x] Description: {meta.get('description', '').strip()}",
        f"- [x] Keywords: {', '.join(meta.get('keywords') or [])}",
        "",
        "## Only a person can do these",
        "",
        *[f"- [ ] {item}" for item in spec["manual"]],
        "",
    ]
    out = root / "dist" / f"publish-{channel}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"checklist -> {out.relative_to(root)}")
    failed = {label: note for label, (passed, _, note) in results.items() if not passed}
    for label, note in failed.items():
        print(f"  unverified: {label} ({note})")
    if failed and not report_only:
        return 1
    return 0
