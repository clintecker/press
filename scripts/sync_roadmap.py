#!/usr/bin/env python3
"""Render the roadmap and reconcile its milestone registry with GitHub.

The checked-in registry is authoritative. GitHub milestones are a mutable
execution view, and ROADMAP.md is the human/site view. This script makes both
projections mechanically comparable without making a network call during the
ordinary documentation build.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "roadmap" / "milestones.json"
ROADMAP = ROOT / "ROADMAP.md"
START = "<!-- BEGIN GENERATED MILESTONES -->"
END = "<!-- END GENERATED MILESTONES -->"
BARE_URL = re.compile(r"https://[^\s]+")


def load_registry() -> dict[str, Any]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise SystemExit("unsupported roadmap registry schema")
    if not isinstance(data.get("repository"), str) or "/" not in data["repository"]:
        raise SystemExit("roadmap registry requires an owner/repository name")

    milestones = data.get("milestones")
    if not isinstance(milestones, list) or not milestones:
        raise SystemExit("roadmap registry requires milestones")
    numbers: set[int] = set()
    titles: set[str] = set()
    for item in milestones:
        required = {"number", "title", "state", "description"}
        if not isinstance(item, dict) or set(item) != required:
            raise SystemExit(f"milestone must contain exactly {sorted(required)}: {item!r}")
        number = item["number"]
        title = item["title"]
        if not isinstance(number, int) or number < 1 or number in numbers:
            raise SystemExit(f"invalid or duplicate milestone number: {number!r}")
        if not isinstance(title, str) or not title or title in titles:
            raise SystemExit(f"invalid or duplicate milestone title: {title!r}")
        if item["state"] not in {"open", "closed"}:
            raise SystemExit(f"invalid state for milestone {number}: {item['state']!r}")
        if not isinstance(item["description"], str) or not item["description"].strip():
            raise SystemExit(f"milestone {number} requires a description")
        numbers.add(number)
        titles.add(title)
    return data


def render(data: dict[str, Any]) -> str:
    repository = data["repository"]
    blocks = [START, ""]
    for item in data["milestones"]:
        number = item["number"]
        url = f"https://github.com/{repository}/milestone/{number}"
        state = "Open" if item["state"] == "open" else "Complete"
        description = BARE_URL.sub(
            lambda match: f"<{match.group(0).rstrip('.,;:')}>"
            + match.group(0)[len(match.group(0).rstrip('.,;:')) :],
            item["description"],
        )
        blocks.extend(
            [
                f"### [{item['title']}]({url}) · {state}",
                "",
                description,
                "",
            ]
        )
    blocks.append(END)
    return "\n".join(blocks)


def projected_roadmap(data: dict[str, Any]) -> str:
    current = ROADMAP.read_text(encoding="utf-8")
    if current.count(START) != 1 or current.count(END) != 1:
        raise SystemExit("ROADMAP.md must contain one generated milestone block")
    before, remainder = current.split(START, 1)
    _, after = remainder.split(END, 1)
    return before + render(data) + after


def write_or_check(data: dict[str, Any], *, check: bool) -> int:
    projected = projected_roadmap(data)
    current = ROADMAP.read_text(encoding="utf-8")
    if check:
        if current != projected:
            print("ROADMAP.md is stale; run: python3 scripts/sync_roadmap.py --write", file=sys.stderr)
            return 1
        print("+ ROADMAP.md matches roadmap/milestones.json")
        return 0
    ROADMAP.write_text(projected, encoding="utf-8")
    print("+ wrote ROADMAP.md from roadmap/milestones.json")
    return 0


def gh(*args: str, input_data: str | None = None) -> Any:
    result = subprocess.run(
        ["gh", *args],
        cwd=ROOT,
        input=input_data,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise SystemExit(result.stderr.strip() or f"gh exited {result.returncode}")
    return json.loads(result.stdout) if result.stdout.strip() else None


def github_drift(data: dict[str, Any], *, apply: bool) -> int:
    repository = data["repository"]
    drift: list[str] = []
    for expected in data["milestones"]:
        number = expected["number"]
        endpoint = f"repos/{repository}/milestones/{number}"
        actual = gh("api", endpoint)
        differences = [
            key
            for key in ("title", "state", "description")
            if actual.get(key) != expected[key]
        ]
        if not differences:
            continue
        drift.append(f"milestone {number}: {', '.join(differences)}")
        if apply:
            payload = {key: expected[key] for key in ("title", "state", "description")}
            gh("api", "--method", "PATCH", endpoint, "--input", "-", input_data=json.dumps(payload))
            print(f"+ synchronized milestone {number}: {expected['title']}")
    if drift and not apply:
        print("GitHub milestone drift:\n  - " + "\n  - ".join(drift), file=sys.stderr)
        print("run: python3 scripts/sync_roadmap.py --apply-github", file=sys.stderr)
        return 1
    if not drift:
        print("+ GitHub milestones match roadmap/milestones.json")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true", help="render ROADMAP.md")
    action.add_argument("--check", action="store_true", help="fail if ROADMAP.md is stale")
    action.add_argument("--check-github", action="store_true", help="fail on GitHub metadata drift")
    action.add_argument("--apply-github", action="store_true", help="reconcile GitHub metadata")
    args = parser.parse_args()
    data = load_registry()
    if args.write or args.check:
        return write_or_check(data, check=args.check)
    return github_drift(data, apply=args.apply_github)


if __name__ == "__main__":
    raise SystemExit(main())
