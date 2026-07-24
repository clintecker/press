#!/usr/bin/env bash
# Run CI's integration gauntlet locally, before you push.
#
# `scripts/verify.sh` proves everything host-side (lint, type, selftest,
# pytest, the ratchets, the site build) but explicitly NOT the container
# gauntlet -- the "consumer" tier where rendered-artifact bugs surface (a
# dropped cover, an unembedded font, a failed epubcheck). That tier only ran
# in CI, a ~15-minute round-trip after pushing.
#
# This runs that gauntlet in a local `docker run` of the toolchain image
# build.yml pins. The gauntlet body is scripts/gauntlet-steps.sh -- the one
# script .github/workflows/integration.yml runs too (its job is already in the
# container), so the local and CI gauntlets cannot drift.
#
# Native on Apple Silicon since the toolchain image went multi-arch (#206):
# no qemu, no exit-247. Usage:
#
#   scripts/gauntlet.sh                 # pinned image, auto-detected platform
#   scripts/gauntlet.sh IMAGE           # a specific image
#   scripts/gauntlet.sh IMAGE PLATFORM  # e.g. linux/amd64 to match CI exactly
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$PWD"

command -v docker >/dev/null 2>&1 || {
  echo "gauntlet: docker is not available; the container tier cannot run locally." >&2
  echo "gauntlet: (CI still runs it. Install/start Docker to close the gap here.)" >&2
  exit 2
}

# The image consumers actually receive: the sha build.yml pins, resolved the
# same way integration.yml's `resolve` job does.
image="${1:-}"
if [ -z "$image" ]; then
  image=$(grep -oE 'ghcr.io/clintecker/press-toolchain:sha-[0-9a-f]+@sha256:[0-9a-f]{64}' \
            .github/workflows/build.yml | head -1)
  test -n "$image" || { echo "gauntlet: build.yml pins no toolchain @sha256 digest"; exit 1; }
fi

# Native platform by default; pass linux/amd64 to reproduce CI byte-for-byte.
platform="${2:-}"
if [ -z "$platform" ]; then
  case "$(uname -m)" in
    arm64|aarch64) platform="linux/arm64" ;;
    x86_64|amd64)  platform="linux/amd64" ;;
    *)             platform="linux/amd64" ;;
  esac
fi

echo "== gauntlet: $image on $platform"

# The repo is mounted read-only at /src; scripts/gauntlet-steps.sh does the whole
# gauntlet under /tmp, so the host tree is never touched. CI runs that same
# script directly (integration.yml's job is already in the container), so the
# local and CI gauntlets are one script and cannot drift.
docker run --rm --platform "$platform" -v "$REPO":/src:ro "$image" \
  bash /src/scripts/gauntlet-steps.sh /src

echo "== gauntlet: OK ($image on $platform)"
