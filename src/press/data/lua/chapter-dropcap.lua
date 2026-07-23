-- Chapter-opening drop caps, at the document-tree layer.
--
-- The press decides the initial, not the author: this filter walks the pandoc
-- AST, finds the first eligible prose paragraph after each level-1 (chapter)
-- heading, and rewrites its opening word into a dropped initial. For LaTeX it
-- emits \PressDropCap{I}{he} (the style is defined centrally in the generated
-- TeX layer); for HTML and EPUB it emits semantic spans the stylesheet turns
-- into a floated initial. The extraction mirrors src/press/dropcaps.py: a
-- grapheme initial (base letter plus combining marks), leading punctuation
-- kept with it, and the remainder of the first word set apart.
--
-- When the style is "none" (the default) the filter is a no-op, so a book
-- that does not opt in renders byte-for-byte as before.

local settings = { style = "none", lines = 3, depth = 0, small_caps = true }

-- Leading punctuation a drop cap keeps in front of its initial.
local LEAD = {}
for _, cp in ipairs({
  0x22, 0x27, 0x60,                 -- " ' `
  0x2018, 0x2019, 0x201C, 0x201D,   -- curly quotes
  0x00AB, 0x00BB, 0x2039, 0x203A,   -- guillemets
  0x2014, 0x2013, 0x2012, 0x2010, 0x2D,  -- dashes and hyphen
  0x00BF, 0x00A1,                   -- inverted marks
}) do LEAD[cp] = true end

-- Codepoint ranges of combining marks, so an accent rides with its base
-- letter into the initial grapheme.
local function is_combining(cp)
  return (cp >= 0x0300 and cp <= 0x036F)
      or (cp >= 0x1AB0 and cp <= 0x1AFF)
      or (cp >= 0x1DC0 and cp <= 0x1DFF)
      or (cp >= 0x20D0 and cp <= 0x20FF)
      or (cp >= 0xFE20 and cp <= 0xFE2F)
end

local function is_space(cp)
  return cp == 0x20 or cp == 0x09 or cp == 0x0A or cp == 0x0D or cp == 0xA0
end

