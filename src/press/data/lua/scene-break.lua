-- Scene breaks as an aesthetic ornament, at the document-tree layer.
--
-- A Markdown thematic break (`* * *`, or any blank-separated rule) is by
-- default a plain horizontal rule. A literary book wants a lighter mark for a
-- shift of scene or time: a centered asterism, the convention a bare rule reads
-- too heavily for. When the book's aesthetic asks for it (scene-break:
-- asterism, carried here as the `scene-break-ornament` metadata) each thematic
-- break becomes a centered asterism in every edition -- the PDF, the reading
-- site, and the EPUB alike.
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
  return nil   -- a format without a centering idiom keeps the plain rule
end

function Pandoc(doc)
  local v = doc.meta["scene-break-ornament"]
  if v ~= nil then ornament = pandoc.utils.stringify(v) end
  if ornament ~= "asterism" then return doc end
  return doc:walk({
    HorizontalRule = function(_)
      return asterism()
    end,
  })
end
