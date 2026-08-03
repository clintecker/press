#!/usr/bin/env bash
# The Lua linter: selene over the pandoc filters -- undefined globals, unused
# locals, shadowing, redundant branches -- configured by selene.toml + the
# pandoc std in pandoc.yml. A single static binary, no Lua toolchain.
#
# No-op when selene is absent (a dev box may lack it); CI installs it before the
# pre-commit run and the toolchain image will carry it. Lua-quality M1 §3.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v selene >/dev/null 2>&1; then
  echo "lua-lint: selene absent, skipping (CI installs and enforces it)"
  exit 0
fi

selene src/press/data/lua/
