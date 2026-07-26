#!/usr/bin/env bash
#
# Run press inside the pinned toolchain container against a book, from a working
# checkout -- the developer harness for the exact bytes CI builds on.
#
# Why a container. The press needs LuaLaTeX, pandoc, the Libertine faces,
# epubcheck, and a Java that can run its jar -- a toolchain you rarely have all
# of locally, and never at the pinned versions. This mounts your checkout
# read-only, installs the locked Python deps into a cached layer, and runs
# `python -m press` straight from src/, so an edit to the source takes effect on
# the next run with no reinstall. Artifacts (and optional page previews) land in
# a host directory you can open.
#
# The toolchain image is read from .github/workflows/build.yml, so this always
# runs the same image the release contract pins: it cannot drift from CI.
#
# Usage:
#   scripts/dev-render.sh [TARGET ...] [options]
#
#   TARGET        one or more press targets (default: pdf). e.g. pdf epub web all
#   --book DIR    book repo to build (default: examples/alice-in-wonderland)
#   --out DIR     host dir for artifacts + previews (default: build/dev-render)
#   --preview[=N] after a pdf build, rasterise pages to JPEG at N dpi (default 120)
#   --shell       open an interactive shell in the container instead of building
#   -h, --help    this text
#
# Examples:
#   scripts/dev-render.sh                         # build Alice's PDF
#   scripts/dev-render.sh pdf --preview           # + JPEG page previews
#   scripts/dev-render.sh all --book ~/code/make-ready
#   scripts/dev-render.sh --shell                 # poke around the toolchain
#
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# The pinned toolchain image, lifted verbatim from the reusable workflow so this
# harness and CI can never disagree about which bytes they run.
image="$(sed -n 's/^[[:space:]]*image:[[:space:]]*//p' \
  "$repo/.github/workflows/build.yml" | head -n1)"
if [[ -z "$image" ]]; then
  echo "dev-render: could not read the toolchain image from build.yml" >&2
  exit 1
fi

targets=()
book="$repo/examples/alice-in-wonderland"
out="$repo/build/dev-render"
preview=""       # empty = off; otherwise a dpi
shell_only=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --book)   book="$2"; shift 2 ;;
    --book=*) book="${1#*=}"; shift ;;
    --out)    out="$2"; shift 2 ;;
    --out=*)  out="${1#*=}"; shift ;;
    --preview)     preview="120"; shift ;;
    --preview=*)   preview="${1#*=}"; shift ;;
    --shell)  shell_only="1"; shift ;;
    -h|--help)
      awk 'NR==1{next} /^#/{sub(/^# ?/,"");print;next} {exit}' "${BASH_SOURCE[0]}"
      exit 0 ;;
    -*) echo "dev-render: unknown option: $1" >&2; exit 2 ;;
    *)  targets+=("$1"); shift ;;
  esac
done
[[ ${#targets[@]} -eq 0 ]] && targets=(pdf)

book="$(cd "$book" 2>/dev/null && pwd)" || book=""
if [[ -z "$book" || ! -f "$book/config/metadata.yaml" ]]; then
  echo "dev-render: --book is not a press book (no config/metadata.yaml)" >&2
  exit 1
fi
mkdir -p "$out"

# Container-writable pip cache so the locked deps download once, not every run.
docker volume inspect press-dev-pipcache >/dev/null 2>&1 \
  || docker volume create press-dev-pipcache >/dev/null

echo "dev-render: image $image"
echo "dev-render: book  $book"
echo "dev-render: out   $out"

if [[ -n "$shell_only" ]]; then
  exec docker run --rm -it \
    -v "$repo":/src:ro -v "$book":/book:ro -v "$out":/out \
    -v press-dev-pipcache:/root/.cache/pip \
    -e PYTHONPATH=/src/src -e BOOK_ROOT=/work/book \
    "$image" bash -lc '
      pip install --break-system-packages -q -r /src/requirements-lock.txt
      cp -r /book /work/book 2>/dev/null || { mkdir -p /work && cp -r /book /work/book; }
      cd /work/book; echo "press is on PYTHONPATH; try: python3 -m press pdf"; exec bash'
fi

# The book mount is read-only (it is your checkout); copy it to a writable place
# inside the container, build there, then hand artifacts back through /out. src/
# stays read-only and live on PYTHONPATH -- no reinstall between edits.
docker run --rm \
  -v "$repo":/src:ro -v "$book":/book:ro -v "$out":/out \
  -v press-dev-pipcache:/root/.cache/pip \
  -e PYTHONPATH=/src/src \
  -e PRESS_TARGETS="${targets[*]}" \
  -e PRESS_PREVIEW="$preview" \
  "$image" bash -euo pipefail -c '
    pip install --break-system-packages -q -r /src/requirements-lock.txt
    mkdir -p /work && cp -r /book /work/book && cd /work/book
    export BOOK_ROOT=/work/book
    for t in $PRESS_TARGETS; do
      echo "── press $t ──"
      python3 -m press "$t"
    done
    rm -rf /out/dist && cp -r dist /out/dist
    if [[ -n "$PRESS_PREVIEW" ]]; then
      pdf="$(ls /out/dist/*.pdf 2>/dev/null | head -n1 || true)"
      if [[ -n "$pdf" ]]; then
        rm -rf /out/preview && mkdir -p /out/preview
        pdftoppm -jpeg -r "$PRESS_PREVIEW" "$pdf" /out/preview/pg
        echo "── previews: $(ls /out/preview/*.jpg | wc -l) pages at ${PRESS_PREVIEW}dpi ──"
      fi
    fi
  '

echo "dev-render: artifacts in $out/dist"
[[ -n "$preview" ]] && echo "dev-render: previews  in $out/preview"
