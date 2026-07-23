#!/usr/bin/env python3
"""Commission a cover per example book via an image model, in a chosen style.

A ONE-TIME art commission, not a build step: image generation is
non-deterministic, so covers are generated once here and committed as
assets/cover.jpg, and every build just uses the committed file. Needs
OPENAI_API_KEY.

    python3 scripts/commission_covers.py [--style ID] [slug ...]

A cover STYLE is an art-direction template from src/press/data/cover-styles.yaml
(Penguin tri-band, Swiss, mid-century, Victorian clothbound, pulp, minimalist,
photographic, Art Deco, bold typographic, collage). A book picks one in
config/aesthetic.yaml (`cover: {style: ..., subject: ...}`) and may define its
own in config/cover-styles.yaml; --style overrides for a one-off. The exact
title/author/imprint are quoted with guardrails on `baked` styles; eyeball each
result and re-run any whose text misrenders.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from press import yamlio  # noqa: E402  (after sys.path shim)

OUT = ROOT / "build" / "commissioned-covers"
STYLES_FILE = ROOT / "src" / "press" / "data" / "cover-styles.yaml"

# Fallback woodcut subjects for the house example books, when a book does not
# name its own `cover: subject:`.
SUBJECTS = {
 "tidepool-field-notes": "a rocky intertidal shore at low tide, tide pools among dark rocks, clusters of barnacles and mussels, fronds of kelp, one small shorebird",
 "hearthstone-cookbook": "a plain winter kitchen still life: a steaming iron cooking pot, a round loaf of bread, onions and root vegetables on a scrubbed wooden table, a small window with falling snow",
 "signal-and-noise-manual": "an amateur radio workbench: an opened valve wireless set, coils and wires, a soldering iron, a wire aerial to a window, faint concentric radio waves above rooftops",
 "small-hours-chapbook": "a quiet attic room at night: a single desk lamp by a window, rooftops and chimneys under a crescent moon and scattered stars",
 "on-the-commons-monograph": "an allegory of the village common: hands stacking sheaves of wheat, a low drystone wall, sheep grazing under an even sky, orderly and classical",
 "the-tinsmith-novella": "a riverside tinsmith's workshop: hammers and tin-snips, sheets of tin, a hanging oil lamp, a workbench, a small river town through an open door",
 "the-long-field-essays": "a long English field under a wide sky: hedgerows, a single old oak, plough furrows receding to a distant farmhouse",
 "field-days-almanac": "a cheerful children's nature scene: a summer meadow with wildflowers, birds on a fence wire, a frog at a pond's edge, a bright sun",
}

GUARDRAIL = """

EXACT TEXT — render verbatim, correctly spelled, and put NO other words on the cover:
  "{title}"  (the title)
  "{author}"  (the author)
  "{imprint}"  (the publisher, where the layout names it)
Precise, legible typography. Flat printed look, faint paper texture.
Do NOT add: any other text, a price, a barcode, a watermark, or extra logos."""


def _load_styles(book: Path) -> dict:
    styles = dict(yamlio.load(STYLES_FILE)["styles"])
    custom = book / "config" / "cover-styles.yaml"
    if custom.is_file():                       # a book may define its own
        styles.update((yamlio.load(custom) or {}).get("styles", {}))
    return styles


def _ctx(slug: str) -> dict:
    book = ROOT / "examples" / slug
    meta = yamlio.load(book / "config" / "metadata.yaml")
    aes = yamlio.load(book / "config" / "aesthetic.yaml") or {}
    cover = aes.get("cover") or {}
    authors = meta.get("author") or []
    imprint = str(meta.get("publisher") or "")
    skip = {"and", "the", "of", "for", "&", "a"}
    initials = "".join(w[0] for w in imprint.split()
                       if w[:1].isalpha() and w.lower() not in skip)[:3].upper()
    palette = aes.get("web-palette") or aes
    return {
        "title": str(meta.get("title") or ""),
        "author": str(authors[0] if authors else ""),
        "imprint": imprint,
        "initials": initials,
        "subject": cover.get("subject") or SUBJECTS.get(slug, "the book's subject"),
        "accent": palette.get("accent") or "#7a2325",
        "paper": palette.get("paper") or "#f4f1e6",
        "_style": cover.get("style") or "penguin-tri-band",
    }


def prompt_for(slug: str, style_id: str) -> str:
    ctx = _ctx(slug)
    style = _load_styles(ROOT / "examples" / slug).get(style_id)
    if not style:
        raise SystemExit(f"unknown cover style {style_id!r}")
    prompt = style["prompt"].format(**ctx)
    if style.get("text", "baked") == "baked":
        prompt += GUARDRAIL.format(**ctx)
    return prompt


def generate(slug: str, style_id: str) -> None:
    data = json.dumps({"model": "gpt-image-2", "prompt": prompt_for(slug, style_id),
                       "size": "1024x1536", "quality": "high", "n": 1}).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations", data=data,
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        b = json.load(r)["data"][0]["b64_json"]
    OUT.mkdir(parents=True, exist_ok=True)
    name = f"{slug}.png" if style_id == _ctx(slug)["_style"] else f"{slug}--{style_id}.png"
    (OUT / name).write_bytes(base64.b64decode(b))
    print(f"ok   {slug}  [{style_id}]")


def main(argv: list[str]) -> None:
    override = None
    if argv and argv[0] == "--style":
        override, argv = argv[1], argv[2:]
    slugs = argv or list(SUBJECTS)
    for s in slugs:
        style_id = override or _ctx(s)["_style"]
        try:
            generate(s, style_id)
        except Exception as e:  # noqa: BLE001 -- a one-off tool; report and go on
            print(f"FAIL {s} [{style_id}]: {e}")
    print(f"+ commissioned {len(slugs)} cover(s) -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
