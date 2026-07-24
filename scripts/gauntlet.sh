#!/usr/bin/env bash
# Run CI's integration gauntlet locally, before you push.
#
# `scripts/verify.sh` proves everything host-side (lint, type, selftest,
# pytest, the ratchets, the site build) but explicitly NOT the container
# gauntlet -- the "consumer" tier where rendered-artifact bugs surface (a
# dropped cover, an unembedded font, a failed epubcheck). That tier only ran
# in CI, a ~15-minute round-trip after pushing.
#
# This script runs those same steps in a local `docker run` of the toolchain
# image build.yml pins: build the wheel, install it, scaffold a stranger's
# book, run the whole `press all`, prove no original identity leaks, and prove
# tampering turns the verifier red. It mirrors .github/workflows/integration.yml
# step for step; when this proves out, that workflow should call this script so
# the two cannot drift.
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

# The repo is mounted read-only; every mutation happens under /tmp in the
# container, so the host tree is never touched. The steps below are
# integration.yml's consumer job, minus the CI-only trust-receipt emit.
docker run --rm --platform "$platform" -v "$REPO":/src:ro "$image" \
  bash -euo pipefail -c '
    echo "-- build and install the wheel"
    python3 -m pip install --break-system-packages --no-cache-dir -q build
    # Copy the source out of the read-only mount to build from, excluding .git
    # (its fsmonitor sockets are uncopyable) and the heavy local-only dirs. The
    # version is hardcoded in pyproject, so the build needs no git metadata.
    mkdir -p /tmp/press-src
    tar -C /src --exclude=.git --exclude=.venv --exclude=build --exclude=dist \
        --exclude=.pytest_cache --exclude=.mypy_cache -cf - . | tar -C /tmp/press-src -xf -
    python3 -m build --wheel --outdir /tmp/wheels /tmp/press-src >/dev/null
    python3 -m pip install --break-system-packages -q /tmp/wheels/press-*.whl

    echo "-- wheel carries the package data"
    cd /tmp
    test "$(press skills | wc -l)" -ge 8
    press workflows | grep -q editorial-passes
    python3 -c "import press.aesthetic, pathlib; assert pathlib.Path(press.aesthetic.HOUSE).is_file()"

    echo "-- scaffold a stranger book"
    press new gate-proof --author "Gate Proof" --publisher "Gate Press" --place "Nowhere"
    cd gate-proof
    git init -q && git add -A
    python3 - <<PY
import pathlib
p = pathlib.Path("config/metadata.yaml")
p.write_text(p.read_text().replace(
    "verify-sentinels: []",
    "verify-sentinels:\n  - \"the gate remembers what it refused\"",
))
c = pathlib.Path("book/chapters/00-preface.md")
c.write_text(c.read_text() + "\n\nEvery build ends the same way: "
             "the gate remembers what it refused.\n")
PY

    echo "-- the whole gauntlet (press all)"
    press all

    echo "-- no original-book identity in public artifacts"
    ! grep -ri "mostly done\|mostly-done" dist/pages dist/site

    echo "-- tampering turns the verifier red"
    rm dist/pages/downloads/gate-proof.pdf
    if python3 -c "from press import verify_pages; raise SystemExit(verify_pages.main())" >/dev/null 2>&1; then
      echo "verifier blessed a tampered site" && exit 1
    fi
    echo "verifier refused the tampered site, as it must"
  '

echo "== gauntlet: OK ($image on $platform)"
