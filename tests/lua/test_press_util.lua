-- Unit tests for the pure helpers in src/press/data/lua/press-util.lua, run
-- under pandoc's Lua 5.4 with no render. The pytest wrapper
-- (tests/test_press_util_lua.py) sets PRESS_LUA_DIR to the filter directory so
-- `require` resolves the module. docs/LUA-QUALITY-PLAN.md §4.
package.path = (os.getenv("PRESS_LUA_DIR") or ".") .. "/?.lua;" .. package.path
local util = require("press-util")

local failed = 0
local function eq(got, want, msg)
  if got ~= want then
    failed = failed + 1
    io.stderr:write(
      string.format("FAIL %s: got %q want %q\n", msg, tostring(got), tostring(want))
    )
  end
end

-- width_opt: measures map to \linewidth fractions, percents compute, empty is
-- "", a raw length passes through.
eq(util.width_opt(nil), "", "width_opt nil")
eq(util.width_opt(""), "", "width_opt empty")
eq(util.width_opt("full-measure"), ",width=\\linewidth", "width_opt full")
eq(util.width_opt("half-measure"), ",width=0.5\\linewidth", "width_opt half")
eq(util.width_opt("third-measure"), ",width=0.3333\\linewidth", "width_opt third")
eq(util.width_opt("50%"), ",width=0.5\\linewidth", "width_opt 50%")
eq(util.width_opt("3in"), ",width=3in", "width_opt raw length")

-- is_true: true/yes/1 in any case, everything else false.
eq(util.is_true("true"), true, "is_true true")
eq(util.is_true("YES"), true, "is_true YES")
eq(util.is_true("1"), true, "is_true 1")
eq(util.is_true("false"), false, "is_true false")
eq(util.is_true(nil), false, "is_true nil")
eq(util.is_true(""), false, "is_true empty")

-- the measure vocabulary the filter and the CSS share.
eq(util.MEASURE_PERCENT["half-measure"], "50%", "MEASURE_PERCENT half")
eq(util.MEASURE_GUARD["full-measure"], 20, "MEASURE_GUARD full")

local function approx(got, want, msg)
  if type(got) ~= "number" or math.abs(got - want) > 1e-9 then
    failed = failed + 1
    io.stderr:write(
      string.format("FAIL %s: got %s want ~%s\n", msg, tostring(got), tostring(want))
    )
  end
end

-- cascade_indent: each line one 2.4em step deeper, the first flush.
approx(util.cascade_indent(1), 0, "cascade_indent first")
approx(util.cascade_indent(3), 4.8, "cascade_indent third")

-- tail_ramp: sine swing (0 at the head, peak a quarter down) with the size ramp.
local off, size = util.tail_ramp(1, 9)
approx(off, 0, "tail_ramp head offset")
eq(size, "\\normalsize", "tail_ramp head size")
off, size = util.tail_ramp(3, 9)
approx(off, 3.0, "tail_ramp quarter offset")
eq(size, "\\small", "tail_ramp quarter size")

-- tail_web_size: the web font-size ramp, head to tip.
eq(util.tail_web_size(1, 9), "1em", "tail_web_size head")
eq(util.tail_web_size(9, 9), "0.68em", "tail_web_size tip")

if failed > 0 then
  io.stderr:write(failed .. " assertion(s) failed\n")
  os.exit(1)
end
print("press-util: all assertions passed")
