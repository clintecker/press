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

OPENAI_MODEL = "gpt-image-1"
GEMINI_MODEL = "gemini-3.1-flash-image"

# Target shapes: (openai size, gemini aspectRatio). The cover matches the
# book trim's orientation; plates declare their own composition in the
# prompt; the logomark is square; the portrait is upright.
SHAPES = {
    "portrait": ("1024x1536", "3:4"),
    "landscape": ("1536x1024", "4:3"),
    "square": ("1024x1024", "1:1"),
}


def shape_for(target: str, prompt: str) -> tuple[str, str]:
    if target == "logomark":
        return SHAPES["square"]
    if target.startswith("plate:"):
        lowered = prompt.lower()
        if "landscape composition" in lowered:
            return SHAPES["landscape"]
        if "portrait composition" in lowered:
            return SHAPES["portrait"]
        return SHAPES["square"]
    return SHAPES["portrait"]  # cover and author portrait


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


def generate_openai(prompt: str, size: str, count: int, transparent: bool) -> list[bytes]:
    payload = {"model": OPENAI_MODEL, "prompt": prompt, "size": size, "n": count}
    if transparent:
        payload["background"] = "transparent"
    body = post_json(
        "https://api.openai.com/v1/images/generations",
        payload,
        {"Authorization": f"Bearer {key_for('openai')}"},
    )
    return [base64.b64decode(item["b64_json"]) for item in body.get("data", [])]


def generate_gemini(prompt: str, aspect: str, count: int) -> list[bytes]:
    # The Imagen predict endpoint is closed to new API users; the Gemini
    # image models answer generateContent with inline image parts.
    images: list[bytes] = []
    for _ in range(count):
        body = post_json(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_MODEL}:generateContent",
            {"contents": [{"parts": [{"text": prompt}]}],
             "generationConfig": {
                 "responseModalities": ["TEXT", "IMAGE"],
                 "imageConfig": {"aspectRatio": aspect},
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
        size, aspect = shape_for(target, prompt)
        directory = root / "art" / "candidates" / target.replace(":", "-")
        directory.mkdir(parents=True, exist_ok=True)
        for model in models:
            images = (
                generate_openai(prompt, size, count, transparent=(target == "logomark"))
                if model == "openai"
                else generate_gemini(prompt, aspect, count)
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
