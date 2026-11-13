-- Example captions and listings, at the document-tree layer.
--
-- A technical book numbers its examples: "Example 2.4. Installing the
-- toolchain on macOS" over the block it names. Authors already write that as
-- a bold paragraph before the fence, which every edition then set as an
-- ordinary bold paragraph, free to strand at a page foot with its code over
-- the leaf (#293). This filter recognises the caption and attaches it to its
-- block, so each edition can set it as a caption: the PDF in the house form
-- with a keep (\PressExampleCaption, book-header.tex), the web and the EPUB
-- as a paragraph of class example-caption, DOCX in the Caption style.
--
-- Two spellings, one result:
--   implicit  a paragraph whose only content is
--             **Example C.N. Title** (or **Example N. Title**, or an
--             appendix's **Example A.N. Title**) directly before a code block.
--   explicit  a fence attribute, ```{.text caption="Example 2.4. Title"},
--             with an optional id; the number is authored in the caption
--             text, as the house numbers tables (no automatic numbering).
--
-- A bold paragraph before anything other than a code block is not a caption
-- and is left alone, and a document with no captioned block is untouched, so
-- a book that writes no examples renders byte-for-byte as before. The space
-- and rules around the block itself are the TeX header's job, not this
-- filter's: every block wears them, captioned or not.

local latex = FORMAT:match("latex") ~= nil
local web = FORMAT:match("html") ~= nil or FORMAT:match("epub") ~= nil
local docx = FORMAT == "docx"

-- The number forms a caption may carry: "2.", "2.4.", "A.3.".
local NUMBER = { "^%d+%.$", "^%d+%.%d+%.$", "^%u%.%d+%.$" }

local function is_number(s)
  for _, pattern in ipairs(NUMBER) do
    if s:match(pattern) then
      return true
    end
  end
  return false
end

-- A space between words: an ordinary one, a tie, or the line end of a
-- caption the author wrapped in the source.
local function is_gap(el)
  return el ~= nil
    and (
      el.t == "Space"
      or el.t == "SoftBreak"
      or (el.t == "Str" and el.text == "\u{00A0}")
    )
end

-- Split caption inlines into the label ("Example 2.4.") and the title
-- inlines after it. Returns nil when the inlines do not open with a label.
local function split_label(inls)
  local word, gap, number, gap2 = inls[1], inls[2], inls[3], inls[4]
  if not (word and word.t == "Str" and word.text == "Example") then
    return nil
  end
  if not (is_gap(gap) and number and number.t == "Str" and is_number(number.text)) then
    return nil
  end
  if not is_gap(gap2) or #inls < 5 then
    return nil
  end
  return "Example " .. number.text, pandoc.List({ table.unpack(inls, 5) })
end

-- The implicit spelling: a Para holding a single Strong that opens with a
-- label and carries a title.
local function implicit_caption(block)
  if block.t ~= "Para" or #block.content ~= 1 or block.content[1].t ~= "Strong" then
    return nil
  end
  return split_label(block.content[1].content)
end

-- Render inline content to LaTeX (the title keeps its code and emphasis).
local function inlines_to_latex(inls)
  local tex = pandoc.write(pandoc.Pandoc({ pandoc.Plain(inls) }), "latex")
  return (tex:gsub("%s+$", ""))
end

-- The caption as inlines: the bold label, a space, the italic title. A
-- caption with no label is the italic title alone.
local function caption_inlines(label, title)
  local out = pandoc.List()
  if label ~= "" then
    out:insert(pandoc.Strong({ pandoc.Str(label) }))
    out:insert(pandoc.Space())
  end
  out:insert(pandoc.Emph(title))
  return out
end

-- The caption block for this format; `id` (possibly "") anchors it, so a
-- link to the example lands on its caption, not under it.
local function caption_block(label, title, id)
  if latex then
    -- The anchor rides in the macro's optional argument, so the header sets
    -- it after the caption's keep, on the page the caption lands on.
    local anchor = ""
    if id ~= "" then
      anchor = "[" .. id .. "]"
    end
    return pandoc.RawBlock(
      "latex",
      "\\PressExampleCaption"
        .. anchor
        .. "{"
        .. label
        .. "}{"
        .. inlines_to_latex(title)
        .. "}"
    )
  end
  local para = pandoc.Para(caption_inlines(label, title))
  if web then
    return pandoc.Div({ para }, pandoc.Attr(id, { "example-caption" }))
  end
  if docx then
    return pandoc.Div({ para }, pandoc.Attr(id, {}, { ["custom-style"] = "Caption" }))
  end
  return para
end

-- The explicit spelling: caption= on the fence. The attribute is consumed
-- (no writer should pass it through as data-caption), and so is the id,
-- which moves to the caption. Returns the caption block, or nil.
local function explicit_caption(code)
  local text = code.attributes.caption
  if text == nil then
    return nil
  end
  code.attributes.caption = nil
  local inls = pandoc.utils.blocks_to_inlines(pandoc.read(text, "markdown").blocks)
  local label, title = split_label(inls)
  if label == nil then
    label, title = "", inls
  end
  local id = code.identifier
  code.identifier = ""
  return caption_block(label, title, id)
end

local function captioned(blocks)
  local out = pandoc.List()
  local changed = false
  local i, n = 1, #blocks
  while i <= n do
    local block, nxt = blocks[i], blocks[i + 1]
    local label, title = implicit_caption(block)
    if label and nxt and nxt.t == "CodeBlock" and nxt.attributes.caption ~= nil then
      -- Both spellings on one block: the attribute is the caption, and the
      -- bold paragraph, which would only repeat or contradict it, is dropped.
      changed = true
      i = i + 1
    elseif label and nxt and nxt.t == "CodeBlock" then
      changed = true
      if latex or web or docx then
        -- The fence's id moves to the caption, as the explicit form's does,
        -- so a link to the example lands on its caption.
        out:insert(caption_block(label, title, nxt.identifier))
        nxt.identifier = ""
      else
        out:insert(block) -- plain text: the paragraph already reads as one
      end
      out:insert(nxt)
      i = i + 2
    elseif block.t == "CodeBlock" and block.attributes.caption ~= nil then
      changed = true
      out:insert(explicit_caption(block))
      out:insert(block)
      i = i + 1
    else
      out:insert(block)
      i = i + 1
    end
  end
  if changed then
    return out
  end
  return nil
end

-- Every block list, at any depth: a captioned example inside a list item or
-- a fenced div is attached as surely as one at the top level.
function Pandoc(doc)
  return doc:walk({ Blocks = captioned })
end
