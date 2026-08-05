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

-- Pure helpers (the measure vocabulary and small predicates) live in
-- press-util.lua beside this filter; load it by its own directory so `require`
-- resolves whatever working directory pandoc runs from. docs/LUA-QUALITY-PLAN.md §4.
local here = (PANDOC_SCRIPT_FILE or ""):match("^(.*[/\\])") or "./"
package.path = here .. "?.lua;" .. package.path
local util = require("press-util")
local MEASURE_WIDTH = util.MEASURE_WIDTH
local MEASURE_PERCENT = util.MEASURE_PERCENT
local MEASURE_GUARD = util.MEASURE_GUARD
local is_true = util.is_true
local width_opt = util.width_opt

local NUMBERED = {
  figure = true,
  chart = true,
  map = true,
  photo = true,
  diagram = true,
}

-- The first Image inline anywhere inside a Figure.
local function first_image(fig)
  local found
  fig:walk({
    Image = function(img)
      if not found then
        found = img
      end
    end,
  })
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
  if w and MEASURE_PERCENT[w] then
    image.attributes.width = MEASURE_PERCENT[w]
  end
  strip_house_keys(image)
  return image
end

-- A figure's inner LaTeX: optional \phantomsection\label, the height-bounded
-- graphic at the given \includegraphics width option, the unnumbered caption,
-- and (for a numbered figure) the List-of-Figures line. Empty pieces drop.
local function fig_inner(image, label, caption_latex, lof2_latex, gwidth)
  local parts = {}
  if label and label ~= "" then
    parts[#parts + 1] = label
  end
  parts[#parts + 1] = "\\pandocbounded{\\includegraphics[keepaspectratio"
    .. gwidth
    .. "]{"
    .. image.src
    .. "}}"
  if caption_latex and caption_latex ~= "" then
    parts[#parts + 1] = "\\caption*{" .. caption_latex .. "}"
  end
  if lof2_latex and lof2_latex ~= "" then
    parts[#parts + 1] = lof2_latex
  end
  return table.concat(parts, "\n")
end

-- A wrapfigure (parity-aware) around pre-built inner LaTeX. side is "i"/"o".
-- Returned as a STRING, not a block, so walk_blocks can fuse it to the head of
-- the following paragraph: a standalone wrapfigure, with a \par between it and
-- the running text, wraps nothing. Inside the box \linewidth is the wrap width.
-- The \Needspace guard keeps a wrap from starting in the last few lines of a
-- page, where it has no room to close under the figure and wrapfig would strand
-- the figure on the next page away from its text; short of the room, the whole
-- wrap moves to the next page together.
local function wrapfig(inner, side, width, outset)
  local w = MEASURE_WIDTH[width] or "0.4\\linewidth"
  local gap = (outset and outset:match("^[%d%.]+em$")) or "1em"
  local guard = MEASURE_GUARD[width] or 11
  return table.concat({
    "\\Needspace*{" .. guard .. "\\baselineskip}%",
    "\\begin{wrapfigure}{" .. side .. "}{" .. w .. "}",
    "\\setlength{\\intextsep}{" .. gap .. "}%",
    "\\centering",
    inner,
    "\\end{wrapfigure}",
  }, "\n")
end

-- A full-page figure on its OWN leaf, deterministically -- NOT a float. A
-- floating figure[p] is only a request: LaTeX defers it when the current page
-- cannot break cleanly, which strands the plate a leaf or two on and leaves a
-- near-blank page where the reader expected it. So the house clears to the leaf,
-- centres the plate and middles it vertically, sets the caption on the SAME leaf
-- with \captionof (no float, so the caption can never defer away from its
-- figure), then clears off. frontispiece clears to a recto so the plate faces
-- the next chapter opening across the gutter. (True bleed would put ink on the
-- trim edge, which the reading-PDF verifier refuses; the house fills the leaf
-- inside the margins instead.)
local function full_page(image, label, caption_latex, lof2_latex, frontis)
  local parts = {
    -- A frontispiece belongs on the verso facing the next chapter's recto, so
    -- it clears to an even page (KOMA's \cleardoubleevenpage; in a one-sided
    -- book it is simply \clearpage). A full-bleed plate just takes the next leaf.
    frontis and "\\cleardoubleevenpage" or "\\clearpage",
    "\\thispagestyle{empty}",
    "\\null\\vfill",
    "\\begin{center}",
  }
  if label and label ~= "" then
    parts[#parts + 1] = label
  end
  parts[#parts + 1] = "\\pandocbounded{\\includegraphics[keepaspectratio,"
    .. "width=\\linewidth]{"
    .. image.src
    .. "}}"
  parts[#parts + 1] = "\\end{center}"
  if caption_latex and caption_latex ~= "" then
    parts[#parts + 1] = "\\captionof{figure}{" .. caption_latex .. "}"
  end
  if lof2_latex and lof2_latex ~= "" then
    parts[#parts + 1] = lof2_latex
  end
  parts[#parts + 1] = "\\vfill\\clearpage"
  return pandoc.RawBlock("latex", table.concat(parts, "\n"))
end

-- Dispatch a placement to its LaTeX container, given the figure's pre-built
-- inner pieces. Returns {wrap=<string>} for a runaround (walk_blocks fuses it
-- to the next paragraph), a full-page RawBlock, or nil to fall through to the
-- ordinary centered figure. A wrap fills its box, so it takes a \linewidth
-- graphic (the declared width sizes the wrap column itself); a full page builds
-- its own body (a non-float leaf uses \captionof, not the float-only \caption*).
local function placed(image, place, width, outset, label, caption_latex, lof2_latex)
  if place == "wrap-inner" or place == "wrap-outer" or place == "margin" then
    local side = (place == "wrap-inner") and "i" or "o"
    local inner =
      fig_inner(image, label, caption_latex, lof2_latex, ",width=\\linewidth")
    return { wrap = wrapfig(inner, side, width, outset) }
  elseif place == "full-bleed" or place == "frontispiece" then
    return full_page(image, label, caption_latex, lof2_latex, place == "frontispiece")
  end
  return nil
end

function Pandoc(doc)
  local latex = FORMAT == "latex" or FORMAT == "beamer"
  local chapter, fign = 0, 0
  local numbers = {}
  local has_numbered = false

  local function unnumbered_header(h)
    for _, c in ipairs(h.classes) do
      if c == "unnumbered" then
        return true
      end
    end
    return false
  end

  -- Build the replacement for one numbered figure.
  local function numbered_block(fig, image, numstr)
    local cap = inlines_to_latex(caption_inlines(fig))
    if latex then
      local label = fig.identifier ~= ""
          and ("\\phantomsection\\label{" .. fig.identifier .. "}")
        or ""
      -- \mbox the label so a narrow column (a third-measure wrap) can never
      -- hyphenate "Figure" into "Fig-ure"; the caption text after it still wraps.
      local caption_latex = "\\mbox{\\textbf{Figure~"
        .. numstr
        .. ".}}\\enspace "
        .. cap
      local lof2 = "\\addcontentsline{lof2}{figure}{\\protect\\numberline{"
        .. numstr
        .. "}"
        .. cap
        .. "}"
      -- A numbered figure honours its placement too (wrap, full page); only
      -- when it names none does it fall through to the centered figure.
      local by_place = placed(
        image,
        image.attributes.place,
        image.attributes.width,
        image.attributes.outset,
        label,
        caption_latex,
        lof2
      )
      if by_place then
        return by_place
      end
      local inner =
        fig_inner(image, label, caption_latex, lof2, width_opt(image.attributes.width))
      return pandoc.RawBlock(
        "latex",
        "\\begin{figure}[H]\\centering\n" .. inner .. "\n\\end{figure}"
      )
    end
    -- Every other writer: keep the real Figure, prepend the number to the
    -- caption, carry the id as the anchor, and honour width and alt. The
    -- image is mutated through fig:walk (a bare first_image is a copy).
    local alt = image.attributes["fig-alt"]
    fig = fig:walk({
      Image = function(img)
        return finalize_image(img, false, alt)
      end,
    })
    local long = fig.caption.long or pandoc.Blocks({})
    local prefix = pandoc.Inlines({
      pandoc.Strong({ pandoc.Str("Figure " .. numstr .. ".") }),
      pandoc.Space(),
    })
    if #long > 0 and (long[1].t == "Plain" or long[1].t == "Para") then
      long[1].content = prefix .. long[1].content
    else
      table.insert(long, 1, pandoc.Plain(prefix))
    end
    fig.caption.long = long
    if fig.identifier ~= "" then
      fig.attr.identifier = fig.identifier
    end
    return fig
  end

  -- Non-numbered figure: a plate. Byte-identical unless it asks for a
  -- placement, a width, or an accessible-alt treatment.
  local function plate_block(fig, image, decorative)
    local place = image.attributes.place
    local width = image.attributes.width
    local alt = image.attributes["fig-alt"]
    if not place and not width and not decorative and not alt then
      return nil -- untouched: the byte-identity guarantee
    end
    -- Honour alt, width, and strip house keys (mutating through fig:walk,
    -- since a bare first_image hands back a copy).
    fig = fig:walk({
      Image = function(img)
        return finalize_image(img, decorative, alt)
      end,
    })
    if not latex or not place then
      return fig
    end
    local cap = inlines_to_latex(caption_inlines(fig))
    local by_place = placed(image, place, width, image.attributes.outset, "", cap, "")
    if by_place then
      return by_place
    end
    return fig -- inline/plate: the ordinary in-flow figure
  end

  local function transform(fig)
    local image = first_image(fig)
    if not image then
      return fig
    end
    local kind = image.classes[1]
    local decorative = is_true(image.attributes.decorative)
    local numbered = kind ~= nil and NUMBERED[kind] and not decorative
    if numbered then
      fign = fign + 1
      local numstr = (chapter > 0) and (chapter .. "." .. fign) or tostring(fign)
      has_numbered = true
      if fig.identifier ~= "" then
        numbers[fig.identifier] = numstr
      end
      return numbered_block(fig, image, numstr)
    end
    return plate_block(fig, image, decorative)
  end

  local walk_blocks
  walk_blocks = function(blocks)
    local out = {}
    -- A wrapfigure only wraps when it fuses to the START of the paragraph that
    -- follows it -- no \par between them. transform() returns {wrap=<latex>}
    -- for a runaround; we hold it here and splice it into the head of the next
    -- Para/Plain. If none follows (end of a section, a heading next, a second
    -- wrap), we flush it standalone so nothing is dropped.
    local pending = nil
    local function flush()
      if pending then
        out[#out + 1] = pandoc.RawBlock("latex", pending)
        pending = nil
      end
    end
    for _, b in ipairs(blocks) do
      if b.t == "Header" and b.level == 1 and not unnumbered_header(b) then
        flush()
        chapter = chapter + 1
        fign = 0
        out[#out + 1] = b
      elseif b.t == "Figure" then
        local r = transform(b) or b
        flush()
        if type(r) == "table" and r.wrap then
          pending = r.wrap
        else
          out[#out + 1] = r
        end
      elseif (b.t == "Para" or b.t == "Plain") and pending then
        table.insert(b.content, 1, pandoc.RawInline("latex", pending .. "%\n"))
        pending = nil
        out[#out + 1] = b
      elseif b.t == "Div" or b.t == "BlockQuote" then
        flush()
        b.content = walk_blocks(b.content)
        out[#out + 1] = b
      else
        flush()
        out[#out + 1] = b
      end
    end
    flush()
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
      if not num then
        return nil
      end
      if latex then
        return pandoc.RawInline(
          "latex",
          "\\hyperref[" .. cid .. "]{Figure~" .. num .. "}"
        )
      end
      return pandoc.Link(
        { pandoc.Str("Figure"), pandoc.Space(), pandoc.Str(num) },
        "#" .. cid
      )
    end,
  })

  return doc
end
