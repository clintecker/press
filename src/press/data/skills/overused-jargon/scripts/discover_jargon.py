#!/usr/bin/env python3
"""
Rank phrases that are unusually common in one corpus versus a baseline.

The script is a discovery aid, not an authorship detector and not an automatic
blacklist generator. It strips common Markdown/code material, counts one- to
three-word phrases, applies additive smoothing, and writes a reviewable CSV.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


TEXT_SUFFIXES = {
    ".txt",
    ".md",
    ".markdown",
    ".rst",
    ".jsonl",
    ".log",
}

# This deliberately small list removes grammatical glue without attempting to
# model all English stop words. A candidate may include stop words when it also
# contains a meaningful token, as in "at its core".
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by",
    "can", "could", "did", "do", "does", "for", "from", "had", "has",
    "have", "he", "her", "here", "hers", "him", "his", "how", "i", "if",
    "in", "into", "is", "it", "its", "may", "me", "might", "more", "most",
    "my", "no", "not", "of", "on", "or", "our", "ours", "she", "should",
    "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "then", "there", "these", "they", "this", "those", "to", "too", "us",
    "was", "we", "were", "what", "when", "where", "which", "who", "why",
    "will", "with", "would", "you", "your", "yours",
}

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-'][A-Za-z0-9]+)*")


@dataclass
class CorpusStats:
    """Counts for a corpus."""

    counts: Counter[str]
    documents: Counter[str]
    total_ngrams: Counter[int]
    examples: dict[str, list[str]]
    document_count: int


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Find phrases overrepresented in a model corpus."
    )
    parser.add_argument(
        "--model",
        nargs="+",
        required=True,
        help="Files or directories containing the corpus under review.",
    )
    parser.add_argument(
        "--baseline",
        nargs="+",
        required=True,
        help="Files or directories containing comparable human/domain prose.",
    )
    parser.add_argument(
        "--known",
        type=Path,
        help="Existing watchlist CSV. Used with --novel-only.",
    )
    parser.add_argument(
        "--novel-only",
        action="store_true",
        help="Exclude terms already present in --known.",
    )
    parser.add_argument(
        "--ngrams",
        default="1,2,3",
        help="Comma-separated n-gram sizes (default: 1,2,3).",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=3,
        help="Minimum total model-corpus count (default: 3).",
    )
    parser.add_argument(
        "--min-docs",
        type=int,
        default=2,
        help="Minimum model documents containing the phrase (default: 2).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=200,
        help="Maximum rows to write (default: 200).",
    )
    parser.add_argument(
        "--smoothing",
        type=float,
        default=0.5,
        help="Additive count used when a phrase is rare or absent (default: 0.5).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output CSV. Writes to stdout when omitted.",
    )
    return parser.parse_args(argv)


def parse_ngram_sizes(value: str) -> tuple[int, ...]:
    """Parse and validate n-gram sizes."""

    try:
        sizes = tuple(sorted({int(part.strip()) for part in value.split(",")}))
    except ValueError as error:
        raise ValueError("--ngrams must contain integers") from error

    if not sizes or any(size < 1 or size > 5 for size in sizes):
        raise ValueError("--ngrams must use sizes from 1 through 5")
    return sizes


def iter_files(items: Sequence[str]) -> Iterator[Path]:
    """Yield supported text files from files or directories."""

    seen: set[Path] = set()

    for raw_item in items:
        item = Path(raw_item)
        if item.is_file():
            resolved = item.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield item
            continue

        if item.is_dir():
            for path in sorted(item.rglob("*")):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in TEXT_SUFFIXES:
                    continue
                resolved = path.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    yield path
            continue

        raise FileNotFoundError(f"{item}: not found")


def blank_preserving_newlines(text: str) -> str:
    """Replace non-newline characters with spaces."""

    return "".join("\n" if char == "\n" else " " for char in text)


def prose_only(text: str) -> str:
    """Remove common code, URL, quote, and log-like material."""

    # Markdown fenced code.
    text = re.sub(
        r"(?ms)^([ \t]*)(`{3,}|~{3,}).*?^\1\2[ \t]*$",
        lambda match: blank_preserving_newlines(match.group(0)),
        text,
    )

    # Inline code and URLs.
    text = re.sub(r"`+[^`\n]*`+", " ", text)
    text = re.sub(r"https?://[^\s<>()]+", " ", text)

    # Markdown blockquotes and common log/stack-trace lines.
    kept_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(">"):
            continue
        if re.match(r"^\s*(Traceback|File \".*\", line \d+|at \S+\()", line):
            continue
        if line.count("{") + line.count("}") > 6:
            continue
        kept_lines.append(line)

    return "\n".join(kept_lines)


def tokenize(text: str) -> list[str]:
    """Return normalized word tokens."""

    tokens: list[str] = []
    for match in TOKEN_RE.finditer(text):
        token = match.group(0).lower()

        # Skip obvious identifiers, hashes, and mostly numeric tokens.
        if "_" in token:
            continue
        if len(token) > 40:
            continue
        if sum(char.isdigit() for char in token) > len(token) // 2:
            continue

        tokens.append(token)

    return tokens


def useful_ngram(parts: Sequence[str]) -> bool:
    """Filter phrases made only of grammar words or obvious noise."""

    if not parts:
        return False
    if all(part in STOP_WORDS for part in parts):
        return False
    if all(len(part) <= 2 for part in parts):
        return False
    return True


def iter_ngrams(tokens: Sequence[str], sizes: Sequence[int]) -> Iterator[tuple[int, str]]:
    """Yield normalized n-grams."""

    for size in sizes:
        if len(tokens) < size:
            continue
        for index in range(len(tokens) - size + 1):
            parts = tokens[index : index + size]
            if useful_ngram(parts):
                yield size, " ".join(parts)


def compact_example(line: str, width: int = 220) -> str:
    """Normalize one source line for a CSV example cell."""

    line = " ".join(line.split())
    if len(line) <= width:
        return line
    return line[: width - 1].rstrip() + "…"


def collect_corpus(paths: Iterable[Path], sizes: Sequence[int]) -> CorpusStats:
    """Count phrases and document frequency for a corpus."""

    counts: Counter[str] = Counter()
    documents: Counter[str] = Counter()
    total_ngrams: Counter[int] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    document_count = 0

    for path in paths:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            raise OSError(f"{path}: {error}") from error

        document_count += 1
        prose = prose_only(raw)
        tokens = tokenize(prose)
        local_terms: set[str] = set()

        for size, term in iter_ngrams(tokens, sizes):
            counts[term] += 1
            total_ngrams[size] += 1
            local_terms.add(term)

        for term in local_terms:
            documents[term] += 1

        # Save a small number of real contexts for later human review.
        lowered_lines = [(line.lower(), line) for line in prose.splitlines() if line.strip()]
        for term in local_terms:
            if len(examples[term]) >= 3:
                continue
            term_pattern = re.compile(rf"(?<![\w-]){re.escape(term)}(?![\w-])")
            for lowered, original in lowered_lines:
                if term_pattern.search(lowered):
                    example = compact_example(original)
                    if example and example not in examples[term]:
                        examples[term].append(example)
                    break

    return CorpusStats(
        counts=counts,
        documents=documents,
        total_ngrams=total_ngrams,
        examples=dict(examples),
        document_count=document_count,
    )


def load_known_terms(path: Path | None) -> set[str]:
    """Load existing watchlist terms."""

    if path is None:
        return set()

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "term" not in reader.fieldnames:
            raise ValueError(f"{path}: expected a 'term' column")
        return {
            row["term"].strip().lower()
            for row in reader
            if row.get("term", "").strip()
        }


def phrase_size(term: str) -> int:
    """Return the number of space-separated words in a phrase."""

    return term.count(" ") + 1


def rank_candidates(
    model: CorpusStats,
    baseline: CorpusStats,
    *,
    sizes: Sequence[int],
    min_count: int,
    min_docs: int,
    smoothing: float,
    known_terms: set[str],
    novel_only: bool,
) -> list[dict[str, Any]]:
    """Create ranked rows with smoothed frequency comparisons."""

    rows: list[dict[str, Any]] = []

    for term, model_count in model.counts.items():
        if model_count < min_count:
            continue

        model_docs = model.documents[term]
        if model_docs < min_docs:
            continue
        if novel_only and term in known_terms:
            continue

        size = phrase_size(term)
        if size not in sizes:
            continue

        baseline_count = baseline.counts[term]
        model_total = max(model.total_ngrams[size], 1)
        baseline_total = max(baseline.total_ngrams[size], 1)

        # Additive smoothing prevents division by zero while still rewarding
        # phrases that are absent from a sufficiently large baseline.
        model_rate = (model_count + smoothing) / (model_total + smoothing)
        baseline_rate = (baseline_count + smoothing) / (baseline_total + smoothing)
        ratio = model_rate / baseline_rate
        log2_ratio = math.log2(ratio)

        # Favor phrases that are both distinctive and repeated across documents.
        score = (
            max(log2_ratio, 0.0)
            * math.log1p(model_count)
            * math.sqrt(model_docs)
        )

        rows.append(
            {
                "term": term,
                "words": size,
                "model_count": model_count,
                "model_documents": model_docs,
                "model_per_million": round(model_count * 1_000_000 / model_total, 3),
                "baseline_count": baseline_count,
                "baseline_documents": baseline.documents[term],
                "baseline_per_million": round(
                    baseline_count * 1_000_000 / baseline_total, 3
                ),
                "frequency_ratio": round(ratio, 3),
                "log2_ratio": round(log2_ratio, 3),
                "score": round(score, 3),
                "known": "yes" if term in known_terms else "no",
                "examples": " || ".join(model.examples.get(term, [])),
            }
        )

    return sorted(
        rows,
        key=lambda row: (
            -float(row["score"]),
            -int(row["model_documents"]),
            -int(row["model_count"]),
            str(row["term"]),
        ),
    )


def write_rows(rows: Sequence[dict[str, Any]], output: Path | None) -> None:
    """Write candidate rows as CSV."""

    fieldnames = [
        "term",
        "words",
        "model_count",
        "model_documents",
        "model_per_million",
        "baseline_count",
        "baseline_documents",
        "baseline_per_million",
        "frequency_ratio",
        "log2_ratio",
        "score",
        "known",
        "examples",
    ]

    if output is None:
        handle = sys.stdout
        close_after = False
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        handle = output.open("w", newline="", encoding="utf-8")
        close_after = True

    try:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if close_after:
            handle.close()


def main(argv: Sequence[str] | None = None) -> int:
    """Run corpus comparison."""

    args = parse_args(argv or sys.argv[1:])

    try:
        sizes = parse_ngram_sizes(args.ngrams)
        known_terms = load_known_terms(args.known)
        model_paths = list(iter_files(args.model))
        baseline_paths = list(iter_files(args.baseline))

        if not model_paths:
            raise ValueError("model corpus contains no supported text files")
        if not baseline_paths:
            raise ValueError("baseline corpus contains no supported text files")

        model = collect_corpus(model_paths, sizes)
        baseline = collect_corpus(baseline_paths, sizes)
        rows = rank_candidates(
            model,
            baseline,
            sizes=sizes,
            min_count=args.min_count,
            min_docs=args.min_docs,
            smoothing=args.smoothing,
            known_terms=known_terms,
            novel_only=args.novel_only,
        )
        write_rows(rows[: args.top], args.output)
    except (OSError, ValueError) as error:
        print(f"discover_jargon: {error}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
