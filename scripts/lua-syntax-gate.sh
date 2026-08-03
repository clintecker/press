#!/usr/bin/env bash
# The Lua syntax gate: compile every filter with pandoc's own Lua 5.4, so a
# typo -- a stray non-ASCII byte in a comment, an unclosed string -- fails at
# commit instead of deep in a LuaLaTeX run. Uses `pandoc lua`, no extra install.
#
# No-op when pandoc is absent (a dev box may lack it); the toolchain image ships
# pandoc and CI runs the same check as a hard gate (tests/test_lua_compiles.py).
# Part of the Lua-quality M1 gates (docs/LUA-QUALITY-PLAN.md §1).
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v pandoc >/dev/null 2>&1; then
  echo "lua-syntax-gate: pandoc absent, skipping (the CI toolchain enforces it)"
  exit 0
fi

status=0
for f in src/press/data/lua/*.lua; do
  if ! err=$(pandoc lua -e "assert(loadfile(arg[1]))" -- "$f" 2>&1); then
    echo "Lua syntax error in $f:"
    echo "$err"
    status=1
  fi
done
exit "$status"
