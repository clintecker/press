-- Number the informative figures, split the illustration lists, and place
-- figures by the house's relative, parity-aware vocabulary.
--
-- The literary woodcut idiom keeps a *plate* unnumbered, and a bare image (no
-- declared kind) is a plate too, so a book that declares no numbered figure is
-- transformed in no way and typesets byte-for-byte as before. Only a figure
-- that DECLARES an informative kind (.figure/.chart/.map/.photo/.diagram) and
-- is not decorative earns a "Figure C.N" number, a List of Figures entry
-- (kept apart from the List of Plates), and a cross-reference target that a
-- `@fig:id` reference resolves to "Figure C.N".
--
-- The number is computed here, once, so every format agrees: LaTeX never
-- counts figures and no pandoc-crossml is needed. Placement rides on the
-- image attributes (width=…-measure, place=…, outset=…) and is applied for
-- the PDF; other formats keep the width and fall back to an in-flow figure.

local NUMBERED = {
  figure = true, chart = true, map = true, photo = true, diagram = true,
}

-- A relative width measure -> the graphics width option, against the line.
local MEASURE_WIDTH = {
  ["full-measure"]  = "\\linewidth",
  ["half-measure"]  = "0.5\\linewidth",
  ["third-measure"] = "0.3333\\linewidth",
}
-- The same, as a pandoc width value other writers understand.
local MEASURE_PERCENT = {
  ["full-measure"] = "100%", ["half-measure"] = "50%", ["third-measure"] = "33%",
}

local function is_true(v)
  v = tostring(v or ""):lower()
  return v == "true" or v == "yes" or v == "1"
end

-- The first Image inline anywhere inside a Figure.
local function first_image(fig)
  local found
  fig:walk({ Image = function(img) if not found then found = img end end })
  return found
end

-- The figure's visible caption as a flat inline list.
local function caption_inlines(fig)
  return pandoc.utils.blocks_to_inlines(fig.caption.long or {})
end

-- Render inline content to LaTeX (the caption keeps its emphasis).
local function inlines_to_latex(inls)
  local tex = pandoc.write(pandoc.Pandoc({ pandoc.Plain(inls) }), "latex")
  return (tex:gsub("%s+$", ""))
end

-- The LaTeX \includegraphics width option for a declared width, or "".
local function width_opt(width)
  if not width or width == "" then return "" end
  if MEASURE_WIDTH[width] then return ",width=" .. MEASURE_WIDTH[width] end
  local pct = width:match("^(%d+)%%$")
  if pct then return ",width=" .. (tonumber(pct) / 100) .. "\\linewidth" end
  return ",width=" .. width       -- a raw length passes through unchanged
end

-- The house-only attributes that must never leak into the output (pandoc
-- would otherwise pass them through as data-* on the HTML <img>).
local function strip_house_keys(image)
  image.attributes.place = nil
  image.attributes.outset = nil
  image.attributes.decorative = nil
  image.attributes["fig-alt"] = nil
end

