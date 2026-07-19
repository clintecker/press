"""The operator: press improve and press research, no session required.

The packaged agent workflows run headlessly through the Claude Code CLI
(`claude -p` hosting the Workflow tool), so "process this directory for
prose quality" and "research the claims" are shell commands. The
default posture is counsel, not surgery: press improve writes
build/editorial-report.md and touches nothing; --apply is the
deliberate hand on the manuscript.
"""

from __future__ import annotations

import json
import shutil
import subprocess

from . import booklib, instruments


TIMEOUT_SECONDS = 3600


def run_workflow(name: str, args_obj: dict, full_bash: bool,
                 extra_tools: list[str] | None = None) -> int:
    """Drive a packaged workflow headlessly.

    Report/research modes get Bash scoped to press commands; --apply
    grants the session full Bash with edits auto-accepted, because the
    law phase reruns press check and fixes violations. That is a real
    grant of shell access to an agent session; it is the deliberate
    meaning of --apply, and the counsel modes never receive it.
    """

    if shutil.which("claude") is None:
        raise SystemExit(
            "the operator needs the Claude Code CLI on PATH "
            "(https://claude.com/claude-code); inside a session, run the "
            f"workflow directly: Workflow({{name: \"{name}\", args: ...}})"
        )
    path = instruments.workflow_paths().get(name)
    if path is None:
        raise SystemExit(f"no packaged workflow named {name}")
    prompt = (
        f"Use the Workflow tool with scriptPath {json.dumps(str(path))} and "
        f"args {json.dumps(args_obj)}. When it completes, report its "
        "returned result and nothing else."
    )
    bash_grant = ["Bash"] if full_bash else ["Bash(press:*)", "Bash(python3:*)"]
    bash_grant += extra_tools or []
    print(f"operator: {name} on {args_obj['root']} (this runs agents; minutes, not seconds)")
    try:
        completed = subprocess.run(
            ["claude", "-p", prompt,
             "--allowedTools", "Workflow", *bash_grant,
             "--permission-mode", "acceptEdits",
             "--output-format", "text"],
            cwd=booklib.root(),
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        raise SystemExit(
            f"the headless session exceeded {TIMEOUT_SECONDS}s and was "
            "stopped; rerun, or run the workflow in a live session to watch it"
        )
    return completed.returncode


def _manuscript_fingerprint(root):
    """Hash of every manuscript and config byte, for proving counsel
    mode kept its hands off."""

    import hashlib

    digest = hashlib.sha256()
    for base in ("book", "config"):
        directory = root / base
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                digest.update(str(path.relative_to(root)).encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()


def improve(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="press improve")
    parser.add_argument("--apply", action="store_true",
                        help="apply the suggestions instead of writing the report")
    parser.add_argument("--rounds", type=int, default=2,
                        help="editorial rounds when applying (default 2)")
    args = parser.parse_args(argv)
    root = booklib.root()
    workflow_args = {"root": str(root), "report": not args.apply}
    if args.apply:
        workflow_args["rounds"] = args.rounds
    before = None if args.apply else _manuscript_fingerprint(root)
    code = run_workflow("editorial-passes", workflow_args, full_bash=args.apply)
    if code == 0 and not args.apply:
        # "Touches nothing" is proven, not promised: the manuscript and
        # config must hash identically after a counsel run.
        if _manuscript_fingerprint(root) != before:
            raise SystemExit(
                "counsel mode changed the manuscript or config; that "
                "violates its contract. Review with git diff, restore, "
                "and report this as a press bug."
            )
        report = root / "build" / "editorial-report.md"
        if report.is_file():
            print(f"report: {report} (manuscript proven untouched)")
        else:
            raise SystemExit(
                "the workflow finished but wrote no report; read its output above"
            )
    return code


def aesthetic(argv: list[str]) -> int:
    """Bare: print the effective visual identity. With a brief: draft
    config/aesthetic.yaml from it through the aesthetic-brief workflow."""

    import argparse

    from . import aesthetic as aesthetic_config

    if not argv:
        return aesthetic_config.show()
    parser = argparse.ArgumentParser(prog="press aesthetic")
    parser.add_argument("brief", nargs="+",
                        help="the look, in the author's words")
    parser.add_argument("--overwrite", action="store_true",
                        help="replace an existing config/aesthetic.yaml")
    args = parser.parse_args(argv)
    workflow_args: dict = {
        "root": str(booklib.root()),
        "brief": " ".join(args.brief),
    }
    if args.overwrite:
        workflow_args["overwrite"] = True
    code = run_workflow("aesthetic-brief", workflow_args, full_bash=False)
    if code == 0:
        print("review it: press aesthetic")
    return code


def research(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="press research")
    parser.add_argument("--max-claims-per-file", type=int, default=None)
    args = parser.parse_args(argv)
    workflow_args: dict = {"root": str(booklib.root())}
    if args.max_claims_per_file:
        workflow_args["maxClaimsPerFile"] = args.max_claims_per_file
    # Research is the one counsel workflow that must reach the web:
    # its whole job is finding and auditing real sources.
    return run_workflow("authorities-research", workflow_args, full_bash=False,
                        extra_tools=["WebSearch", "WebFetch"])
