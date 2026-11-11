#!/usr/bin/env python3
"""Early warning for producer-ledger pending entries nearing their review date.

`.celebrimbor/producers.yaml` carries `pending` entries, each with a
`review_by` date. When one passes, the quality gate fails every push with no
warning beforehand. This script lists entries that are within a horizon of
expiring (or already expired) and, with `--open-issue`, opens or updates one
GitHub issue so the debt is seen weeks ahead.

It warns; it never fails: the exit status is 0 whether or not anything is
expiring.

This script lives outside `src/press`, so the adapters boundary gate (no
direct subprocess calls) does not apply; it calls `subprocess.run` directly
to drive the `gh` CLI. A dry run (no `--open-issue`) never calls `gh`.

Usage: python3 scripts/ledger_review_watch.py
           [--today YYYY-MM-DD] [--horizon 30] [--open-issue]
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = "clintecker/press"
LEDGER_PATH = Path(".celebrimbor") / "producers.yaml"
TITLE = "Producer ledger: pending entries expire within 30 days"
LABEL = "maintenance"

Row = tuple[str, dt.date, str]


def expiring(ledger: dict[str, Any], today: dt.date, horizon_days: int = 30) -> list[Row]:
    """Pending entries due on or before today + horizon, soonest first.

    Already-expired entries are included.
    """
    cutoff = today + dt.timedelta(days=horizon_days)
    rows: list[Row] = []
    for subject, entry in (ledger.get("pending") or {}).items():
        due = dt.date.fromisoformat(str(entry["review_by"]))
        if due <= cutoff:
            rows.append((subject, due, str(entry.get("reason", "")).strip()))
    return sorted(rows, key=lambda r: (r[1], r[0]))


def render_issue(rows: list[Row]) -> tuple[str, str]:
    """Return (title, body) for the tracking issue."""
    lines = [
        "These pending producer-ledger entries are within 30 days of their "
        "`review_by` date (or past it). When the date passes, the quality "
        "gate fails every push.",
        "",
        "| Subject | review_by | Reason |",
        "| --- | --- | --- |",
    ]
    for subject, due, reason in rows:
        lines.append(f"| `{subject}` | {due.isoformat()} | {' '.join(reason.split())} |")
    lines += [
        "",
        "Resolve each by writing the owed verifier and its negative fixture, "
        "not by moving the date. See CONTRIBUTING.md, \"What a proof has to "
        "prove\".",
        "",
        "Maintained by `scripts/ledger_review_watch.py` "
        "(`.github/workflows/ledger-review.yml`).",
    ]
    return TITLE, "\n".join(lines) + "\n"


def issue_action(existing_number: int | None) -> str:
    """Which `gh issue` subcommand to run given the number found, if any."""
    return "create" if existing_number is None else "edit"


def _gh(args: list[str]) -> str:
    done = subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
    return done.stdout


def open_issue(title: str, body: str) -> None:
    """Open the tracking issue, or update the open one with the same title."""
    found = _gh(
        [
            "issue", "list", "--repo", REPO, "--state", "open",
            "--search", f'"{title}" in:title',
            "--json", "number", "--jq", ".[0].number",
        ]
    ).strip()
    number = int(found) if found else None
    with tempfile.TemporaryDirectory() as tmp:
        body_file = Path(tmp) / "body.md"
        body_file.write_text(body, encoding="utf-8")
        if issue_action(number) == "edit":
            _gh(["issue", "edit", str(number), "--repo", REPO, "--body-file", str(body_file)])
        else:
            _gh(
                [
                    "issue", "create", "--repo", REPO, "--title", title,
                    "--body-file", str(body_file), "--label", LABEL,
                ]
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--today", type=dt.date.fromisoformat, default=None)
    parser.add_argument("--horizon", type=int, default=30)
    parser.add_argument("--open-issue", action="store_true")
    args = parser.parse_args(argv)

    from press import yamlio

    today = args.today or dt.date.today()
    rows = expiring(yamlio.load(LEDGER_PATH), today, args.horizon)
    if not rows:
        print(f"No pending ledger entries expire within {args.horizon} days of {today}.")
        return 0
    print(f"{len(rows)} pending ledger entries expire within {args.horizon} days of {today}:")
    for subject, due, reason in rows:
        print(f"  {due}  {subject}  {' '.join(reason.split())}")
    if args.open_issue:
        open_issue(*render_issue(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