-- An image's accessible alt (its pandoc "caption" inlines) becomes: empty for
-- a decorative ornament, the fig-alt for anything that declares one, otherwise
-- unchanged. The visible figure caption is a different field and is left
-- alone (alt and caption are distinct, #225 kin). A relative width measure is
-- translated to the percent other writers understand, and the house-only keys
-- are stripped. Returns the mutated image (used through fig:walk, which
-- otherwise hands back copies).
local function finalize_image(image, decorative, alt)
  if decorative then
    image.caption = {}
  elseif alt and alt ~= "" then
    image.caption = pandoc.Inlines({ pandoc.Str(alt) })
  end
  local w = image.attributes.width
  if w and MEASURE_PERCENT[w] then image.attributes.width = MEASURE_PERCENT[w] end
  strip_house_keys(image)
  return image
end

-- A wrapfigure (parity-aware) for a placed plate. side is "i"/"o".
local function wrapfig(image, caption_latex, side, width, outset)
  local w = MEASURE_WIDTH[width] or "0.4\\linewidth"
  local gap = (outset and outset:match("^[%d%.]+em$")) or "1em"
  local label = ""
  return pandoc.RawBlock("latex", table.concat({
    "\\begin{wrapfigure}{" .. side .. "}{" .. w .. "}",
    "\\setlength{\\intextsep}{" .. gap .. "}%",
    "\\centering",
    label,
    "\\pandocbounded{\\includegraphics[keepaspectratio,width=" .. w .. "]{"
      .. image.src .. "}}",
    caption_latex ~= "" and ("\\caption*{" .. caption_latex .. "}") or "",
    "\\end{wrapfigure}",
  }, "\n"))
end

-- A full-page plate on its own leaf (full-bleed and frontispiece map here;
-- true bleed would put ink on the trim edge, which the reading-PDF verifier
-- refuses, so the house treats it as a full-measure plate on a cleared page).
local function full_page(image, caption_latex, recto)
  local clear = recto and "\\cleardoublepage" or "\\clearpage"
  return pandoc.RawBlock("latex", table.concat({
    clear,
    "\\thispagestyle{empty}",
    "\\begin{figure}[p]\\centering",
    "\\pandocbounded{\\includegraphics[keepaspectratio,width=\\linewidth]{"
      .. image.src .. "}}",
    caption_latex ~= "" and ("\\caption*{" .. caption_latex .. "}") or "",
    "\\end{figure}",
  }, "\n"))
end

function Pandoc(doc)
  local latex = FORMAT == "latex" or FORMAT == "beamer"
  local chapter, fign = 0, 0
  local numbers = {}
  local has_numbered = false

  local function unnumbered_header(h)
    for _, c in ipairs(h.classes) do
      if c == "unnumbered" then return true end
    end
    return false
  end

  -- Build the replacement for one numbered figure.
  local function numbered_block(fig, image, numstr)
    local cap = inlines_to_latex(caption_inlines(fig))
    if latex then
      local label = fig.identifier ~= "" and
        ("\\phantomsection\\label{" .. fig.identifier .. "}") or ""
      local tex = table.concat({
        "\\begin{figure}[H]\\centering",
        label,
        "\\pandocbounded{\\includegraphics[keepaspectratio"
          .. width_opt(image.attributes.width) .. "]{" .. image.src .. "}}",
        "\\caption*{\\textbf{Figure~" .. numstr .. ".}\\enspace " .. cap .. "}",
        "\\addcontentsline{lof2}{figure}{\\protect\\numberline{" .. numstr
          .. "}" .. cap .. "}",
        "\\end{figure}",
      }, "\n")
      return pandoc.RawBlock("latex", tex)
    end
    -- Every other writer: keep the real Figure, prepend the number to the
    -- caption, carry the id as the anchor, and honour width and alt. The
    -- image is mutated through fig:walk (a bare first_image is a copy).
    local alt = image.attributes["fig-alt"]
    fig = fig:walk({ Image = function(img)
      return finalize_image(img, false, alt)
    end })
    local long = fig.caption.long or pandoc.Blocks({})
    local prefix = pandoc.Inlines({
      pandoc.Strong({ pandoc.Str("Figure " .. numstr .. ".") }), pandoc.Space(),
    })
    if #long > 0 and long[1].t == "Plain" then
      long[1].content = prefix .. long[1].content
    elseif #long > 0 and long[1].t == "Para" then
      long[1].content = prefix .. long[1].content
    else
      table.insert(long, 1, pandoc.Plain(prefix))
    end
    fig.caption.long = long
    if fig.identifier ~= "" then fig.attr.identifier = fig.identifier end
    return fig
  end

  -- Non-numbered figure: a plate. Byte-identical unless it asks for a
  -- placement, a width, or an accessible-alt treatment.
  local function plate_block(fig, image, decorative)
    local place = image.attributes.place
    local width = image.attributes.width
    local alt = image.attributes["fig-alt"]
    if not place and not width and not decorative and not alt then
      return nil   -- untouched: the byte-identity guarantee
    end
    -- Honour alt, width, and strip house keys (mutating through fig:walk,
    -- since a bare first_image hands back a copy).
    fig = fig:walk({ Image = function(img)
      return finalize_image(img, decorative, alt)
    end })
    if not latex or not place then return fig end
    local cap = inlines_to_latex(caption_inlines(fig))
    if place == "wrap-inner" then
      return wrapfig(image, cap, "i", width, image.attributes.outset)
    elseif place == "wrap-outer" or place == "margin" then
      return wrapfig(image, cap, "o", width, image.attributes.outset)
    elseif place == "full-bleed" then
      return full_page(image, cap, false)
    elseif place == "frontispiece" then
      return full_page(image, cap, true)
    end
    return fig      -- inline/plate: the ordinary in-flow figure
  end

  local function transform(fig)
    local image = first_image(fig)
    if not image then return fig end
    local kind = image.classes[1]
    local decorative = is_true(image.attributes.decorative)
    local numbered = kind ~= nil and NUMBERED[kind] and not decorative
    if numbered then
      fign = fign + 1
      local numstr = (chapter > 0) and (chapter .. "." .. fign) or tostring(fign)
      has_numbered = true
      if fig.identifier ~= "" then numbers[fig.identifier] = numstr end
      return numbered_block(fig, image, numstr)
    end
    return plate_block(fig, image, decorative)
  end

  local walk_blocks
  walk_blocks = function(blocks)
    local out = {}
    for _, b in ipairs(blocks) do
      if b.t == "Header" and b.level == 1 and not unnumbered_header(b) then
        chapter = chapter + 1
        fign = 0
        out[#out + 1] = b
      elseif b.t == "Figure" then
        out[#out + 1] = transform(b) or b
      elseif b.t == "Div" or b.t == "BlockQuote" then
        b.content = walk_blocks(b.content)
        out[#out + 1] = b
      else
        out[#out + 1] = b
      end
    end
    return out
  end

  doc.blocks = walk_blocks(doc.blocks)

  -- The List of Figures prints only when the book has numbered figures, and
  -- sits just after the (optional) List of Plates the template emits.
  if has_numbered and latex then
    table.insert(doc.blocks, 1, pandoc.RawBlock("latex", "\\PressListOfFigures"))
  end

  -- Resolve every @fig:id cross-reference to a linked "Figure C.N".
  doc = doc:walk({
    Cite = function(cite)
      local cid = cite.citations[1] and cite.citations[1].id or ""
      local num = numbers[cid]
      if not num then return nil end
      if latex then
        return pandoc.RawInline("latex",
          "\\hyperref[" .. cid .. "]{Figure~" .. num .. "}")
      end
      return pandoc.Link(
        { pandoc.Str("Figure"), pandoc.Space(), pandoc.Str(num) }, "#" .. cid)
    end,
  })

  return doc
end
