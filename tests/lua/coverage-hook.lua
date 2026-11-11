-- The Lua filter coverage hook (tests/lua_coverage.py inlines this into a
-- per-filter shim when PRESS_LUA_COV_DIR is set). It records every line pandoc
-- executes in a source under PRESS_LUA_DIR, runs the real filter, and appends
-- the hits to a fresh hits-*.tsv when the document finishes. The real filter's
-- return values pass through untouched, so rendered output is byte-identical.
--
-- The generator replaces the `...` on the next line with three Lua string
-- literals (the filters directory with a trailing separator, the real filter,
-- the hits directory); the line count is unchanged.
local PRESS_LUA_DIR, PRESS_REAL_FILTER, PRESS_COV_DIR = ...

-- The shim's own chunk is never a hit, even when it lives under PRESS_LUA_DIR.
local self_source = debug.getinfo(1, "S").source
local hits = {}

debug.sethook(function(_, line)
  -- `.source` is "@<path>" as loaded; `short_src` truncates long paths to
  -- "...<tail>", which would never match the absolute PRESS_LUA_DIR prefix.
  local source = debug.getinfo(2, "S").source
  if source == self_source or source:sub(1, 1) ~= "@" then
    return
  end
  local path = source:sub(2)
  if path:sub(1, #PRESS_LUA_DIR) == PRESS_LUA_DIR then
    local seen = hits[path]
    if not seen then
      seen = {}
      hits[path] = seen
    end
    seen[line] = true
  end
end, "l")

-- A filter finds its siblings (press-util.lua) by PANDOC_SCRIPT_FILE's
-- directory; point it at the real filter, not this shim. The pandoc std marks
-- the global read-only for filters; this harness is the one place that sets it.
-- selene: allow(incorrect_standard_library_use)
PANDOC_SCRIPT_FILE = PRESS_REAL_FILTER
dofile(PRESS_REAL_FILTER)

local function write_hits()
  -- os.tmpname creates the file, so its basename is unique among concurrent
  -- pandoc runs for as long as it exists; remove it only after the write.
  local reservation = os.tmpname()
  local unique = reservation:match("[^/\\]+$")
  local name = PRESS_COV_DIR .. "/hits-" .. unique .. "-" .. os.time() .. ".tsv"
  local fh = assert(io.open(name, "w"))
  for path, lines in pairs(hits) do
    local base = path:match("[^/\\]+$")
    for ln in pairs(lines) do
      fh:write(base, "\t", ln, "\n")
    end
  end
  fh:close()
  os.remove(reservation)
end

local real_pandoc = Pandoc
function Pandoc(doc)
  local out = doc
  if real_pandoc then
    -- pandoc treats a nil return as "unchanged", so nil maps back to doc.
    out = real_pandoc(doc)
    if out == nil then
      out = doc
    end
  end
  -- Lua's zero-argument form clears the hook; selene's std wrongly requires two.
  -- selene: allow(incorrect_standard_library_use)
  debug.sethook()
  write_hits()
  return out
end