-- Split a UTF-8 string into lead / initial grapheme / remainder-of-word /
-- rest, mirroring dropcaps.split_initial. Returns nil when there is no letter
-- to drop (so the caller leaves the paragraph untouched).
local function split_initial(s)
  local cps = {}
  for _, c in utf8.codes(s) do cps[#cps + 1] = c end
  local n = #cps
  local i = 1
  -- leading whitespace is dropped
  while i <= n and is_space(cps[i]) do i = i + 1 end
  local lead_start = i
  while i <= n and LEAD[cps[i]] do i = i + 1 end
  local lead_end = i - 1
  if i > n then return nil end
  -- the initial must be a real character, not punctuation like an ellipsis
  local first = cps[i]
  if LEAD[first] or is_space(first) then return nil end
  local init_start = i
  i = i + 1
  while i <= n and is_combining(cps[i]) do i = i + 1 end
  local init_end = i - 1
  -- remainder of the first word
  local word_start = i
  while i <= n and not is_space(cps[i]) do i = i + 1 end
  local word_end = i - 1
  local rest_start = i

  local function slice(a, b)
    if a > b then return "" end
    return utf8.char(table.unpack(cps, a, b))
  end
  return {
    lead = slice(lead_start, lead_end),
    initial = slice(init_start, init_end),
    word = slice(word_start, word_end),
    rest = slice(rest_start, n),
  }
end

-- Blocks that are not the opening prose paragraph: an epigraph, a figure, a
-- rule, a list, a table, code. The opener is the first Para past these.
local SKIP = {
  BlockQuote = true, CodeBlock = true, BulletList = true,
  OrderedList = true, DefinitionList = true, Table = true,
  HorizontalRule = true, Figure = true,
}

-- The first inline that carries text, diving one level into an emphasis span
-- so a paragraph that opens in italics still gets its initial. Returns the Str
-- element and the list it lives in, or nil.
local function first_text(inlines)
  local head = inlines[1]
  if head == nil then return nil end
  if head.t == "Str" then return head, inlines end
  -- Dive one level into an emphasis span or a quotation: a paragraph that
  -- opens in italics or inside quotation marks still gets its initial, and
  -- the wrapper (the emphasis, the quote glyphs) renders around it. `smart`
  -- turns a straight opening quote into a Quoted node, so this is the common
  -- real-manuscript case, not an edge one.
  if (head.t == "Emph" or head.t == "Strong" or head.t == "Span"
      or head.t == "Quoted")
      and head.content and head.content[1] and head.content[1].t == "Str" then
    return head.content[1], head.content
  end
  return nil
end

local function drop_inlines(parts)
  -- The initial (with any leading punctuation) and the word remainder, as
  -- format-specific inlines.
  local head = parts.lead .. parts.initial
  if FORMAT:match("latex") then
    return { pandoc.RawInline("latex",
      "\\PressDropCap{" .. head .. "}{" .. parts.word .. "}") }
  end
  local cap = pandoc.Span(pandoc.Str(head), pandoc.Attr("", { "drop-cap" }))
  local out = { cap }
  if parts.word ~= "" then
    out[#out + 1] = pandoc.Span(pandoc.Str(parts.word),
      pandoc.Attr("", { "opening-word-rest" }))
  end
  return out
end

local function transform(para)
  local str, list = first_text(para.content)
  if str == nil then return para end
  local parts = split_initial(str.text)
  if parts == nil then return para end

  -- Replace the leading Str with the drop-cap inlines plus the tail of its
  -- own text, in place, so surrounding inlines (and any emphasis wrapper) are
  -- preserved.
  local replacement = drop_inlines(parts)
  if parts.rest ~= "" then replacement[#replacement + 1] = pandoc.Str(parts.rest) end
  list[1] = nil
  local rebuilt = {}
  for _, el in ipairs(replacement) do rebuilt[#rebuilt + 1] = el end
  for k = 2, #list + 1 do
    if list[k] ~= nil then rebuilt[#rebuilt + 1] = list[k] end
  end
  -- write back
  for k = #list + 1, 1, -1 do list[k] = nil end
  for k, el in ipairs(rebuilt) do list[k] = el end

  -- Mark the whole paragraph so the stylesheet can clear the float below it.
  if not FORMAT:match("latex") then
    return pandoc.Para({ pandoc.Span(para.content, pandoc.Attr("", { "chapter-opening" })) })
  end
  return para
end

local function read_settings(meta)
  local function s(key, default)
    local v = meta[key]
    if v == nil then return default end
    return pandoc.utils.stringify(v)
  end
  settings.style = s("chapter-opening-style", "none")
  settings.lines = tonumber(s("chapter-opening-lines", "3")) or 3
  settings.small_caps = s("chapter-opening-smallcaps", "true") ~= "false"
end

function Pandoc(doc)
  read_settings(doc.meta)
  if settings.style == "none" then return doc end

  local blocks = doc.blocks
  local i = 1
  while i <= #blocks do
    local b = blocks[i]
    -- Only a numbered chapter opening takes a drop cap. Front and back matter
    -- (a preface, an "also by", an about-the-author, a glossary) are level-1
    -- headings too, but they are unnumbered, and a bibliographic list or a
    -- one-line bio is not a chapter to open with a dropped initial.
    local is_chapter = b.t == "Header" and b.level == 1
      and not (b.classes:includes("unnumbered") or b.classes:includes("unlisted"))
    if is_chapter then
      local j = i + 1
      while j <= #blocks and SKIP[blocks[j].t] do j = j + 1 end
      if j <= #blocks and blocks[j].t == "Para" then
        blocks[j] = transform(blocks[j])
        i = j + 1
      else
        i = i + 1
      end
    else
      i = i + 1
    end
  end
  return doc
end
