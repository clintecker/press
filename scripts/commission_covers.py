#!/usr/bin/env python3
"""Commission covers for the example books, reusing the press cover engine.

`press cover` commissions a cover for the book in the current directory; the
gallery examples are not a working directory, so this small tool loops the same
engine (press.cover) over examples/<slug>, in each book's own style (or one
forced with --style). It exists only to (re)generate the gallery's committed
covers; authoring a real book uses `press cover`. Needs OPENAI_API_KEY.

    python3 scripts/commission_covers.py [--style ID] [slug ...]

Output lands in build/commissioned-covers/ (gitignored); review the lettering
and copy the good ones to examples/<slug>/assets/cover.jpg.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from press import cover, yamlio  # noqa: E402  (after sys.path shim)

EXAMPLES = ROOT / "examples"
OUT = ROOT / "build" / "commissioned-covers"


def commission(slug: str, style_override: str | None) -> None:
    book = EXAMPLES / slug
    meta = yamlio.load(book / "config" / "metadata.yaml")
    aes = yamlio.load(book / "config" / "aesthetic.yaml") or {}
    styles = cover.load_styles(book)
    style_id = style_override or (aes.get("cover") or {}).get("style") or "penguin-tri-band"
    if style_id not in styles:
        print(f"FAIL {slug}: unknown style {style_id!r}")
        return
    ctx = cover.context(meta, aes)
    prompt = cover.build_prompt(styles[style_id], ctx)
    default = (aes.get("cover") or {}).get("style") or "penguin-tri-band"
    name = f"{slug}.png" if style_id == default else f"{slug}--{style_id}.png"
    try:
        cover._generate(prompt, OUT / name)
        print(f"ok   {slug}  [{style_id}]")
    except Exception as e:  # noqa: BLE001 -- a one-off tool; report and go on
        print(f"FAIL {slug} [{style_id}]: {e}")


def main(argv: list[str]) -> None:
    override = None
    if argv and argv[0] == "--style":
        override, argv = argv[1], argv[2:]
    slugs = argv or [d.name for d in sorted(EXAMPLES.iterdir())
                     if (d / "config" / "metadata.yaml").is_file()]
    for slug in slugs:
        commission(slug, override)
    print(f"+ commissioned {len(slugs)} cover(s) -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
