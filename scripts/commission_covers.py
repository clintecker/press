#!/usr/bin/env python3
"""Commission a Penguin-style cover per example book via an image model.

A ONE-TIME art commission, not a build step: image generation is
non-deterministic, so covers are generated once here and committed as
assets/cover.jpg, and every build just uses the committed file. Needs
OPENAI_API_KEY. Run:  python3 scripts/commission_covers.py [slug ...]

Each cover is the classic Penguin tri-band grid -- coloured bands top and
bottom, a cream centre, Gill Sans title and author -- distinguished the way
real Penguins are: one colour (the book's accent) and one woodcut (its
subject). The exact title/author/imprint are quoted with guardrails; the
caller should eyeball each result and re-run a slug whose text misrenders.
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Raw generations land here (a gitignored build dir); an operator reviews them
# and copies the good ones to each book's assets/cover.jpg.
OUT = ROOT / "build" / "commissioned-covers"

# The woodcut subject for each book's central vignette.
SUBJECTS = {
 "tidepool-field-notes": "a rocky intertidal shore at low tide, tide pools among dark rocks, clusters of barnacles and mussels, fronds of kelp, one small shorebird",
 "hearthstone-cookbook": "a plain winter kitchen still life: a steaming iron cooking pot, a round loaf of bread, onions and root vegetables on a scrubbed wooden table, a small window with falling snow beyond",
 "signal-and-noise-manual": "an amateur radio workbench: an opened valve wireless set, coils and wires, a soldering iron, a wire aerial rising to a window, faint concentric radio waves above rooftops",
 "small-hours-chapbook": "a quiet attic room at night seen from within: a single desk lamp by a window, rooftops and chimneys under a crescent moon and scattered stars beyond the glass",
 "on-the-commons-monograph": "an allegory of the village common: hands stacking sheaves of wheat, a low drystone wall, sheep grazing under an even sky, orderly and classical",
 "the-tinsmith-novella": "a riverside tinsmith's workshop: hammers and tin-snips, sheets of tin, a hanging oil lamp, a workbench, a small river town seen through an open door",
 "the-long-field-essays": "a long English field under a wide sky: hedgerows, a single old oak, plough furrows receding to a distant farmhouse",
 "field-days-almanac": "a cheerful children's nature scene: a summer meadow with wildflowers, birds on a fence wire, a frog at a pond's edge, a bright sun; lively and warm",
}

def _val(text, key, indent=""):
    m = re.search(rf'^{indent}{key}:[ \t]*"?([^"\n]+)"?', text, re.M)
    return m.group(1).strip().strip('"') if m else ""

def _first_author(meta):
    m = re.search(r'^author:[ \t]*\n[ \t]+-[ \t]*(.+)$', meta, re.M)
    return m.group(1).strip().strip('"') if m else ""

def prompt_for(slug):
    meta = (ROOT/"examples"/slug/"config"/"metadata.yaml").read_text()
    aes = (ROOT/"examples"/slug/"config"/"aesthetic.yaml").read_text()
    title, author, imprint = _val(meta,"title"), _first_author(meta), _val(meta,"publisher")
    accent = _val(aes,"accent",indent="  ") or "#7a2325"
    paper  = _val(aes,"paper",indent="  ") or "#f4f1e6"
    subject = SUBJECTS[slug]
    skip = {"and","the","of","for","&","a"}
    initials = "".join(w[0] for w in imprint.split()
                       if w[:1].isalpha() and w.lower() not in skip)[:3].upper()
    return f"""A classic mid-century Penguin-style paperback book cover, portrait, flat graphic print design, photographed vintage paperback, printed in a SINGLE colour ({accent}) on warm cream ({paper}).

STRICT HORIZONTAL TRI-BAND GRID (straight, symmetrical, edge to edge):
- Top band (~22% of height): solid {accent}. Centered: a thin cream horizontal oval outline enclosing the small words "{imprint}" in tiny clean sans-serif capitals.
- Middle band (~56%): cream. In its UPPER third, two centered lines of Gill Sans (clean humanist sans-serif), evenly letter-spaced, in {accent}:
    line 1, large and bold: {title}
    line 2, smaller: {author}
  BELOW the type, filling the rest of the cream band, one woodcut / linocut illustration in the SAME {accent} ink on cream: {subject}. Bold clean engraving linework with cross-hatching.
- Bottom band (~22%): solid {accent}. Centered in it, a small thin cream oval outline enclosing the publisher's monogram: the capital letters "{initials}" in clean cream sans-serif, well-sized and centred so they read clearly. Nothing else in this band.

EXACT TEXT — render verbatim, correctly spelled, NO other words anywhere on the cover:
  "{title}"
  "{author}"
  "{imprint}"  (as the top oval)
  "{initials}"  (as the bottom monogram)

Gill Sans typography, precise even kerning, strong legible title. Flat matte printed look, faint vintage paper texture.
Do NOT add: any other text, price, barcode, penguin bird, watermark, extra logos, or an outer border around the whole cover."""

def generate(slug):
    data = json.dumps({"model":"gpt-image-2","prompt":prompt_for(slug),
                       "size":"1024x1536","quality":"high","n":1}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/images/generations", data=data,
        headers={"Authorization":f"Bearer {os.environ['OPENAI_API_KEY']}","Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        b = json.load(r)["data"][0]["b64_json"]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/f"{slug}.png").write_bytes(base64.b64decode(b))
    print(f"ok   {slug}")

def main(argv):
    slugs = argv or list(SUBJECTS)
    for s in slugs:
        try:
            generate(s)
        except Exception as e:  # noqa: BLE001 -- a one-off tool; report and go on
            print(f"FAIL {s}: {e}")
    print(f"+ commissioned {len(slugs)} covers -> {OUT}")

if __name__ == "__main__":
    main(sys.argv[1:])
