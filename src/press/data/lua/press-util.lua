-- Pure helpers shared by the pandoc Lua filters: the figure measure vocabulary
-- and small predicates. No pandoc-AST dependency, so they are unit-tested under
-- plain Lua (tests/lua/test_press_util.lua via `pandoc lua`); the AST-shaping
-- stays in the filters, integration-tested through pandoc. Filters load this
-- with a PANDOC_SCRIPT_FILE-relative package.path (see each filter's preamble).
-- docs/LUA-QUALITY-PLAN.md §4.

local M = {}

-- A relative width measure -> the graphics width option, against the line.
M.MEASURE_WIDTH = {
  ["full-measure"] = "\\linewidth",
  ["half-measure"] = "0.5\\linewidth",
  ["third-measure"] = "0.3333\\linewidth",
}

-- The same, as a pandoc width value other writers understand.
M.MEASURE_PERCENT = {
  ["full-measure"] = "100%",
  ["half-measure"] = "50%",
  ["third-measure"] = "33%",
}

-- Roughly how many text lines tall a wrapped figure at each measure is: a plate
-- is about square, so a fraction of the line width is that fraction of the text
-- block's ~24 lines, plus a couple for the caption. A wrap needs at least this
-- many lines left on the page; short of them \Needspace moves the whole wrap to
-- the next page instead of letting it hang off the foot with too few lines to
-- close under it. A shade under square, so a wide-short plate is not over-moved.
M.MEASURE_GUARD = {
  ["full-measure"] = 20,
  ["half-measure"] = 13,
  ["third-measure"] = 9,
}

-- A house boolean attribute: "true"/"yes"/"1" (any case) reads true, else false.
function M.is_true(v)
  v = tostring(v or ""):lower()
  return v == "true" or v == "yes" or v == "1"
end

-- The LaTeX \includegraphics width option for a declared width, or "".
function M.width_opt(width)
  if not width or width == "" then
    return ""
  end
  if M.MEASURE_WIDTH[width] then
    return ",width=" .. M.MEASURE_WIDTH[width]
  end
  local pct = width:match("^(%d+)%%$")
  if pct then
    return ",width=" .. (tonumber(pct) / 100) .. "\\linewidth"
  end
  return ",width=" .. width -- a raw length passes through unchanged
end

return M
