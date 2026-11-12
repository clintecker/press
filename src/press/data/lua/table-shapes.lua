-- Shape-aware tables, at the document-tree layer.
--
-- A Markdown table is two different things wearing one syntax. A reference
-- list (a short key column, perhaps a short sub column, then one column of
-- prose) reads badly as a grid: the prose column is squeezed into a narrow
-- cell and wraps a word to a line. A true grid (every column short, read
-- across and down) reads badly as anything else. So the house reads the
-- table's shape from its cells and sets each by what it is:
--
--   ledger  a native DefinitionList inside Div.ledger: the key as the term,
--           a middle column (if any) as Div.ledger-sub, the prose as the
--           definition; the caption and the header legend ride above it in
--           Div.ledger-caption and Div.ledger-legend; LaTeX gets
--           \begin{PressLedger} ... \end{PressLedger} around the list.
--   grid    the Table kept, inside Div.grid, with every column given an
--           explicit relative width; LaTeX gets \PressGridBegin and
--           \PressGridEnd around it.
--
-- An author who disagrees wraps the table in a `::: ledger` or `::: grid`
-- fenced div, which forces the shape of every table inside it. A document with
-- no tables renders byte-for-byte as before.

-- The pure classifier (word_count, table_shape) lives in press-util.lua beside
-- this filter; load it by its own directory so `require` resolves whatever
-- working directory pandoc runs from. docs/LUA-QUALITY-PLAN.md section 4.
local here = (PANDOC_SCRIPT_FILE or ""):match("^(.*[/\\])") or "./"
package.path = here .. "?.lua;" .. package.path
local util = require("press-util")

local latex = FORMAT:match("latex") ~= nil

-- The narrowest share a grid column may take, so a short column never
-- collapses to a sliver beside a long one.
local MIN_SHARE = 0.12

-- The separator between header cells in a ledger's legend (a middle dot).
local LEGEND_SEP = " \u{00B7} "

-- The shape forced by the nearest enclosing `.ledger`/`.grid` div, or nil.
local forced = nil

-- The header rows (empty for a header-less table).
local function head_rows(tbl)
  return tbl.head.rows
end

