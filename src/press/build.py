"""Build every format of the book from the Markdown sources in filename order.

Pandoc defaults live in the press as templates whose path entries use two
prefixes: "@press/..." resolves into the installed package's data directory,
"@book/..." resolves into the book repository. A "?optional" suffix drops the
entry when the book does not carry that file, which is how a book without a
cover, without woodcuts, or without custom front matter builds cleanly from
the same defaults.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import yaml

from . import booklib
from . import gen_authorities
from . import gen_index


def run(command: list[str]) -> None:
    printable = " ".join(command)
    print(f"+ {printable}")
    env = os.environ.copy()
    env.setdefault("SOURCE_DATE_EPOCH", "1784160000")
    env["BOOK_ROOT"] = str(booklib.root())
    env["BOOK_PUBLISHER"] = str(booklib.metadata().get("publisher") or "")
    subprocess.run(command, cwd=booklib.root(), env=env, check=True)


def book_inputs() -> list[str]:
    """Chapters, then appendices merged with generated appendices in letter order."""

    root = booklib.root()
    chapters = [a for a in booklib.chapter_args() if "/chapters/" in a.replace("\\", "/")]
    appendices = [a for a in booklib.chapter_args() if "/appendices/" in a.replace("\\", "/")]
    for generated in (gen_index.generate(), gen_authorities.generate()):
        if generated is not None:
            appendices.append(str(generated.relative_to(root)))
    appendices.sort(key=lambda a: Path(a).name)
    return chapters + appendices


def woodcut_count() -> int:
    return len(list((booklib.root() / "assets" / "woodcuts").glob("*.jpg")))


def _resolve_entry(value: str) -> str | None:
    """Resolve one @-prefixed path; None means an optional file is absent."""

    optional = value.endswith("?optional")
    if optional:
        value = value[: -len("?optional")]
    if value.startswith("@press/"):
        path = booklib.DATA / value[len("@press/") :]
    elif value.startswith("@book/"):
        path = booklib.root() / value[len("@book/") :]
    else:
        return value
    if not path.exists():
        if optional:
            return None
        raise SystemExit(f"defaults reference a missing file: {path}")
    return str(path)


def _resolve_paths(node):
    if isinstance(node, dict):
        resolved = {}
        for key, value in node.items():
            value = _resolve_paths(value)
            if value is not None:
                resolved[key] = value
        return resolved
    if isinstance(node, list):
        values = [_resolve_paths(item) for item in node]
        return [item for item in values if item is not None]
    if isinstance(node, str):
        return _resolve_entry(node)
    return node


def render_defaults(name: str) -> Path:
    """Materialize a press defaults template for this book into build/."""

    with (booklib.DATA / "defaults" / f"{name}.yaml").open(encoding="utf-8") as handle:
        defaults = yaml.safe_load(handle)

    root = booklib.root()
    if name == "html":
        cover = root / "assets" / "cover.jpg"
        if cover.is_file():
            fragment = root / "build" / "cover-fragment.html"
            fragment.parent.mkdir(parents=True, exist_ok=True)
            title = booklib.metadata()["title"]
            fragment.write_text(
                '<p style="text-align:center;margin:0 0 2em 0;">'
                f'<img src="assets/cover.jpg" alt="{title} cover" '
                'style="max-width:100%;height:auto;'
                'box-shadow:0 2px 12px rgba(0,0,0,0.35);"/></p>\n',
                encoding="utf-8",
            )
    if name == "pdf":
        # An empty List of Plates is worse than none; only figure-bearing
        # books get the list.
        defaults.setdefault("variables", {})["lof"] = woodcut_count() > 0

    resolved = _resolve_paths(defaults)
    out = root / "build" / "defaults" / f"{name}.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(resolved, sort_keys=False), encoding="utf-8")
    return out


def pandoc_build(defaults_name: str, output: str, extra: list[str] | None = None) -> None:
    root = booklib.root()
    (root / "dist").mkdir(parents=True, exist_ok=True)
    (root / "build").mkdir(parents=True, exist_ok=True)
    defaults = render_defaults(defaults_name)
    command = ["pandoc", f"--defaults={defaults}"]
    if extra:
        command.extend(extra)
    command.extend(book_inputs())
    command.extend(["--output", output])
    run(command)


def strip_heading_attrs(text: str) -> str:
    """Drop pandoc heading attributes ({-}, {.unnumbered}) from stitched output.

    The stitched Markdown is raw source, not a pandoc render, so attribute
    blocks would ship as literal text. Fence tracking keeps shell comments
    inside code blocks untouched.
    """

    lines = []
    fence = ""
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            fence = "" if fence == stripped[:3] else (fence or stripped[:3])
        elif not fence:
            line = re.sub(r"^(#{1,6}\s.*?)\s*\{[^}]*\}\s*$", r"\1", line)
        lines.append(line)
    return "\n".join(lines)


def markdown_build(output: str) -> None:
    """Stitch the canonical Markdown chapters into one distributable file."""

    root = booklib.root()
    (root / "dist").mkdir(parents=True, exist_ok=True)
    meta = booklib.metadata()
    authors = ", ".join(meta["author"])
    header = (
        f"# {meta['title']}\n\n"
        f"*{meta['subtitle']}*\n\n"
        f"By {authors}. {meta['date']}. {meta['copyright']} "
        f"Published by {meta['publisher']}, {meta['publisher-place']}.\n"
    )
    parts = [header]
    inputs = book_inputs()
    for rel in inputs:
        text = strip_heading_attrs((root / rel).read_text(encoding="utf-8"))
        parts.append(text.strip() + "\n")
    (root / output).write_text("\n".join(parts), encoding="utf-8")
    print(f"+ stitched {len(inputs)} files -> {output}")


def recompress_images(target: Path) -> None:
    """Shrink reader images for the web; engravings tolerate quality 70 well."""

    from PIL import Image

    for path in sorted(target.rglob("*.jpg")):
        image = Image.open(path)
        image.save(path, quality=70, optimize=True)


def site_build(output_dir: str) -> None:
    """Per-chapter HTML site via pandoc's chunkedhtml writer."""

    root = booklib.root()
    out = root / output_dir
    if out.exists():
        shutil.rmtree(out)
    pandoc_build("chunked", output_dir, extra=["--to=chunkedhtml"])
    shutil.copy(booklib.DATA / "web" / "reader.css", out / "reader.css")
    cover = root / "assets" / "cover.jpg"
    if cover.is_file():
        shutil.copy(cover, out / "cover.jpg")
    woodcuts = root / "assets" / "woodcuts"
    if woodcuts.is_dir():
        shutil.copytree(woodcuts, out / "assets" / "woodcuts", dirs_exist_ok=True)
    recompress_images(out)
    archive = root / "dist" / f"{booklib.slug()}-site"
    if archive.with_suffix(".zip").exists():
        archive.with_suffix(".zip").unlink()
    shutil.make_archive(str(archive), "zip", root_dir=root / "dist", base_dir="site")


