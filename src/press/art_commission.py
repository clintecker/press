"""Submit commissioned prompts to image models: press art commission.

The art-direction workflow writes the prompts; this module spends the
money. Each prompt in art/commissions.md is submitted to the chosen
model at the aspect ratio its target demands, and every returned image
lands under art/candidates/<target>/ for a human eye. Nothing here
touches assets/; a candidate becomes part of the book only through
press art accept.

API keys come from the environment (OPENAI_API_KEY, GEMINI_API_KEY);
the press never stores them. Every call is a deliberate spend, so the
command reports what it will submit and to which model before it does.
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from . import booklib

# Model choices are print-driven, researched 2026-07: a 6 x 9 cover at
# 300dpi needs ~1800x2700px, so drafts-at-1K models cannot serve finals.
# gpt-image-2 takes arbitrary sizes (multiples of 16, max edge 3840,
# max ~8.3MP) but dropped transparent backgrounds, so the logomark
# stays on gpt-image-1 where transparency is supported and proven.
# On Gemini, gemini-3-pro-image (best text rendering) takes the cover;
# gemini-3.1-flash-image (the workhorse) takes plates and portrait;
# both accept imageConfig {aspectRatio, imageSize} up to 4K.
OPENAI_FLAGSHIP = "gpt-image-2"
OPENAI_TRANSPARENT = "gpt-image-1"
GEMINI_FLAGSHIP = "gemini-3-pro-image"
GEMINI_WORKHORSE = "gemini-3.1-flash-image"

# (openai model, size, quality, transparent), (gemini model, aspect, imageSize)
SHAPES = {
    "cover": ((OPENAI_FLAGSHIP, "2304x3456", "high", False),
              (GEMINI_FLAGSHIP, "2:3", "4K")),
    "portrait-plate": ((OPENAI_FLAGSHIP, "2304x3456", "high", False),
                       (GEMINI_WORKHORSE, "2:3", "2K")),
    "landscape-plate": ((OPENAI_FLAGSHIP, "3456x2304", "high", False),
                        (GEMINI_WORKHORSE, "3:2", "2K")),
    "square-plate": ((OPENAI_FLAGSHIP, "2048x2048", "high", False),
                     (GEMINI_WORKHORSE, "1:1", "2K")),
    "logomark": ((OPENAI_TRANSPARENT, "1024x1024", "high", True),
                 (GEMINI_WORKHORSE, "1:1", "1K")),
    "author-portrait": ((OPENAI_FLAGSHIP, "2304x3456", "high", False),
                        (GEMINI_WORKHORSE, "2:3", "2K")),
}


def shape_for(target: str, prompt: str) -> tuple[tuple, tuple]:
    if target == "logomark":
        key = "logomark"
    elif target == "cover":
        key = "cover"
    elif target == "portrait":
        key = "author-portrait"
    else:
        lowered = prompt.lower()
        if "landscape composition" in lowered:
            key = "landscape-plate"
        elif "portrait composition" in lowered:
            key = "portrait-plate"
        else:
            key = "square-plate"
    return SHAPES[key]


def parse_commissions(path: Path) -> dict[str, str]:
    """target -> prompt, from the workflow's commissions.md structure."""

    if not path.is_file():
        raise SystemExit(
            f"no {path.name}; run the art-direction workflow first"
        )
    text = path.read_text(encoding="utf-8")
    prompts: dict[str, str] = {}
    section = None
    plate = None
    fence: list[str] | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip().lower()
            plate = None
        elif line.startswith("### "):
            plate = line[4:].strip()
        elif line.startswith("```"):
            if fence is None:
                fence = []
            else:
                prompt = "\n".join(fence).strip()
                fence = None
                if not prompt or section is None:
                    continue
                if section.startswith("cover"):
                    prompts.setdefault("cover", prompt)
                elif section.startswith("plates") and plate:
                    prompts.setdefault(f"plate:{plate}", prompt)
                elif section.startswith("logomark"):
                    prompts.setdefault("logomark", prompt)
                elif section.startswith("author portrait"):
                    prompts.setdefault("portrait", prompt)
        elif fence is not None:
            fence.append(line)
    if not prompts:
        raise SystemExit(f"{path} contains no fenced prompts I recognize")
    return prompts


