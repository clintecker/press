#!/usr/bin/env python3
"""
Report watched jargon in Markdown or plain-text files.

The checker is intentionally mechanical. It finds exact watchlist matches while
skipping code, URLs, and quoted Markdown by default. Human or model judgment is
still required to decide whether an "inspect" term is precise in context.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


# Higher numbers are stricter findings.
STATUS_LEVEL = {
    "allow": 0,
    "inspect": 1,
    "rewrite": 2,
    "ban": 3,
}


@dataclass(frozen=True)
class Rule:
    """One watchlist rule loaded from CSV."""

    term: str
    match: str
    status: str
    category: str
    question: str
    allowed_when: str
    source: str
    notes: str


@dataclass(frozen=True)
class Finding:
    """One term occurrence in a source file."""

    path: str
    line: int
    column: int
    term: str
    status: str
    category: str
    question: str
    context: str


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse command-line arguments."""

    default_watchlist = (
        Path(__file__).resolve().parent / "data" / "jargon" / "watchlist.csv"
    )

    parser = argparse.ArgumentParser(
        description="Find watched jargon in Markdown or plain-text files."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Files to scan. Reads stdin when no path is supplied.",
    )
    parser.add_argument(
        "--watchlist",
        type=Path,
        default=default_watchlist,
        help=f"Watchlist CSV (default: {default_watchlist}).",
    )
    parser.add_argument(
        "--fail-on",
        choices=("none", "inspect", "rewrite", "ban"),
        default="rewrite",
        help="Return exit code 1 when this status or a stricter status is found.",
    )
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        metavar="TERM",
        help="Allow one term for this run. May be repeated.",
    )
    parser.add_argument(
        "--include-quotes",
        action="store_true",
        help="Also scan Markdown blockquotes. They are skipped by default.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON array instead of human-readable lines.",
    )
    parser.add_argument(
        "--max-findings",
        type=int,
        default=500,
        help="Stop after this many findings (default: 500).",
    )
    return parser.parse_args(argv)


def load_rules(path: Path) -> list[Rule]:
    """Load and validate the watchlist."""

    required = {
        "term",
        "match",
        "status",
        "category",
        "question",
        "allowed_when",
        "source",
        "notes",
    }

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: missing CSV header")

        missing = required.difference(reader.fieldnames)
        if missing:
            joined = ", ".join(sorted(missing))
            raise ValueError(f"{path}: missing columns: {joined}")

        rules: list[Rule] = []
        for row_number, row in enumerate(reader, start=2):
            term = row["term"].strip()
            match = row["match"].strip().lower()
            status = row["status"].strip().lower()

            if not term:
                raise ValueError(f"{path}:{row_number}: empty term")
            if match not in {"word", "phrase", "regex"}:
                raise ValueError(
                    f"{path}:{row_number}: match must be word, phrase, or regex"
                )
            if status not in STATUS_LEVEL:
                raise ValueError(
                    f"{path}:{row_number}: unknown status {status!r}"
                )

            rules.append(
                Rule(
                    term=term,
                    match=match,
                    status=status,
                    category=row["category"].strip(),
                    question=row["question"].strip(),
                    allowed_when=row["allowed_when"].strip(),
                    source=row["source"].strip(),
                    notes=row["notes"].strip(),
                )
            )

    # Match longer phrases first so a phrase can be reported before a component word.
    return sorted(rules, key=lambda rule: (-len(rule.term), rule.term.lower()))


def blank_preserving_newlines(text: str) -> str:
    """Replace every non-newline character with a space."""

    return "".join("\n" if char == "\n" else " " for char in text)


def strip_nonprose(text: str, *, include_quotes: bool) -> str:
    """
    Hide content that should not be linted while preserving offsets.

    Preserving string length and newline positions lets later matches map back to
    the original line and column without maintaining a separate source map.
    """

    cleaned = text

    # Hide fenced Markdown code blocks.
    fenced_code = re.compile(r"(?ms)^([ \t]*)(`{3,}|~{3,}).*?^\1\2[ \t]*$")
    cleaned = fenced_code.sub(
        lambda match: blank_preserving_newlines(match.group(0)),
        cleaned,
    )

    # Hide inline code. This deliberately handles ordinary Markdown, not every
    # possible nested-backtick construction.
    inline_code = re.compile(r"`+[^`\n]*`+")
    cleaned = inline_code.sub(
        lambda match: " " * len(match.group(0)),
        cleaned,
    )

    # Hide URLs while leaving surrounding prose in place.
    url = re.compile(r"https?://[^\s<>()]+")
    cleaned = url.sub(lambda match: " " * len(match.group(0)), cleaned)

    if not include_quotes:
        # Hide Markdown blockquotes because quoted source text should normally be
        # preserved rather than "corrected" by a house-style checker.
        quote_line = re.compile(r"(?m)^[ \t]*>.*$")
        cleaned = quote_line.sub(
            lambda match: " " * len(match.group(0)),
            cleaned,
        )

    return cleaned


