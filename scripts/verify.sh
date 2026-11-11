#!/usr/bin/env bash
# The one pre-PR proof: the local-runnable half of what CI's quality gate
# checks, fast layers first so a cheap failure stops before an expensive one.
# It composes the existing tools; it does not reimplement their laws.
#
#   scripts/verify.sh          # the default ladder (host-side)
#   scripts/verify.sh --quick  # stop after the fast lint/type/test layer
#   scripts/verify.sh --full   # also run CI's container gauntlet locally
#
# --full closes the local/CI gap: it runs the integration gauntlet in the
# pinned toolchain image (scripts/gauntlet.sh) so the "consumer" tier -- where
# rendered-artifact bugs surface -- is proven before you push, not 15 minutes
# later in CI. Native on Apple Silicon since the image went multi-arch (#206);
# needs Docker. Still CI/human-only even with --full: the live second-party
# proofs (a fork-PR from another account, a private book in another org).
set -euo pipefail
cd "$(dirname "$0")/.."

mode="${1:-}"

step() { printf '\n== %s\n' "$1"; }

step "lint, type, format, selftest, pytest (the CI battery)"
pre-commit run --all-files

if [ "$mode" = "--quick" ]; then
  echo "--quick: stopping before the ratchets and site build."
  exit 0
fi

step "the celebrimbor quality gate (surface, invariants, producers, known-bad, imports, impact, coverage, mutation, and press's domain checks)"
# Produce coverage first (celebrimbor.coverage measures a .coverage file, it does
# not run the suite). Never pass --update-baselines locally: it re-measures on
# this machine and can inflate the committed floors above CI's. The mutation
# ratchet runs inside the gate now, over press.mutation:survivors
# ([tool.celebrimbor] mutation_survivors); there is no separate script.
python3 -m pytest -q -p no:cacheprovider --cov=press --cov-report=
celebrimbor gate

step "the Lua filter coverage ratchet"
if command -v pandoc >/dev/null 2>&1; then
  PRESS_LUA_COV_DIR="$(mktemp -d)"
  export PRESS_LUA_COV_DIR
  python3 -m pytest -q -p no:cacheprovider \
    tests/test_figure_numbering_filter.py tests/test_figure_placement.py \
    tests/test_set_pieces.py tests/test_scene_break.py tests/test_dropcaps_filter.py \
    tests/test_typographic_spacing.py tests/test_print_safe_images_filter.py
  python3 scripts/lua_coverage_ratchet.py check --cov-dir "$PRESS_LUA_COV_DIR"
  unset PRESS_LUA_COV_DIR
else
  echo "lua coverage: pandoc absent, skipped (CI enforces it)"
fi

step "the documentation site builds and its checks pass"
python3 scripts/build_site.py >/dev/null

if [ "$mode" = "--full" ]; then
  step "the integration gauntlet in the pinned toolchain image"
  scripts/gauntlet.sh
  echo
  echo "verify --full: OK. (Only the live second-party proofs remain CI/human-only.)"
  exit 0
fi

echo
echo "verify: OK. (Run --full to also prove the container gauntlet; CI runs it and"
echo "the live second-party proofs on push and on a release tag.)"
