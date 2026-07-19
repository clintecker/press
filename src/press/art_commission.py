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


def generate_openai(prompt: str, spec: tuple, count: int,
                    references: list[tuple[bytes, str]] | None = None) -> list[bytes]:
    model, size, quality, transparent = spec
    headers = {"Authorization": f"Bearer {key_for('openai')}"}
    if not references:
        payload = {"model": model, "prompt": prompt, "size": size,
                   "quality": quality, "n": count}
        if transparent:
            payload["background"] = "transparent"
        body = post_json(
            "https://api.openai.com/v1/images/generations", payload, headers
        )
        return [base64.b64decode(item["b64_json"]) for item in body.get("data", [])]

    # Reference-image work goes through images/edits, a multipart form.
    boundary = "pressart" + base64.urlsafe_b64encode(references[0][0][:9]).decode().strip("=")
    fields = {"model": model, "prompt": prompt, "size": size,
              "quality": quality, "n": str(count)}
    parts = []
    for name, value in fields.items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; "
            f'name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    for index, (blob, mime) in enumerate(references):
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; "
            f'name="image[]"; filename="ref{index}.{mime.split("/")[1]}"\r\n'
            f"Content-Type: {mime}\r\n\r\n".encode() + blob + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        "https://api.openai.com/v1/images/edits",
        data=b"".join(parts),
        headers={**headers,
                 "Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise SystemExit(f"api.openai.com refused ({exc.code}): {detail}")
    return [base64.b64decode(item["b64_json"]) for item in body.get("data", [])]


def generate_gemini(prompt: str, spec: tuple, count: int,
                    references: list[tuple[bytes, str]] | None = None) -> list[bytes]:
    # The Imagen predict endpoint is closed to new API users; the Gemini
    # image models answer generateContent with inline image parts.
    model, aspect, image_size = spec
    parts: list[dict] = [{"text": prompt}]
    for blob, mime in references or []:
        parts.append({"inlineData": {
            "mimeType": mime,
            "data": base64.b64encode(blob).decode("ascii"),
        }})
    images: list[bytes] = []
    for _ in range(count):
        body = post_json(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent",
            {"contents": [{"parts": parts}],
             "generationConfig": {
                 "responseModalities": ["TEXT", "IMAGE"],
                 "imageConfig": {"aspectRatio": aspect, "imageSize": image_size},
             }},
            {"x-goog-api-key": key_for("gemini")},
        )
        found = len(images)
        for candidate in body.get("candidates", []):
            for part in (candidate.get("content") or {}).get("parts", []):
                data = (part.get("inlineData") or {}).get("data")
                if data:
                    images.append(base64.b64decode(data))
        if len(images) == found:
            # A refusal explains itself in text or finishReason; relay it.
            for candidate in body.get("candidates", []):
                reason = candidate.get("finishReason", "")
                texts = [p.get("text", "") for p in (candidate.get("content") or {}).get("parts", [])]
                note = " ".join(t for t in texts if t)[:300]
                print(f"    gemini returned no image ({reason}): {note or 'no explanation'}")
    return images


def author_photo(root: Path) -> tuple[bytes, str] | None:
    """The author's own photograph, when supplied: art/author-photo.jpg
    or .png, any case (cameras write .JPG). Its presence turns the
    portrait commission into an engraving of the actual author instead
    of an invented one."""

    mimes = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
    for path in sorted((root / "art").glob("author-photo.*")):
        mime = mimes.get(path.suffix.lower())
        if mime and path.is_file():
            data = path.read_bytes()
            if not data:
                raise SystemExit(
                    f"{path} is empty (an interrupted copy?); "
                    "re-save the photograph and rerun"
                )
            return normalize_reference(data, path), "image/jpeg"
    return None


def normalize_reference(data: bytes, path: Path) -> bytes:
    """A likeness reference needs face detail, not a 24MP camera file;
    full-size exports also overflow the APIs' inline request caps.
    Anything over 2048px or ~4MB is resized and re-encoded in memory;
    the author's file on disk is never touched."""

    import io

    from PIL import Image, ImageOps

    image: Image.Image = Image.open(io.BytesIO(data))
    if (len(data) <= 4_000_000 and max(image.size) <= 2048
            and image.format == "JPEG"):
        # Small and already the format its mime label claims.
        return data
    image = Image.open(io.BytesIO(data))
    transposed = ImageOps.exif_transpose(image)
    if transposed is not None:
        image = transposed
    image.thumbnail((2048, 2048))
    out = io.BytesIO()
    image.convert("RGB").save(out, format="JPEG", quality=90)
    print(f"  reference normalized: {path.name} -> {image.size[0]}x{image.size[1]} jpeg")
    return out.getvalue()


STYLE_PREAMBLE = (
    "STYLE REFERENCES: the attached engravings are earlier accepted "
    "plates from this same book. Match their hand exactly: line weight, "
    "hatching density, black distribution, and framing. The new plate "
    "must look cut by the same engraver.\n\n"
)


def style_references(root: Path, target: str) -> list[tuple[bytes, str]]:
    """Up to two accepted plates, excluding the one being regenerated,
    so every new plate is held to the book's existing hand."""

    if not target.startswith("plate:"):
        return []
    own = target.split(":", 1)[1] + ".jpg"
    plates = [
        p for p in sorted((root / "assets" / "woodcuts").glob("*.jpg"))
        if p.name != own
    ][:2]
    return [(normalize_reference(p.read_bytes(), p), "image/jpeg") for p in plates]


LIKENESS_PREAMBLE = (
    "The attached photograph is the author: the person facing the camera. "
    "Ignore every other face in the frame, including faces printed on "
    "clothing, posters, or in the background. Engrave this actual person: "
    "hold their real features, hair, and expression faithfully while "
    "rendering them entirely in the style directed below. Do not idealize "
    "or substitute a different face. If a feature is hidden in the "
    "photograph (a hat over the hair, sunglasses over the eyes), say so "
    "in one line of text instead of inventing it.\n\n"
)


def commission(targets: list[str], models: list[str], count: int,
               photo_path: str | None = None) -> int:
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

    if photo_path:
        chosen_photo = Path(photo_path)
        if not chosen_photo.is_absolute():
            chosen_photo = root / chosen_photo
        if not chosen_photo.is_file():
            raise SystemExit(f"no such photograph: {chosen_photo}")
        photo: tuple[bytes, str] | None = (normalize_reference(chosen_photo.read_bytes(), chosen_photo),
                 "image/jpeg")
    else:
        photo = author_photo(root)
    saved = 0
    for target, prompt in chosen.items():
        openai_spec, gemini_spec = shape_for(target, prompt)
        references: list[tuple[bytes, str]] = []
        if target == "portrait" and photo:
            references = [photo]
            prompt = LIKENESS_PREAMBLE + prompt
            print(f"  {target}: engraving the supplied author photograph")
        else:
            references = style_references(root, target)
            if references:
                prompt = STYLE_PREAMBLE + prompt
                print(f"  {target}: holding to {len(references)} accepted plate(s)")
        directory = root / "art" / "candidates" / target.replace(":", "-")
        directory.mkdir(parents=True, exist_ok=True)
        for model in models:
            images = (
                generate_openai(prompt, openai_spec, count, references)
                if model == "openai"
                else generate_gemini(prompt, gemini_spec, count, references)
            )
            if not images:
                print(f"  {target} <- {model}: no image returned")
                continue
            index = 1
            for blob in images:
                while (directory / f"{model}-{index}.png").exists():
                    index += 1
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
    parser.add_argument("--photo", default=None,
                        help="portrait reference photograph (default art/author-photo.*)")
    args = parser.parse_args(argv)
    return commission(args.targets, args.models or ["openai", "gemini"],
                      args.count, args.photo)