-- The data rows: each body's intermediate head rows, then its body rows.
local function body_rows(tbl)
  local rows = {}
  for _, body in ipairs(tbl.bodies) do
    for _, row in ipairs(body.head) do
      rows[#rows + 1] = row
    end
    for _, row in ipairs(body.body) do
      rows[#rows + 1] = row
    end
  end
  return rows
end

-- A cell's words: each Code inline counts as one word however many tokens its
-- text holds, so a `press all` key is as short as a `hemingway` one.
local function cell_words(cell)
  local blocks = pandoc.Blocks(cell.contents):walk({
    Code = function()
      return pandoc.Str("X")
    end,
  })
  return util.word_count(pandoc.utils.stringify(blocks) or "")
end

local function cell_chars(cell)
  return utf8.len(pandoc.utils.stringify(cell.contents) or "") or 0
end

-- Per-column means of measure(cell) over the body rows.
local function column_means(rows, ncols, measure)
  local sums = {}
  for i = 1, ncols do
    sums[i] = 0
  end
  for _, row in ipairs(rows) do
    for i = 1, ncols do
      local cell = row.cells[i]
      if cell then
        sums[i] = sums[i] + measure(cell)
      end
    end
  end
  local means = {}
  for i = 1, ncols do
    means[i] = (#rows > 0) and (sums[i] / #rows) or 0
  end
  return means
end

local function cell_inlines(cell)
  return pandoc.utils.blocks_to_inlines(cell and cell.contents or {})
end

local function is_blank(cell)
  return cell == nil or pandoc.utils.stringify(cell.contents) == ""
end

-- The legend: the last header row's cells joined by a middle dot, or nil when
-- the table has no header row or the header is blank.
local function legend(tbl)
  local rows = head_rows(tbl)
  local row = rows[#rows]
  if not row then
    return nil
  end
  local out = pandoc.Inlines({})
  local any = false
  for _, cell in ipairs(row.cells) do
    if not is_blank(cell) then
      if any then
        out:insert(pandoc.Str(LEGEND_SEP))
      end
      out:extend(cell_inlines(cell))
      any = true
    end
  end
  return any and out or nil
end

local function classed(blocks, class)
  return pandoc.Div(blocks, pandoc.Attr("", { class }))
end

-- A Plain promoted to a Para, so merged continuation blocks stay paragraphs.
local function as_paras(blocks)
  local out = pandoc.Blocks({})
  for _, b in ipairs(blocks) do
    if b.t == "Plain" then
      out:insert(pandoc.Para(b.content))
    else
      out:insert(b)
    end
  end
  return out
end

-- The middle cells (between key and prose) as one Div.ledger-sub, or nil.
local function sub_block(row, ncols)
  local inl = pandoc.Inlines({})
  for i = 2, ncols - 1 do
    local cell = row.cells[i]
    if not is_blank(cell) then
      if #inl > 0 then
        inl:insert(pandoc.Str(LEGEND_SEP))
      end
      inl:extend(cell_inlines(cell))
    end
  end
  if #inl == 0 then
    return nil
  end
  return classed({ pandoc.Para(inl) }, "ledger-sub")
end

local function to_ledger(tbl, ncols)
  local items = {}
  for _, row in ipairs(body_rows(tbl)) do
    local defn = pandoc.Blocks({})
    local sub = sub_block(row, ncols)
    if sub then
      defn:insert(sub)
    end
    local prose = row.cells[ncols]
    if prose then
      -- Beside a sub block the prose is a paragraph of its own, not bare text.
      defn:extend(sub and as_paras(prose.contents) or prose.contents)
    end
    local last = items[#items]
    if is_blank(row.cells[1]) and last then
      -- An empty key continues the previous entry: its blocks join the same
      -- definition as further paragraphs.
      local merged = as_paras(last[2][1])
      merged:extend(as_paras(defn))
      last[2][1] = merged
    else
      items[#items + 1] = { cell_inlines(row.cells[1]), { defn } }
    end
  end
  local blocks = {}
  local caption = pandoc.utils.blocks_to_inlines(tbl.caption.long or {})
  if #caption > 0 then
    blocks[#blocks + 1] = classed({ pandoc.Para(caption) }, "ledger-caption")
  end
  local leg = legend(tbl)
  if leg then
    blocks[#blocks + 1] = classed({ pandoc.Para(leg) }, "ledger-legend")
  end
  if latex then
    blocks[#blocks + 1] = pandoc.RawBlock("latex", "\\begin{PressLedger}")
  end
  blocks[#blocks + 1] = pandoc.DefinitionList(items)
  if latex then
    blocks[#blocks + 1] = pandoc.RawBlock("latex", "\\end{PressLedger}")
  end
  return classed(blocks, "ledger")
end

-- Each column's share of the measure: its mean character length's share,
-- floored at MIN_SHARE, then normalised so the shares sum to 1.
local function shares(rows, ncols)
  local means = column_means(rows, ncols, cell_chars)
  local total = 0
  for i = 1, ncols do
    total = total + means[i]
  end
  local out, sum = {}, 0
  for i = 1, ncols do
    local share = (total > 0) and (means[i] / total) or (1 / ncols)
    out[i] = math.max(MIN_SHARE, share)
    sum = sum + out[i]
  end
  for i = 1, ncols do
    out[i] = out[i] / sum
  end
  return out
end

local function to_grid(tbl, ncols)
  local w = shares(body_rows(tbl), ncols)
  local specs = {}
  for i, spec in ipairs(tbl.colspecs) do
    specs[i] = { spec[1], w[i] }
  end
  tbl.colspecs = specs
  local blocks = {}
  if latex then
    blocks[#blocks + 1] = pandoc.RawBlock("latex", "\\PressGridBegin")
  end
  blocks[#blocks + 1] = tbl
  if latex then
    blocks[#blocks + 1] = pandoc.RawBlock("latex", "\\PressGridEnd")
  end
  return classed(blocks, "grid")
end

local function shape_of(tbl, ncols)
  if forced == "ledger" and ncols >= 2 then
    return "ledger"
  elseif forced then
    return "grid"
  end
  return util.table_shape(ncols, column_means(body_rows(tbl), ncols, cell_words))
end

local shaper
shaper = {
  traverse = "topdown",
  Div = function(div)
    local shape = (div.classes:includes("ledger") and "ledger")
      or (div.classes:includes("grid") and "grid")
    if not shape then
      return nil -- an ordinary div (an admonition): walk on into it
    end
    local saved = forced
    forced = shape
    div.content = div.content:walk(shaper)
    forced = saved
    return div, false
  end,
  Table = function(tbl)
    local ncols = #tbl.colspecs
    if shape_of(tbl, ncols) == "ledger" then
      return to_ledger(tbl, ncols), false
    end
    -- The wrapper is not walked again, or its own `.grid` class would read
    -- as a forcing div.
    return to_grid(tbl, ncols), false
  end,
}

function Pandoc(doc)
  return doc:walk(shaper)
end
