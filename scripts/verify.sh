#!/usr/bin/env bash
# The one pre-PR proof: the local-runnable half of what CI's quality gate
# checks, fast layers first so a cheap failure stops before an expensive one.
# It composes the existing tools; it does not reimplement their laws.
#
#   scripts/verify.sh          # the default ladder
#   scripts/verify.sh --quick  # stop after the fast lint/type/test layer
#
# What it does NOT run (CI-only, needs the container or a second identity):
# the integration gauntlet in the toolchain image, the consumer proof, and
# the live second-party proofs. Those run on push and on a release tag.
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n== %s\n' "$1"; }

step "lint, type, format, selftest, pytest (the CI battery)"
pre-commit run --all-files

if [ "${1:-}" = "--quick" ]; then
  echo "--quick: stopping before the ratchets and site build."
  exit 0
fi

step "per-module coverage floor"
# Never run coverage_ratchet.py --update locally: it re-measures on this
# machine and can inflate the committed baselines above CI's floor.
python3 scripts/coverage_ratchet.py

step "mutation score on the pure modules"
python3 scripts/mutation_ratchet.py

step "the documentation site builds and its checks pass"
python3 scripts/build_site.py >/dev/null

echo
echo "verify: OK. (CI additionally runs the container gauntlet and consumer proof.)"
