"""Verify every table on an HTML surface is in a shape the press renders.

``table-shapes.lua`` turns every table into one of two forms: a ledger (a
``div.ledger`` holding a definition list) or a grid (a ``div.grid`` holding
the table), and ``webmeta.label_table_cells`` stamps each body cell of a
headed grid with its column's header so a phone can stack the row into a
labelled card. A bare table is the one form that crushes on a phone, so its
appearance on a rendered surface is refused here (INV-table-shape).
"""

from __future__ import annotations

import re

_TABLE_TAG = re.compile(r"<(/?)(div|table|dt)\b([^>]*)>", re.I)
_CLASS_ATTR = re.compile(r"""\bclass\s*=\s*["']([^"']*)["']""", re.I)
_TAGS = re.compile(r"<[^>]+>")


def _classes(attrs: str) -> set[str]:
    """The class tokens of one tag's attribute text."""

    found = _CLASS_ATTR.search(attrs)
    return set(found.group(1).split()) if found else set()


def _empty_ledger(frame: dict) -> bool:
    return frame["ledger"] and not frame["entries"]


def _open(stack: list[dict], tag: str, attrs: str, label: str) -> None:
    """Push an opening div or table; a table must open directly in a grid."""

    if tag == "table":
        parent = stack[-1] if stack else None
        if parent is None or parent["tag"] != "div" or "grid" not in parent["classes"]:
            raise SystemExit(f"{label}: table outside a grid wrapper")
    classes = _classes(attrs)
    stack.append({"tag": tag, "classes": classes, "ledger": "ledger" in classes, "entries": 0})


def _close(stack: list[dict], tag: str, label: str) -> None:
    """Pop to the matching opener; a ledger closing with no entry is refused."""

    while stack:
        frame = stack.pop()
        if _empty_ledger(frame):
            raise SystemExit(f"{label}: ledger without an entry")
        if frame["tag"] == tag:
            return


def _count_entry(stack: list[dict]) -> None:
    """Credit a ``<dt>`` to every open ledger, so an author's ``.ledger`` div
    nested around the press's own wrapper never closes as empty."""

    for frame in stack:
        if frame["ledger"]:
            frame["entries"] += 1


def _require_wrapped_tables(markup: str, label: str) -> None:
    """Every table sits directly inside a ``div.grid``; every ``div.ledger``
    carries at least one ``<dt>`` entry before it closes."""

    stack: list[dict] = []
    for match in _TABLE_TAG.finditer(markup):
        closing, tag, attrs = match.group(1), match.group(2).lower(), match.group(3)
        if tag == "dt":
            if not closing:
                _count_entry(stack)
        elif closing:
            _close(stack, tag, label)
        else:
            _open(stack, tag, attrs, label)
    if any(_empty_ledger(frame) for frame in stack):
        raise SystemExit(f"{label}: ledger without an entry")


def _headed(table: str) -> bool:
    """A table with a header row carrying text: the labeller's own reading."""

    head = re.search(r"<thead>(.*?)</thead>", table, re.S | re.I)
    if not head:
        return False
    headers = re.findall(r"<th\b[^>]*>(.*?)</th>", head.group(1), re.S | re.I)
    return any(_TAGS.sub("", header).strip() for header in headers)


def _require_labelled_rows(markup: str, label: str) -> None:
    """Every body row of a headed table carries ``data-label`` on its cells,
    judged by the same reading ``webmeta.label_table_cells`` stamps by: a
    table whose header row is absent or blank is headless and owes none."""

    for table in re.findall(r"<table\b.*?</table>", markup, re.S | re.I):
        body = re.search(r"<tbody>(.*?)</tbody>", table, re.S | re.I)
        if not body or not _headed(table):
            continue
        for row in re.findall(r"<tr\b[^>]*>.*?</tr>", body.group(1), re.S | re.I):
            cells = re.search(r"<td\b", row, re.I)
            labelled = re.search(r"<td\b[^>]*\bdata-label=", row, re.I)
            if cells and not labelled:
                raise SystemExit(f"{label}: grid row without data-label")


def verify_tables(markup: str, label: str, *, labels: bool = True) -> None:
    """Every table on an HTML surface is in one of the two shapes the press
    renders (INV-table-shape): a ``div.grid`` holding a table whose headed
    body rows carry ``data-label`` cells, or a ``div.ledger`` holding a
    definition list with at least one entry. A bare table, an unlabelled
    headed row, or an empty ledger is refused, keyed to ``label``.

    ``labels=False`` drops the ``data-label`` demand for a surface that
    stacks no phone cards: the EPUB, whose stylesheet has no card rules and
    whose build stamps no labels, still owes the wrapper and the entries."""

    _require_wrapped_tables(markup, label)
    if labels:
        _require_labelled_rows(markup, label)