def download_names() -> list[str]:
    slug = booklib.slug()
    return [
        f"{slug}.pdf",
        f"{slug}.epub",
        f"{slug}.html",
        f"{slug}.md",
        f"{slug}.txt",
        f"{slug}.docx",
        f"{slug}-site.zip",
        f"{slug}-source.zip",
    ]


def pages_build(output_dir: str) -> None:
    """Assemble the GitHub Pages site: landing page, chapters, downloads."""

    root = booklib.root()
    out = root / output_dir
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    meta = booklib.metadata()
    template = (booklib.DATA / "web" / "index-template.html").read_text(encoding="utf-8")
    replacements = {
        "{{TITLE}}": meta["title"],
        "{{SUBTITLE}}": meta["subtitle"],
        "{{AUTHOR}}": ", ".join(meta["author"]),
        "{{DATE}}": meta["date"],
        "{{COPYRIGHT}}": meta["copyright"],
        "{{PUBLISHER}}": meta["publisher"],
        "{{PLACE}}": meta["publisher-place"],
        "{{REPO_URL}}": meta.get("repository", ""),
    }
    page = template
    for key, value in replacements.items():
        page = page.replace(key, value)
    (out / "index.html").write_text(page, encoding="utf-8")

    for optional in ("cover.jpg", "press-logo.png"):
        source = root / "assets" / optional
        if source.is_file():
            shutil.copy(source, out / optional)
    woodcuts = root / "assets" / "woodcuts"
    if woodcuts.is_dir():
        shutil.copytree(woodcuts, out / "woodcuts")
    shutil.copytree(root / "dist" / "site", out / "read")
    downloads = out / "downloads"
    downloads.mkdir()
    for name in download_names():
        source = root / "dist" / name
        if not source.exists():
            raise SystemExit(
                f"pages: {name} missing from dist; build it before pages "
                "(silent gaps in the public downloads are not allowed)"
            )
        shutil.copy(source, downloads / name)
    print(f"+ assembled pages site -> {output_dir}")


def build_target(target: str) -> None:
    if shutil.which("pandoc") is None:
        raise SystemExit("pandoc is required")
    slug = booklib.slug()
    if target == "pdf":
        pandoc_build("pdf", f"dist/{slug}.pdf")
    elif target == "epub":
        meta = booklib.metadata()
        rights = (
            f"{meta['copyright']} Published by {meta['publisher']}, "
            f"{meta['publisher-place']}."
        )
        pandoc_build("epub", f"dist/{slug}.epub", extra=["--metadata", f"rights={rights}"])
    elif target == "html":
        pandoc_build("html", f"dist/{slug}.html")
    elif target == "markdown":
        markdown_build(f"dist/{slug}.md")
    elif target == "site":
        site_build("dist/site")
    elif target == "pages":
        pages_build("dist/pages")
    elif target == "txt":
        pandoc_build("portable", f"dist/{slug}.txt", extra=["--to=plain", "--columns=80"])
    elif target == "docx":
        pandoc_build("portable", f"dist/{slug}.docx", extra=["--to=docx"])
    else:
        raise SystemExit(f"unknown build target: {target}")
