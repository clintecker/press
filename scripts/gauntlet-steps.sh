#!/usr/bin/env bash
# The integration gauntlet, run INSIDE the toolchain container: build the wheel,
# scaffold a stranger's book, run the whole `press all`, prove no original
# identity leaks, and prove tampering turns the verifier red.
#
# Two callers run this identical script, so CI and local cannot drift:
#   - .github/workflows/integration.yml runs it directly (its job IS the
#     container), then emits the CI-only trust receipt.
#   - scripts/gauntlet.sh runs it via `docker run` of the pinned image, so a
#     developer gets the same verdict locally before pushing.
#
# Arg 1 is the press source tree (default the current directory). Everything
# else happens under /tmp, so the source is only read, never written.
set -euo pipefail

src="$(cd "${1:-.}" && pwd)"

echo "-- build and install the wheel"
python3 -m pip install --break-system-packages --no-cache-dir -q build
# Build from a copy that excludes .git (its fsmonitor sockets are uncopyable)
# and the heavy local-only dirs. The version is hardcoded in pyproject, so the
# build needs no git metadata.
rm -rf /tmp/press-src && mkdir -p /tmp/press-src
tar -C "$src" --exclude=.git --exclude=.venv --exclude=build --exclude=dist \
    --exclude=.pytest_cache --exclude=.mypy_cache -cf - . | tar -C /tmp/press-src -xf -
python3 -m build --wheel --outdir /tmp/wheels /tmp/press-src >/dev/null
# Runtime dependencies from the hash-pinned lock (#194: immutable identities),
# then press itself with --no-deps so nothing is resolved fresh from PyPI.
python3 -m pip install --break-system-packages -q --require-hashes -r "$src/requirements-lock.txt"
python3 -m pip install --break-system-packages -q --no-deps /tmp/wheels/press-*.whl

echo "-- wheel carries the package data"
cd /tmp
test "$(press skills | wc -l)" -ge 8
press workflows | grep -q editorial-passes
python3 -c "import press.aesthetic, pathlib; assert pathlib.Path(press.aesthetic.HOUSE).is_file()"

echo "-- scaffold a stranger book"
cd /tmp
rm -rf gate-proof
press new gate-proof --author "Gate Proof" --publisher "Gate Press" --place "Nowhere"
cd gate-proof
git init -q && git add -A
python3 - <<'PY'
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
# A bare `! grep ...` under set -e does NOT fail the build (errexit is disabled
# for a !-negated command), so an if-block is used: a leak must turn it red.
if grep -ri "mostly done\|mostly-done" dist/pages dist/site; then
  echo "original-book identity leaked into public artifacts" && exit 1
fi

echo "-- tampering turns the verifier red"
rm dist/pages/downloads/gate-proof.pdf
if python3 -c "from press import verify_pages; raise SystemExit(verify_pages.main())" >/dev/null 2>&1; then
  echo "verifier blessed a tampered site" && exit 1
fi
echo "verifier refused the tampered site, as it must"