def compile_rule(rule: Rule) -> re.Pattern[str]:
    """Compile a case-insensitive matcher for one rule."""

    if rule.match == "regex":
        return re.compile(rule.term, re.IGNORECASE)

    escaped = re.escape(rule.term)

    # Word-like boundaries reject letters, digits, underscores, and hyphens on
    # either side. This prevents "gate" from matching "gateway" and "load" from
    # matching part of a hyphenated identifier.
    return re.compile(
        rf"(?<![\w-]){escaped}(?![\w-])",
        re.IGNORECASE,
    )


def line_and_column(text: str, offset: int) -> tuple[int, int]:
    """Convert a zero-based character offset to one-based line and column."""

    line = text.count("\n", 0, offset) + 1
    previous_newline = text.rfind("\n", 0, offset)
    column = offset - previous_newline
    return line, column


def line_context(text: str, offset: int, width: int = 180) -> str:
    """Return a compact single-line excerpt around a match."""

    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    if end == -1:
        end = len(text)

    context = text[start:end].strip()
    if len(context) <= width:
        return context
    return context[: width - 1].rstrip() + "…"


def scan_text(
    *,
    path: str,
    text: str,
    rules: Iterable[Rule],
    allowed_terms: set[str],
    include_quotes: bool,
    remaining: int,
) -> list[Finding]:
    """Scan one text value and return findings."""

    cleaned = strip_nonprose(text, include_quotes=include_quotes)
    findings: list[Finding] = []

    for rule in rules:
        if rule.status == "allow":
            continue
        if rule.term.casefold() in allowed_terms:
            continue

        pattern = compile_rule(rule)
        for match in pattern.finditer(cleaned):
            line, column = line_and_column(text, match.start())
            findings.append(
                Finding(
                    path=path,
                    line=line,
                    column=column,
                    term=match.group(0),
                    status=rule.status,
                    category=rule.category,
                    question=rule.question,
                    context=line_context(text, match.start()),
                )
            )
            if len(findings) >= remaining:
                return findings

    # Present findings in source order rather than watchlist order.
    return sorted(findings, key=lambda item: (item.line, item.column, item.term.lower()))


def read_inputs(paths: Sequence[str]) -> list[tuple[str, str]]:
    """Read named files or stdin."""

    if not paths:
        return [("<stdin>", sys.stdin.read())]

    inputs: list[tuple[str, str]] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_file():
            raise FileNotFoundError(f"{path}: not a file")
        inputs.append((str(path), path.read_text(encoding="utf-8")))
    return inputs


def print_text(findings: Sequence[Finding]) -> None:
    """Print findings in a compiler-like format."""

    for finding in findings:
        print(
            f"{finding.path}:{finding.line}:{finding.column}: "
            f"{finding.status}: {finding.term!r} [{finding.category}]"
        )
        if finding.context:
            print(f"  {finding.context}")
        if finding.question:
            print(f"  Ask: {finding.question}")


def should_fail(findings: Sequence[Finding], fail_on: str) -> bool:
    """Return whether the selected threshold should fail the process."""

    if fail_on == "none":
        return False

    threshold = STATUS_LEVEL[fail_on]
    return any(STATUS_LEVEL[finding.status] >= threshold for finding in findings)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the checker."""

    args = parse_args(argv or sys.argv[1:])

    try:
        rules = load_rules(args.watchlist)
        inputs = read_inputs(args.paths)
    except (OSError, ValueError) as error:
        print(f"jargon_lint: {error}", file=sys.stderr)
        return 2

    allowed_terms = {term.casefold() for term in args.allow}
    findings: list[Finding] = []

    for path, text in inputs:
        remaining = args.max_findings - len(findings)
        if remaining <= 0:
            break
        findings.extend(
            scan_text(
                path=path,
                text=text,
                rules=rules,
                allowed_terms=allowed_terms,
                include_quotes=args.include_quotes,
                remaining=remaining,
            )
        )

    if args.json:
        print(json.dumps([asdict(item) for item in findings], indent=2))
    else:
        print_text(findings)
        if findings:
            print(f"\n{len(findings)} finding(s).", file=sys.stderr)

    return 1 if should_fail(findings, args.fail_on) else 0


if __name__ == "__main__":
    raise SystemExit(main())
