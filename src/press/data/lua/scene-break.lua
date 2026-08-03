-- Scene breaks as an aesthetic ornament, at the document-tree layer.
--
-- A Markdown thematic break (`* * *`, or any blank-separated rule) is by
-- default a plain horizontal rule. A literary book wants a lighter mark for a
-- shift of scene or time: a centered asterism, the convention a bare rule reads
-- too heavily for; or the staggered three-row array of asterisks Tenniel's 1866
-- Alice set at each shrink and grow -- "fairy dust". When the book's aesthetic
-- asks for one (scene-break: asterism | fairy-dust, carried here as the
-- `scene-break-ornament` metadata) each thematic break becomes that ornament in
-- every edition -- the PDF, the reading site, and the EPUB alike.
--
-- Off (the default, `rule`) the filter changes nothing, so every existing
-- book's rules render byte-for-byte as before. It is aesthetic-gated on
-- purpose: turning a rule into an ornament is a design choice a book opts into.

local ornament = "rule"

local function asterism()
  -- A centered row of three asterisks -- what the Project Gutenberg sources
  -- spell as rows of asterisks, and what a Victorian trade edition set as a
  -- scene break. Asterisks (not a dedicated asterism glyph) so every interior
  -- font carries them.
  if FORMAT:match("latex") then
    return pandoc.RawBlock("latex", "\\begin{center}*\\quad*\\quad*\\end{center}")
  end
  if FORMAT:match("html") or FORMAT:match("epub") then
    return pandoc.RawBlock("html", '<p class="asterism">* * *</p>')
  end
  return nil -- a format without a centering idiom keeps the plain rule
end

local function fairy_dust()
  -- The staggered three-row asterisk array Tenniel's 1866 Alice set for each
  -- shrink or grow: four asterisks, three offset into the gaps, four again -- a
  -- scattered "fairy dust", not a single row. One source thematic break becomes
  -- the whole array in every edition; the LaTeX macro and the .fairy-dust CSS
  -- share the grid so print and web read alike.
  if FORMAT:match("latex") then
    return pandoc.RawBlock("latex", "\\PressFairyDust")
  end
  if FORMAT:match("html") or FORMAT:match("epub") then
    return pandoc.RawBlock(
      "html",
      '<div class="fairy-dust" role="separator" aria-hidden="true">'
        .. "<span>&#42;&#42;&#42;&#42;</span>"
        .. "<span>&#42;&#42;&#42;</span>"
        .. "<span>&#42;&#42;&#42;&#42;</span></div>"
    )
  end
  return nil
end

local ORNAMENTS = { asterism = asterism, ["fairy-dust"] = fairy_dust }

function Pandoc(doc)
  local v = doc.meta["scene-break-ornament"]
  if v ~= nil then
    ornament = pandoc.utils.stringify(v)
  end
  local render = ORNAMENTS[ornament]
  if render == nil then
    return doc
  end -- "rule" (or unknown): leave the rule
  return doc:walk({
    HorizontalRule = function(_)
      return render()
    end,
  })
end
