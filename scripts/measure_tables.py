#!/usr/bin/env python3
"""Measure how a built reader site sets its tables, in a real browser.

A maintainer's instrument, not a gate. It drives headless Chrome (through
`check_layout.Chrome`, the same CDP-over-pipe driver the documentation site's
layout check uses) over every `*.html` page of a built site, at three viewport
widths (1280, 820, and 390 CSS pixels by default), and reports, per width:

  * code split inside a token: a `<code>` span with no space in it whose
    boxes fall on more than one line, in a table cell or a ledger entry (an
    identifier or command broken mid-word);
  * code wrapped at a space: a multi-word `<code>` span that wraps between
    words (legitimate, but counted, because a command reads worse in pieces);
  * sparse prose: a table cell of three or more lines averaging fewer than
    1.5 words a line (a column squeezed until its prose reads one word deep);
  * tall cells: a table cell of five or more lines;
  * tables wider than the measure (a grid scrolls in its own box, so this is
    reported, not judged);
  * clipped cells: a cell whose content is wider than its box;
  * pages scrolling sideways: the document itself wider than the viewport;
  * and the `.ledger` and `.grid` elements on each page and in total, at the
    first width (the markup does not change with the viewport).

Lines are counted from the client rectangles of a Range over the cell's
contents, bucketed by the cell's computed line height, so the numbers are a
heuristic: an inline box taller than a line, or a line height the page does
not state, can move a count by one. Read them as a comparison between two
builds of the same book, not as absolutes.

Run:  python3 scripts/measure_tables.py BOOK/dist/site [--widths 1280,820,390]
      [--json] [--fail-on-any]

It exits 0 and prints a notice when no Chrome is installed (set PRESS_CHROME
to point at one). With --fail-on-any it exits 1 if any width has a code token
split inside itself, a clipped cell, or a page scrolling sideways.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_layout  # noqa: E402  (a sibling script, not a package)

VIEWPORT_HEIGHT = 900

# One page's measurements: every table cell, every code span in a table or a
# ledger, every table's geometry, the page's own overflow, and the shape
# counts. Lines are Range client rects bucketed by the element's line height.
_JS = r"""(() => {
  const lh = (el) => {
    const cs = getComputedStyle(el);
    const v = parseFloat(cs.lineHeight);
    return v > 0 ? v : parseFloat(cs.fontSize) * 1.2;
  };
  const lines = (rects, h) => {
    const tops = new Set();
    for (const b of rects) if (b.width > 0 && b.height > 0) tops.add(Math.round(b.top / h));
    return Math.max(1, tops.size);
  };
  const cellLines = (c) => {
    const rg = document.createRange(); rg.selectNodeContents(c);
    return lines(rg.getClientRects(), lh(c));
  };
  const cells = [];
  document.querySelectorAll('table').forEach((t, i) => {
    for (const r of Array.from(t.rows).slice(1)) for (const c of r.cells) {
      const text = c.innerText.trim();
      const words = text ? text.split(/\s+/).length : 0;
      cells.push({table: i, lines: cellLines(c), words, text: text.slice(0, 60),
                  clipped: c.scrollWidth > c.clientWidth + 1});
    }
  });
  const codes = [];
  document.querySelectorAll('table code, .ledger code').forEach((k) => {
    const n = lines(k.getClientRects(), lh(k));
    if (n > 1) {
      const host = k.closest('table') ? 'table' : 'ledger';
      codes.push({text: k.innerText.slice(0, 40), host, inToken: !/\s/.test(k.innerText.trim())});
    }
  });
  const cs = getComputedStyle(document.body);
  const measure = document.body.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
  const tables = Array.from(document.querySelectorAll('table')).map((t, i) =>
    ({i, width: Math.round(t.getBoundingClientRect().width)}));
  const de = document.documentElement;
  return {cells, codes, tables, measure: Math.round(measure),
          overflow: Math.round(de.scrollWidth - de.clientWidth),
          ledgers: document.querySelectorAll('.ledger').length,
          grids: document.querySelectorAll('.grid').length};
})()"""


def summarize(pages: dict[str, dict]) -> dict:
    """Fold one width's per-page measurements into the reported counts."""

    def n_tables(items: list[tuple[str, dict]]) -> int:
        return len({(page, c["table"]) for page, c in items})

    cells = [(p, c) for p, m in pages.items() for c in m["cells"] if c["words"]]
    codes = [(p, k) for p, m in pages.items() for k in m["codes"]]
    sparse = [(p, c) for p, c in cells if c["lines"] >= 3 and c["words"] / c["lines"] < 1.5]
    tall = [(p, c) for p, c in cells if c["lines"] >= 5]
    clipped = [(p, c) for p, c in cells if c["clipped"]]
    wide = [(p, t) for p, m in pages.items() for t in m["tables"] if t["width"] > m["measure"] + 1]
    return {
        "body_cells": len(cells),
        "tables": sum(len(m["tables"]) for m in pages.values()),
        "split_in_token": [f"{p}: {k['text']!r} ({k['host']})" for p, k in codes if k["inToken"]],
        "wrapped_at_space": len([k for _, k in codes if not k["inToken"]]),
        "sparse_cells": len(sparse),
        "sparse_tables": n_tables(sparse),
        "tall_cells": len(tall),
        "clipped_cells": [f"{p}: table {c['table']} {c['text']!r}" for p, c in clipped],
        "wider_than_measure": len(wide),
        "scrolling_pages": sorted(p for p, m in pages.items() if m["overflow"] > 1),
        "ledgers": {p: m["ledgers"] for p, m in pages.items() if m["ledgers"]},
        "grids": {p: m["grids"] for p, m in pages.items() if m["grids"]},
    }


