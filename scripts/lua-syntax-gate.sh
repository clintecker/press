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
# loadfile COMPILES without running, so this catches syntax errors without
# executing a filter's top-level code (a filter may `require` a sibling module
# by a package.path only pandoc sets when it runs the filter). The path goes
# through the environment, not a positional arg -- `pandoc lua -e CODE -- FILE`
# would run CODE and then execute FILE as a script.
for f in src/press/data/lua/*.lua; do
  if ! err=$(LUA_SYNTAX_FILE="$f" pandoc lua -e 'assert(loadfile(os.getenv("LUA_SYNTAX_FILE")))' 2>&1); then
    echo "Lua syntax error in $f:"
    echo "$err"
    status=1
  fi
done
exit "$status"