def post_json(url: str, payload: dict, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise SystemExit(f"{url.split('/')[2]} refused ({exc.code}): {detail}")


def key_for(model: str) -> str:
    var = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}[model]
    value = os.environ.get(var)
    if not value:
        raise SystemExit(f"{var} is not set; the press does not store keys")
    return value


def generate_openai(prompt: str, spec: tuple, count: int) -> list[bytes]:
    model, size, quality, transparent = spec
    payload = {"model": model, "prompt": prompt, "size": size,
               "quality": quality, "n": count}
    if transparent:
        payload["background"] = "transparent"
    body = post_json(
        "https://api.openai.com/v1/images/generations",
        payload,
        {"Authorization": f"Bearer {key_for('openai')}"},
    )
    return [base64.b64decode(item["b64_json"]) for item in body.get("data", [])]


def generate_gemini(prompt: str, spec: tuple, count: int) -> list[bytes]:
    # The Imagen predict endpoint is closed to new API users; the Gemini
    # image models answer generateContent with inline image parts.
    model, aspect, image_size = spec
    images: list[bytes] = []
    for _ in range(count):
        body = post_json(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent",
            {"contents": [{"parts": [{"text": prompt}]}],
             "generationConfig": {
                 "responseModalities": ["TEXT", "IMAGE"],
                 "imageConfig": {"aspectRatio": aspect, "imageSize": image_size},
             }},
            {"x-goog-api-key": key_for("gemini")},
        )
        for candidate in body.get("candidates", []):
            for part in (candidate.get("content") or {}).get("parts", []):
                data = (part.get("inlineData") or {}).get("data")
                if data:
                    images.append(base64.b64decode(data))
    return images


def commission(targets: list[str], models: list[str], count: int) -> int:
    root = booklib.root()
    prompts = parse_commissions(root / "art" / "commissions.md")
    chosen = {t: p for t, p in prompts.items() if not targets or t in targets}
    unknown = [t for t in targets if t not in prompts]
    if unknown:
        raise SystemExit(
            f"no commission for {', '.join(unknown)}; have: {', '.join(prompts)}"
        )
    plan = ", ".join(f"{t} -> {'+'.join(models)}" for t in chosen)
    print(f"submitting {len(chosen)} commissions ({count} image(s) each): {plan}")

    saved = 0
    for target, prompt in chosen.items():
        openai_spec, gemini_spec = shape_for(target, prompt)
        directory = root / "art" / "candidates" / target.replace(":", "-")
        directory.mkdir(parents=True, exist_ok=True)
        for model in models:
            images = (
                generate_openai(prompt, openai_spec, count) if model == "openai"
                else generate_gemini(prompt, gemini_spec, count)
            )
            if not images:
                print(f"  {target} <- {model}: no image returned")
                continue
            for index, blob in enumerate(images, start=1):
                out = directory / f"{model}-{index}.png"
                out.write_bytes(blob)
                print(f"  {target} <- {model}: {out.relative_to(root)} ({len(blob)//1024}kB)")
                saved += 1
    if saved == 0:
        raise SystemExit("no images were produced")
    print(
        f"{saved} candidate(s) under art/candidates/; review, then take one in "
        "with: press art accept <file> --as <target>"
    )
    return 0


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="press art commission")
    parser.add_argument("targets", nargs="*",
                        help="cover, plate:<name>, logomark, portrait; default all")
    parser.add_argument("--model", action="append", choices=["openai", "gemini"],
                        dest="models", help="repeatable; default both")
    parser.add_argument("--count", type=int, default=1,
                        help="images per target per model (default 1)")
    args = parser.parse_args(argv)
    return commission(args.targets, args.models or ["openai", "gemini"], args.count)
