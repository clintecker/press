-- Redirect interior figure paths to the print-safe copies press.print_safe
-- writes under build/print-assets/ (flattened, resolution-capped). Applied
-- only through the print defaults, so the reading PDF keeps the originals.
-- The rewritten path resolves against the same base as the original
-- assets/ reference, so lualatex embeds the sanitized image with no
-- graphicspath guesswork.
function Image(el)
  el.src = el.src:gsub("^%.?/?assets/", "build/print-assets/assets/")
  return el
end