def measure_site(site_dir: Path, widths: list[int], chrome_path: str) -> dict[int, dict]:
    """Load every page at every width and return the summary per width."""

    pages = sorted(site_dir.glob("*.html"))
    results: dict[int, dict] = {}
    with check_layout.Chrome(chrome_path) as chrome:
        for width in widths:
            chrome.set_viewport(width, VIEWPORT_HEIGHT)
            raw: dict[str, dict] = {}
            for page in pages:
                chrome.navigate(page.resolve().as_uri())
                raw[page.name] = chrome.evaluate(_JS)
            results[width] = summarize(raw)
    return results


def failures(results: dict[int, dict]) -> int:
    """The count --fail-on-any judges: in-token splits, clipped cells, and
    pages scrolling sideways, at every width."""

    return sum(
        len(r["split_in_token"]) + len(r["clipped_cells"]) + len(r["scrolling_pages"])
        for r in results.values()
    )


def report(results: dict[int, dict]) -> None:
    """Print the human table, the shape counts, and every offender by name."""

    print(
        f"{'width':>6} {'cells':>6} {'split':>6} {'at-space':>9} {'sparse':>12} "
        f"{'tall':>5} {'clipped':>8} {'wide':>5} {'scrolling':>10}"
    )
    for width, r in results.items():
        sparse = f"{r['sparse_cells']}/{r['sparse_tables']}t"
        print(
            f"{width:>6} {r['body_cells']:>6} {len(r['split_in_token']):>6} "
            f"{r['wrapped_at_space']:>9} {sparse:>12} {r['tall_cells']:>5} "
            f"{len(r['clipped_cells']):>8} {r['wider_than_measure']:>5} "
            f"{len(r['scrolling_pages']):>10}"
        )
    first = next(iter(results.values()))
    print(
        f"shapes: {sum(first['ledgers'].values())} ledgers, "
        f"{sum(first['grids'].values())} grids, {first['tables']} tables"
    )
    for page in sorted(set(first["ledgers"]) | set(first["grids"])):
        print(
            f"  {page}: {first['ledgers'].get(page, 0)} ledgers, "
            f"{first['grids'].get(page, 0)} grids"
        )
    for width, r in results.items():
        for key in ("split_in_token", "clipped_cells", "scrolling_pages"):
            for item in r[key]:
                print(f"  {width}px {key}: {item}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("site_dir", type=Path, help="a built reader site (BOOK/dist/site)")
    parser.add_argument(
        "--widths", default="1280,820,390", help="comma-separated viewport widths in CSS pixels"
    )
    parser.add_argument("--json", action="store_true", help="print the results as JSON")
    parser.add_argument(
        "--fail-on-any",
        action="store_true",
        help="exit 1 on any in-token split, clipped cell, or sideways page",
    )
    args = parser.parse_args(argv)

    chrome_path = check_layout.find_chrome()
    if chrome_path is None:
        print(
            "~ table measurement skipped: no Chrome/Chromium found (set PRESS_CHROME to its path)"
        )
        return 0
    if not args.site_dir.is_dir():
        parser.error(f"{args.site_dir} is not a directory")
    widths = [int(w) for w in args.widths.split(",") if w.strip()]
    results = measure_site(args.site_dir, widths, chrome_path)
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        report(results)
    return 1 if args.fail_on_any and failures(results) else 0


if __name__ == "__main__":
    sys.exit(main())
