-- Typographic spacing, at the document-tree layer.
--
-- The author types plainly; the house ties the spaces a fine setter would. A
-- line should not break after a title ("Mr. Smith"), after a reference short
-- form ("p. 42", "Fig. 3"), or between a person's initials ("C. L. Dodgson").
-- This filter binds those with a non-breaking space, which renders as ~ in
-- LaTeX and U+00A0 on the web and in EPUB, and collapses back to an ordinary
-- space in text extraction -- so it changes line-breaking, never the words
-- (the cross-edition agreement check normalizes whitespace, so every edition
-- still agrees).
--
-- Conservative by construction: a curated abbreviation set, and a tie only when
-- what follows fits -- a capitalized word after a title, a digit after a
-- reference, another initial or a name after an initial. Anything else is left
-- exactly as typed, so ordinary prose is untouched.

local NBSP = utf8.char(0xA0)

-- Titles that bind to a following capitalized word (a name).
local TITLES = {
  ["Mr."] = true,
  ["Mrs."] = true,
  ["Ms."] = true,
  ["Dr."] = true,
  ["Prof."] = true,
  ["St."] = true,
  ["Mt."] = true,
  ["Sr."] = true,
  ["Jr."] = true,
  ["Rev."] = true,
  ["Hon."] = true,
  ["Capt."] = true,
  ["Sgt."] = true,
  ["Gen."] = true,
  ["Col."] = true,
  ["Lt."] = true,
  ["Fr."] = true,
}

-- Reference short forms that bind to a following number. Kept to the forms
-- whose plain word is not a common sentence word, so a period that is really a
-- full stop is never swept up.
local REFS = {
  ["p."] = true,
  ["pp."] = true,
  ["No."] = true,
  ["Nos."] = true,
  ["Fig."] = true,
  ["Figs."] = true,
  ["Ch."] = true,
  ["Vol."] = true,
  ["Pt."] = true,
  ["Eq."] = true,
  ["\u{00A7}"] = true,
  ["\u{00B6}"] = true,
}

local function is_number(s)
  return s:match("^%d") ~= nil
end
local function is_capitalized(s)
  return s:match("^%u") ~= nil
end
local function is_initial(s)
  return s:match("^%u%.$") ~= nil
end

local function binds(a, b)
  if TITLES[a] and is_capitalized(b) then
    return true
  end
  if REFS[a] and is_number(b) then
    return true
  end
  if is_initial(a) and (is_initial(b) or is_capitalized(b)) then
    return true
  end
  return false
end

function Inlines(inlines)
  local out = pandoc.List()
  local i, n = 1, #inlines
  while i <= n do
    local a, sp, b = inlines[i], inlines[i + 1], inlines[i + 2]
    if
      a
      and a.t == "Str"
      and sp
      and sp.t == "Space"
      and b
      and b.t == "Str"
      and binds(a.text, b.text)
    then
      out:insert(a)
      out:insert(pandoc.Str(NBSP))
      i = i + 2 -- keep b as the next head, so initials chain
    else
      out:insert(a)
      i = i + 1
    end
  end
  return out
end
