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

-- Set-piece geometry (docs/LUA-QUALITY-PLAN.md §4). The AST-shaping stays in
-- set-pieces.lua; only the pure numbers live here.

M.CASCADE_STEP = 2.4 -- em added per cascade line

-- The cascade indent (em) for the i-th line, 1-based: each line one step deeper.
function M.cascade_indent(i)
  return (i - 1) * M.CASCADE_STEP
end

M.TAIL_AMP = 3.0 -- em, the serpentine's horizontal swing

-- The LaTeX size ramp down a tail, from the head to the tip.
M.TAIL_SIZES = {
  "\\normalsize",
  "\\normalsize",
  "\\small",
  "\\small",
  "\\footnotesize",
  "\\footnotesize",
  "\\scriptsize",
  "\\scriptsize",
  "\\tiny",
}

-- The web font-size ramp down a tail, head to tip.
M.TAIL_WEB_SIZES = {
  "1em",
  "1em",
  "0.92em",
  "0.92em",
  "0.84em",
  "0.84em",
  "0.76em",
  "0.76em",
  "0.68em",
}

-- The serpentine tail's horizontal offset (em) and LaTeX size command for line
-- i of n: a sine swing, the size tapering head to tip.
function M.tail_ramp(i, n)
  local t = (i - 1) / math.max(n - 1, 1) -- 0 at the head, 1 at the tip
  local offset = M.TAIL_AMP * math.sin(t * 2 * math.pi)
  local size = M.TAIL_SIZES[math.min(#M.TAIL_SIZES, 1 + math.floor(t * #M.TAIL_SIZES))]
  return offset, size
end

-- The web font-size string for line i of n, tapering head to tip.
function M.tail_web_size(i, n)
  local idx = math.min(
    #M.TAIL_WEB_SIZES,
    1 + math.floor((i - 1) / math.max(n - 1, 1) * #M.TAIL_WEB_SIZES)
  )
  return M.TAIL_WEB_SIZES[idx]
end

return M
