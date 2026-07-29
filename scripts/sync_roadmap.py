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
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

# The subset of milestone fields the reconcile is allowed to touch. It never
# creates or deletes a milestone and never edits an issue; it only aligns
# these three fields for milestone numbers already present in the registry.
RECONCILED_FIELDS = ("title", "state", "description")

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "roadmap" / "milestones.json"
ROADMAP = ROOT / "ROADMAP.md"
START = "<!-- BEGIN GENERATED MILESTONES -->"
END = "<!-- END GENERATED MILESTONES -->"
BARE_URL = re.compile(r"https://[^\s]+")


def _link_label(url: str) -> str:
    """A readable label for a bare GitHub/other URL, so the roadmap shows
    words instead of raw links. On the site the href is later rewritten to
    the local page; the label reads well on GitHub and the site alike."""

    import re as _re

    m = _re.search(r"/milestone/(\d+)", url)
    if m:
        return f"milestone {m.group(1)}"
    m = _re.search(r"/issues/(\d+)", url)
    if m:
        return f"issue {m.group(1)}"
    if "/issues?" in url or "/issues/" in url:
        return "the tracked issues"
    m = _re.search(r"/releases/tag/(v[\d.]+)", url)
    if m:
        return f"the {m.group(1)} release"
    m = _re.search(r"/blob/main/(?:docs/)?([A-Za-z][\w-]*)\.md", url)
    if m:
        name = m.group(1)
        friendly = {
            "ARCHITECTURE": "the architecture guide",
            "REFERENCE": "the command reference",
            "INSTALL": "the installation guide",
            "CONTRIBUTING": "the contributing guide",
            "ROADMAP": "the roadmap",
            "CHANGELOG": "the changelog",
            "TUI-PLAN": "the TUI plan",
            "INVARIANTS": "the invariant ledger",
        }
        return friendly.get(name, name.lower())
    m = _re.match(r"https?://([^/]+)", url)
    return m.group(1) if m else url


def _label_bare_urls(text: str) -> str:
    """Turn every bare URL in prose into a labeled Markdown link, keeping any
    trailing punctuation outside the link."""

    def repl(match: "re.Match[str]") -> str:
        raw = match.group(0)
        trail = ""
        while raw and raw[-1] in ".,;:":
            trail = raw[-1] + trail
            raw = raw[:-1]
        return f"[{_link_label(raw)}]({raw}){trail}"

    return BARE_URL.sub(repl, text)


def validate_groups(data: dict[str, Any]) -> set[str]:
    groups = data.get("groups")
    if not isinstance(groups, list) or not groups:
        raise SystemExit("roadmap registry requires presentation groups")
    group_ids: set[str] = set()
    for group in groups:
        required = {"id", "heading", "description"}
        if not isinstance(group, dict) or set(group) != required:
            raise SystemExit(f"group must contain exactly {sorted(required)}: {group!r}")
        group_id = group["id"]
        if not isinstance(group_id, str):
            raise SystemExit(f"invalid or duplicate group id: {group_id!r}")
        if not group_id.strip() or group_id != group_id.strip() or group_id in group_ids:
            raise SystemExit(f"invalid or duplicate group id: {group_id!r}")
        if not isinstance(group["heading"], str) or not group["heading"].strip():
            raise SystemExit(f"group {group_id!r} requires a heading")
        if not isinstance(group["description"], str) or not group["description"].strip():
            raise SystemExit(f"group {group_id!r} requires a description")
        group_ids.add(group_id)
    return group_ids


def validate_milestones(data: dict[str, Any], group_ids: set[str]) -> None:
    milestones = data.get("milestones")
    if not isinstance(milestones, list) or not milestones:
        raise SystemExit("roadmap registry requires milestones")
    numbers: set[int] = set()
    titles: set[str] = set()
    for item in milestones:
        required = {"number", "group", "title", "state", "description"}
        if not isinstance(item, dict) or set(item) != required:
            raise SystemExit(f"milestone must contain exactly {sorted(required)}: {item!r}")
        number = item["number"]
        title = item["title"]
        if item["group"] not in group_ids:
            raise SystemExit(f"unknown group for milestone {number}: {item['group']!r}")
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
    if "complete" not in group_ids:
        raise SystemExit(
            "roadmap registry requires the 'complete' group; closed milestones present there"
        )


def load_registry() -> dict[str, Any]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if data.get("schema_version") != 2:
        raise SystemExit("unsupported roadmap registry schema")
    if not isinstance(data.get("repository"), str) or "/" not in data["repository"]:
        raise SystemExit("roadmap registry requires an owner/repository name")
    validate_milestones(data, validate_groups(data))
    return data


COMPLETE_GROUP = "complete"


def effective_group(item: dict[str, Any]) -> str:
    """Closed milestones always present under the completed
    foundations, wherever they were scheduled; the registry's group
    field records intent, the state decides placement."""

    return COMPLETE_GROUP if item["state"] == "closed" else item["group"]


def render(data: dict[str, Any]) -> str:
    repository = data["repository"]
    blocks = [START, ""]
    for group in data["groups"]:
        members = [item for item in data["milestones"] if effective_group(item) == group["id"]]
        if not members:
            continue
        blocks.extend([f"## {group['heading']}", "", group["description"], ""])
        for item in members:
            number = item["number"]
            url = f"https://github.com/{repository}/milestone/{number}"
            state = "Open" if item["state"] == "open" else "Complete"
            description = _label_bare_urls(item["description"])
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
            print(
                "ROADMAP.md is stale; run: python3 scripts/sync_roadmap.py --write", file=sys.stderr
            )
            return 1
        print("+ ROADMAP.md matches roadmap/milestones.json")
        return 0
    ROADMAP.write_text(projected, encoding="utf-8")
    print("+ wrote ROADMAP.md from roadmap/milestones.json")
    return 0


