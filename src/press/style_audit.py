"""Editorial checks that are mechanical enough to automate.

This is intentionally a lint pass, not an editor. It catches a small set of
patterns that repeatedly make technical prose vague or synthetic. It cannot
prove truth, voice, or good judgment.

Universal rules live here. Per-book bans (project names, apparatus words,
vocabulary the author has outlawed) come from the book's
config/house-rules.yaml under banned-patterns.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from . import booklib

CURLY_QUOTES = {
    "‘": "curly single quote",
    "’": "curly apostrophe",
    "“": "curly double quote",
    "”": "curly double quote",
}

# Codepoints the print fonts are known to carry. Anything else silently
# vanishes from the PDF, so anything else is an error in book prose.
ALLOWED_CHARS = re.compile(r"[^\t\n\r\x20-\x7eÀ-ſ]")

FORBIDDEN_CHARS = {
    "—": "em dash",
    "–": "en dash",
}

FORBIDDEN_PATTERNS = {
    r"\bin conclusion\b": "generic conclusion",
    r"\bit is important to note\b": "throat-clearing phrase",
    r"\bit is worth noting\b": "throat-clearing phrase",
    r"\bat its core\b": "fake-revelation phrase",
    r"\bthe real question is\b": "fake-revelation phrase",
    r"\blet(?:'|’)s (?:dive|delve|explore|break this down)\b": "chatbot signposting",
    r"\bwithout further ado\b": "chatbot signposting",
    r"\bstands as a testament\b": "inflated significance",
    r"\bvibrant tapestry\b": "inflated AI phrase",
    r"\bnot only\b.{0,120}\bbut also\b": "formulaic negative parallelism",
}

TITLE_SMALL_WORDS = {
    "a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into",
    "nor", "of", "on", "or", "over", "the", "to", "up", "with", "without",
}


def banned_book_patterns() -> dict[re.Pattern, str]:
    """The book's banned patterns, compiled once; a malformed regex is
    a config mistake and gets a refusal naming the file and pattern,
    not a traceback out of the re parser mid-audit."""

    compiled = {}
    for pattern, label in dict(
        booklib.house_rules().get("banned-patterns") or {}
    ).items():
        try:
            compiled[re.compile(pattern)] = label
        except re.error as exc:
            raise SystemExit(
                "config/house-rules.yaml: banned pattern "
                f"{pattern!r} is not a valid regex ({exc})"
            ) from exc
    return compiled


def audit_dirs() -> list[Path]:
    root = booklib.root()
    extra = booklib.house_rules().get("audit-dirs") or []
    return [root / "book"] + [root / name for name in extra]


def markdown_files(explicit: list[str]) -> list[Path]:
    if explicit:
        # Explicit paths are fixtures or drafts judged as manuscript prose.
        return [Path(arg).resolve() for arg in explicit]
    files: list[Path] = []
    for directory in audit_dirs():
        if directory.exists():
            files.extend(sorted(directory.rglob("*.md")))
    return files


def in_fenced_code(lines: list[str]) -> list[bool]:
    flags: list[bool] = []
    active = False
    marker = ""
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            candidate = stripped[:3]
            if not active:
                active = True
                marker = candidate
            elif candidate == marker:
                active = False
                marker = ""
            flags.append(True)
            continue
        flags.append(active)
    return flags


def looks_title_cased(heading: str) -> bool:
    words = re.findall(r"[A-Za-z][A-Za-z0-9'-]*", heading)
    candidates = [w for w in words[1:] if w.lower() not in TITLE_SMALL_WORDS and not w.isupper()]
    if len(candidates) < 3:
        return False
    capitalized = sum(1 for w in candidates if w[:1].isupper())
    return capitalized / len(candidates) >= 0.8


def check_forbidden(line: str, where: str, errors: list[str]) -> None:
    """The universal battery: characters and phrases banned in all prose."""

    for char, name in FORBIDDEN_CHARS.items():
        if char in line:
            errors.append(f"{where}: contains {name}")
    for pattern, label in FORBIDDEN_PATTERNS.items():
        if re.search(pattern, line, flags=re.IGNORECASE):
            errors.append(f"{where}: {label}")


def check_book_prose(
    line: str, where: str, banned: dict[re.Pattern, str], errors: list[str]
) -> None:
    """Checks that apply only to manuscript prose: typography glyphs,
    print-font coverage, and the book's own banned patterns."""

    for char, name in CURLY_QUOTES.items():
        if char in line:
            errors.append(f"{where}: contains {name}")
    stray = ALLOWED_CHARS.search(line)
    if stray:
        errors.append(
            f"{where}: glyph U+{ord(stray.group(0)):04X} "
            "is outside the print-font set"
        )
    for compiled, label in banned.items():
        if compiled.search(line):
            errors.append(f"{where}: {label}")


def check_heading(
    line: str, where: str, in_book: bool, errors: list[str], warnings: list[str]
) -> None:
    heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
    if heading is None:
        return
    if in_book and re.match(r"^\d", heading.group(1)):
        errors.append(f"{where}: manual number in heading")
    if looks_title_cased(heading.group(1)):
        target = errors if in_book else warnings
        target.append(f"{where}: title-case heading: {heading.group(1)}")


def check_paragraph_length(
    text: str, relative: Path, in_book: bool, errors: list[str], warnings: list[str]
) -> None:
    # Dense chapters are difficult to read in a narrow trim.
    paragraphs = re.split(r"\n\s*\n", text)
    for index, paragraph in enumerate(paragraphs, start=1):
        if paragraph.lstrip().startswith(("#", "```", "~~~", "|", "- [", ">")):
            continue
        words = re.findall(r"\b\w+[\w'-]*\b", paragraph)
        if len(words) > 190:
            # The editorial law says paragraphs stay under 190 words;
            # a law downgraded to a warning is guidance wearing a
            # uniform. Book prose enforces it; press-side docs only
            # hear about it.
            target = errors if in_book else warnings
            target.append(
                f"{relative}: paragraph {index} has {len(words)} words "
                "(the law is under 190; split it)"
            )


def report(explicit: list[str], errors: list[str], warnings: list[str]) -> int:
    if warnings:
        print("Editorial warnings:")
        for warning in warnings:
            print(f"  - {warning}")

    if errors:
        print("Editorial checks failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Editorial checks passed: {len(markdown_files(explicit))} Markdown files")
    return 0


def main(argv: list[str] | None = None) -> int:
    explicit = list(argv if argv is not None else sys.argv[1:])
    explicit_mode = bool(explicit)
    root = booklib.root()
    book_dir = root / "book"
    banned = banned_book_patterns()

    errors: list[str] = []
    warnings: list[str] = []

    for path in markdown_files(explicit):
        try:
            relative = path.relative_to(root)
        except ValueError:
            relative = path
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        code_flags = in_fenced_code(lines)
        in_book = explicit_mode or book_dir in path.parents

        for number, (line, in_code) in enumerate(zip(lines, code_flags), start=1):
            where = f"{relative}:{number}"
            if line.rstrip() != line:
                errors.append(f"{where}: trailing whitespace")
            if in_code:
                continue
            check_forbidden(line, where, errors)
            if in_book:
                check_book_prose(line, where, banned, errors)
            check_heading(line, where, in_book, errors, warnings)

        check_paragraph_length(text, relative, in_book, errors, warnings)

    return report(explicit, errors, warnings)


if __name__ == "__main__":
    raise SystemExit(main())
