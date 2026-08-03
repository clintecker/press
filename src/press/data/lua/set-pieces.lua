-- Set-piece typographic forms, at the document-tree layer.
--
-- Some passages are not prose and not a plain figure: a staggered address, a
-- stanza of verse, a poem shaped like a mouse's tail. Markdown cannot express
-- their geometry, and no author should hand-set coordinates that then rot in
-- one edition. Instead the author writes plain lines in a fenced div and the
-- house lays the geometry, projecting it into every format:
--
--   ::: cascade   a staircase -- an address, an inscription, a signature block
--   ::: verse     a stanza set in the house verse measure
--   ::: tail      a serpentine calligram computed from the verse's own lines
--
-- The body is an ordinary line block (`| line`), so the words stay live,
-- searchable, and accessible, and the plain-text edition shows them as verse.
-- A book that uses none of these renders byte-for-byte as before.

local CASCADE_STEP = 2.4 -- em added per cascade line
local VERSE_INDENT = "3em" -- the verse block's left inset
local TAIL_AMP = 3.0 -- em, the serpentine's horizontal swing
-- The size ramp down a tail, from the head to the tip.
local TAIL_SIZES = {
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

-- Only html and epub carry the styled geometry; every other writer (markdown,
-- plain text, docx) gets a clean native line block instead of the fenced divs
-- and inline styles the html projection would otherwise leak into the source.
local function is_web()
  return FORMAT:match("html") ~= nil or FORMAT:match("epub") ~= nil
end

-- The lines of a set-piece: a line block's lines, else each Para/Plain as one.
local function get_lines(div)
  for _, blk in ipairs(div.content) do
    if blk.t == "LineBlock" then
      return blk.content
    end
  end
  local lines = {}
  for _, blk in ipairs(div.content) do
    if blk.t == "Para" or blk.t == "Plain" then
      lines[#lines + 1] = blk.content
    end
  end
  return lines
end

local function with_tail(inlines, extra)
  local out = {}
  for _, il in ipairs(inlines) do
    out[#out + 1] = il
  end
  for _, il in ipairs(extra) do
    out[#out + 1] = il
  end
  return out
end

-- ::: cascade -- each line indented one step more than the last.
local function cascade(lines)
  if FORMAT:match("latex") then
    local out = { pandoc.RawBlock("latex", "\\par\\addvspace{0.7em}") }
    for i, line in ipairs(lines) do
      local pre = pandoc.RawInline(
        "latex",
        string.format("\\noindent\\hspace*{%.2fem}", (i - 1) * CASCADE_STEP)
      )
      out[#out + 1] = pandoc.Plain(
        with_tail({ pre }, with_tail(line, { pandoc.RawInline("latex", "\\par") }))
      )
    end
    out[#out + 1] = pandoc.RawBlock("latex", "\\addvspace{0.7em}")
    return out
  end
  if not is_web() then
    return pandoc.LineBlock(lines)
  end
  local items = {}
  for i, line in ipairs(lines) do
    items[#items + 1] = pandoc.Div(
      pandoc.Plain(line),
      pandoc.Attr(
        "",
        { "cascade-line" },
        { { "style", string.format("padding-left:%.1fem", (i - 1) * CASCADE_STEP) } }
      )
    )
  end
  return pandoc.Div(items, pandoc.Attr("", { "cascade" }))
end

-- ::: verse -- the house verse measure; opening quotes hang via protrusion.
local function verse(lines)
  -- Join the lines with LineBreak into ONE block: pandoc renders separate
  -- Plain blocks as separate paragraphs, and a \\ across paragraphs is "no line
  -- here to end". A LineBreak is \\ in LaTeX and <br> on the web; a blank source
  -- line adds a second break, the stanza gap.
  local inl = {}
  local first, gap = true, false
  for _, line in ipairs(lines) do
    if #line == 0 then
      gap = true
    else
      if not first then
        inl[#inl + 1] = pandoc.LineBreak()
        if gap then
          inl[#inl + 1] = pandoc.LineBreak()
        end
      end
      for _, il in ipairs(line) do
        inl[#inl + 1] = il
      end
      first, gap = false, false
    end
  end
  if FORMAT:match("latex") then
    return {
      pandoc.RawBlock("latex", "\\begin{PressVerse}"),
      pandoc.Plain(inl),
      pandoc.RawBlock("latex", "\\end{PressVerse}"),
    }
  end
  if not is_web() then
    return pandoc.LineBlock(lines)
  end
  return pandoc.Div(pandoc.Plain(inl), pandoc.Attr("", { "verse" }))
end

-- ::: tail -- a serpentine: a sine-driven horizontal offset per line, the size
-- tapering from head to tip. The calligram computed from ordinary verse lines,
-- not coordinates in the manuscript.
local function tail(lines)
  local n = #lines
  local function ramp(i)
    local t = (i - 1) / math.max(n - 1, 1) -- 0 at the head, 1 at the tip
    local offset = TAIL_AMP * math.sin(t * 2 * math.pi)
    local size = TAIL_SIZES[math.min(#TAIL_SIZES, 1 + math.floor(t * #TAIL_SIZES))]
    return offset, size
  end
  if FORMAT:match("latex") then
    local out = { pandoc.RawBlock("latex", "\\par\\addvspace{1.1em}\\begin{center}") }
    for i, line in ipairs(lines) do
      local offset, size = ramp(i)
      local pre =
        pandoc.RawInline("latex", string.format("\\hspace*{%.2fem}{%s ", offset, size))
      out[#out + 1] = pandoc.Plain(
        with_tail({ pre }, with_tail(line, { pandoc.RawInline("latex", "}\\par") }))
      )
    end
    out[#out + 1] = pandoc.RawBlock("latex", "\\end{center}\\addvspace{1.1em}")
    return out
  end
  if not is_web() then
    return pandoc.LineBlock(lines)
  end
  local items = {}
  local pct = {
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
  for i, line in ipairs(lines) do
    local offset, _ = ramp(i)
    local sz = pct[math.min(#pct, 1 + math.floor((i - 1) / math.max(n - 1, 1) * #pct))]
    items[#items + 1] = pandoc.Div(
      pandoc.Plain(line),
      pandoc.Attr(
        "",
        { "tail-line" },
        { { "style", string.format("margin-left:%.2fem;font-size:%s", offset, sz) } }
      )
    )
  end
  return pandoc.Div(items, pandoc.Attr("", { "tail" }))
end

function Div(el)
  if el.classes:includes("cascade") then
    return cascade(get_lines(el))
  end
  if el.classes:includes("verse") then
    return verse(get_lines(el))
  end
  if el.classes:includes("tail") then
    return tail(get_lines(el))
  end
  return nil
end