class GhError(RuntimeError):
    """A GitHub API call failed for a reason worth retrying (network hiccup,
    5xx, rate limit). The reconcile retries these; if they persist it fails
    the run, visibly, rather than treating GitHub as the source of truth."""


class MilestoneNotFound(GhError):
    """A milestone number present in the registry does not exist on GitHub.
    This is definitive, never retried, and never repaired by creating one:
    the reconcile only aligns metadata for milestones that already exist."""


# The API surface the reconcile is allowed to reach. A milestone GET and a
# milestone PATCH, nothing else -- typed as a callable so a test can supply a
# fake boundary and prove no create/delete or issue write is ever attempted.
GhClient = Callable[..., Any]


def gh(*args: str, input_data: str | None = None) -> Any:
    try:
        result = subprocess.run(
            ["gh", *args],
            cwd=ROOT,
            input=input_data,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        raise SystemExit(
            "GitHub CLI 'gh' is required for GitHub roadmap synchronization; "
            "install it from https://cli.github.com/"
        ) from None
    if result.returncode:
        message = result.stderr.strip() or f"gh exited {result.returncode}"
        # A 404 on a milestone GET is definitive: the milestone is absent, and
        # the reconcile must skip it, never create it. Everything else is a
        # candidate for retry.
        if re.search(r"HTTP 404|Not Found", message):
            raise MilestoneNotFound(message)
        raise GhError(message)
    return json.loads(result.stdout) if result.stdout.strip() else None


def _with_retry(
    fn: Callable[[], Any],
    *,
    retries: int,
    sleep: Callable[[float], None],
) -> Any:
    """Run fn, retrying transient GhError up to `retries` extra times with a
    small backoff. A MilestoneNotFound is definitive and never retried."""

    for attempt in range(retries + 1):
        try:
            return fn()
        except MilestoneNotFound:
            raise
        except GhError:
            if attempt == retries:
                raise
            sleep(0.5 * (attempt + 1))


def _summary_lines(
    repository: str,
    sha: str | None,
    changed: list[tuple[int, str]],
    skipped: list[tuple[int, str]],
) -> list[str]:
    lines = ["## Roadmap reconcile", ""]
    if sha:
        commit = f"https://github.com/{repository}/commit/{sha}"
        lines.append(f"Source commit: [`{sha[:7]}`]({commit})")
    else:
        lines.append("Source commit: (unknown)")
    lines.append("")
    if changed:
        lines.append("Reconciled milestone metadata:")
        lines.append("")
        for number, title in changed:
            url = f"https://github.com/{repository}/milestone/{number}"
            lines.append(f"- [{title}]({url}) (milestone {number})")
    else:
        lines.append("No milestone metadata changes; GitHub already matched the registry.")
    if skipped:
        lines.append("")
        lines.append("Absent on GitHub (never created by the reconcile):")
        lines.append("")
        for number, title in skipped:
            lines.append(f"- {title} (milestone {number})")
    lines.append("")
    return lines


def _write_summary(env: Mapping[str, str], text: str) -> None:
    """Append the durable job summary to $GITHUB_STEP_SUMMARY when the runner
    sets it; a no-op locally so the script stays useful off CI."""

    path = env.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")


def github_drift(
    data: dict[str, Any],
    *,
    apply: bool,
    api: GhClient = gh,
    env: Mapping[str, str] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    retries: int = 2,
) -> int:
    env = os.environ if env is None else env
    repository = data["repository"]
    drift: list[str] = []
    changed: list[tuple[int, str]] = []
    skipped: list[tuple[int, str]] = []
    failures: list[str] = []
    for expected in data["milestones"]:
        number = expected["number"]
        title = expected["title"]
        endpoint = f"repos/{repository}/milestones/{number}"
        try:
            actual = _with_retry(lambda: api("api", endpoint), retries=retries, sleep=sleep)
        except MilestoneNotFound:
            # Present in the registry, absent on GitHub. Never create it; the
            # reconcile only aligns metadata for milestones that exist. The
            # scheduled read-only drift alarm still reports the absence.
            print(f"! milestone {number} absent on GitHub; not created ({title})", file=sys.stderr)
            skipped.append((number, title))
            continue
        except GhError as error:
            failures.append(f"milestone {number}: {error}")
            continue
        differences = [key for key in RECONCILED_FIELDS if actual.get(key) != expected[key]]
        if not differences:
            continue
        drift.append(f"milestone {number}: {', '.join(differences)}")
        if not apply:
            continue
        payload = json.dumps({key: expected[key] for key in RECONCILED_FIELDS})
        try:
            _with_retry(
                lambda: api(
                    "api", "--method", "PATCH", endpoint, "--input", "-", input_data=payload
                ),
                retries=retries,
                sleep=sleep,
            )
        except GhError as error:
            failures.append(f"milestone {number}: {error}")
            continue
        print(f"+ synchronized milestone {number}: {title}")
        changed.append((number, title))

    if apply:
        _write_summary(
            env, "\n".join(_summary_lines(repository, env.get("GITHUB_SHA"), changed, skipped))
        )

    if failures:
        print("GitHub reconcile failed:\n  - " + "\n  - ".join(failures), file=sys.stderr)
        return 1
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
