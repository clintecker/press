"""Fast source checks before invoking Pandoc or TeX."""

from __future__ import annotations

import re
from pathlib import Path

from . import booklib

FORBIDDEN = ["TODO: write", "TBD: write", "lorem ipsum"]


def _content_failures(root: Path, path: Path) -> list[str]:
    """Everything wrong inside one source file that exists."""

    failures: list[str] = []
    text = path.read_text(encoding="utf-8")
    if len(text.strip()) < 80:
        failures.append(f"suspiciously short source: {path.relative_to(root)}")
    if not re.search(r"^#\s+\S", text, flags=re.MULTILINE):
        failures.append(f"no level-1 heading: {path.relative_to(root)}")
    lowered = text.lower()
    for phrase in FORBIDDEN:
        if phrase in lowered:
            failures.append(f"unfinished marker '{phrase}': {path.relative_to(root)}")
    return failures


def _source_failures(root: Path) -> tuple[list[str], set[Path]]:
    """Walk the ordered chapter list once; return failures and the set seen."""

    failures: list[str] = []
    seen: set[Path] = set()
    for path in booklib.chapter_files():
        if path in seen:
            failures.append(f"duplicate source file: {path.relative_to(root)}")
        seen.add(path)
        if not path.is_file():
            failures.append(f"missing source file: {path.relative_to(root)}")
            continue
        failures.extend(_content_failures(root, path))
    return failures, seen


def _metadata_failures() -> list[str]:
    metadata = booklib.metadata()
    return [
        f"metadata missing {required}:"
        for required in ["title", "author", "description", "slug"]
        if not metadata.get(required)
    ]


def _sentinel_failures(seen: set[Path]) -> list[str]:
    # A sentinel that never appears in the source proves nothing in the
    # artifacts; catch the typo here, not after six builds.
    manuscript_text = " ".join(
        " ".join(path.read_text(encoding="utf-8").split())
        for path in seen if path.is_file()
    )
    return [
        f"sentinel not found in the manuscript: {sentinel}"
        for sentinel in booklib.sentinels()
        if " ".join(sentinel.split()) not in manuscript_text
    ]


def _config_shape_failures(root: Path) -> list[str]:
    """Prove the shape of every optional, build-consumed config file before
    Pandoc or TeX runs. A file the typed model accepts but the renderer
    dereferences (the index terms, the authorities ledger, the front matter,
    the house rules) must fail here with a located diagnostic, not deep in a
    generator with a bare TypeError."""

    from . import config_schema, config_store

    failures: list[str] = []
    for file in config_schema.CHECKED_SHAPES:
        path = root / file
        if not path.is_file():
            continue
        try:
            proposed = config_store.load(path)
        except config_store.ConfigError as exc:
            failures.append(str(exc))
            continue
        failures.extend(
            f"{file}: {problem}"
            for problem in config_schema.validate_file(root, file, proposed)
        )
    return failures


def _plate_failures(root: Path, seen: set[Path]) -> list[str]:
    # A plate on disk that no manuscript file references ships in every
    # archive and the site while appearing in no book; orphans are
    # mistakes. The match is path-anchored so raven.jpg cannot hide
    # behind a reference to black-raven.jpg.
    manuscript = "\n".join(
        path.read_text(encoding="utf-8") for path in seen if path.is_file()
    )
    return [
        f"plate never referenced by the manuscript: assets/woodcuts/{plate.name}"
        for plate in booklib.plate_files(root / "assets" / "woodcuts")
        if f"woodcuts/{plate.name}" not in manuscript
    ]


def _figure_failures(root: Path, seen: set[Path]) -> list[str]:
    """Refuse a malformed figure-placement vocabulary before pandoc or TeX
    runs (#225 kin). The grammar is relative and parity-aware by law -- an
    absolute width, a left/right side, an out-of-vocabulary place, a non-em
    outset, a measure on a plate, or a decorative image that still carries alt
    text is a mistake located here, not a silent mis-typeset later."""

    from . import figures

    problems: list[str] = []
    for path in sorted(seen):
        if not path.is_file():
            continue
        figs = figures.parse(path.read_text(encoding="utf-8"))
        rel = path.relative_to(root)
        problems.extend(f"{rel}: {problem}" for problem in figures.validate(figs))
    return problems


def _print_format_failures() -> list[str]:
    """Refuse a trim + ink + provider combination the chosen printer will not
    make, at ``press check`` time rather than deep in the cover renderer
    (#222). The trim and ink come from the selected design profile, the
    binding from ``print.binding``; the page-count bounds are left to the
    build, where the real page count is known. The house provider declares no
    catalog and passes everything, so a book that names no provider is
    unaffected. An unknown or invalid profile or provider id is reported with a
    fuller message by the config checks, so it is not double-reported here."""

    from . import profiles, provider_specs

    print_cfg = booklib.metadata().get("print") or {}
    binding = print_cfg.get("binding", "perfect-bound")
    try:
        profile = profiles.active()
        spec = provider_specs.active()
        trim_w, trim_h = profile.trim
        ink = profile.ink
    except SystemExit:
        return []
    return spec.check_selection(trim_w, trim_h, binding, ink=ink)


def main() -> int:
    root = booklib.root()
    failures, seen = _source_failures(root)
    failures.extend(_metadata_failures())

    from . import commerce, registrations

    failures.extend(registrations.failures())
    failures.extend(commerce.failures())
    failures.extend(_sentinel_failures(seen))
    failures.extend(_plate_failures(root, seen))
    failures.extend(_figure_failures(root, seen))
    failures.extend(_config_shape_failures(root))
    failures.extend(_print_format_failures())

    if failures:
        print("Source checks failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"Source checks passed: {len(seen)} ordered Markdown files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
