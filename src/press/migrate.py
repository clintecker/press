"""Migrate a book from one press major to the next, and roll it back.

A book pins the press in exactly two places: ``requirements.txt`` (the
``git+https`` install line, for local builds) and its CI workflow (the
``uses: clintecker/press/.github/workflows/build.yml@vN`` line). Migration
is repinning those sites and nothing else. It never touches the manuscript,
the config, or the accepted art -- the three things a book owns -- so a
migration cannot change what the book *says*, only which pipeline builds it.

The v1-to-v2 migration is deliberately quiet: a v1 book that repins to v2 and
keeps the house design profile renders byte-for-byte as it did, because the
house profile reproduces the sealed v1 geometry exactly. The design changes
only when the author *selects* a non-house profile, which is a separate,
explicit act. So migration's job is to prove that quietness: show every
change before making it, make only the pin change, and keep an exact backup
so the whole thing reverses.

The contract this enforces is ``docs/MIGRATION.md``; the guarantees are
``INV-migration-safe`` (only the pin moves; rollback restores exact bytes)
and ``INV-migration-preview`` (a dry run reports every change before any
mutation).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import version

# The press pin, in either book site: the bare install target
# ``clintecker/press@vN`` and the workflow ref
# ``clintecker/press/.github/workflows/build.yml@vN``. The optional
# three-part suffix is captured so an immutable pin (``@v1.20.0``) is
# recognized and, on migration, floated to the new major (``@v2``).
_PIN = re.compile(r"(clintecker/press(?:/[\w./-]*?)?@v)(\d+)(\.\d+\.\d+)?")

# Where the pin may legitimately live. A match anywhere else (a manuscript
# file that happens to quote the pin, say) is refused rather than rewritten,
# so migration can never edit prose.
_PIN_FILES = ("requirements.txt",)
_WORKFLOW_DIRS = (".github/workflows",)

# Files a book may supply that the design profile does not govern; migration
# preserves them untouched and names each so the author re-checks it against
# the major they are moving to.
_OVERRIDES = {
    "tex/title-page.tex": "overrides the generated front matter entirely; "
                          "verify it against your trim before shipping",
    "assets/web/reader.css": "replaces the house reader stylesheet outright",
    "assets/web/extra.css": "appends after the house stylesheet and wins the cascade",
    "config/aesthetic.yaml": "the book's visual identity, applied by every art commission",
}

STATE_DIR = ".press"
BACKUP = "migration-backup.json"
RECEIPT = "migration-receipt.json"


@dataclass(frozen=True)
class PinSite:
    """One place the press major is pinned."""

    path: str          # book-relative
    major: int
    text: str          # the exact matched pin, e.g. "clintecker/press@v1"


@dataclass(frozen=True)
class Diagnosis:
    """What a book is pinned to and what a migration would need to weigh."""

    sites: tuple[PinSite, ...]
    overrides: tuple[tuple[str, str], ...] = ()
    problems: tuple[str, ...] = ()

    @property
    def from_major(self) -> int | None:
        majors = {site.major for site in self.sites}
        if len(majors) == 1:
            return next(iter(majors))
        return None


@dataclass(frozen=True)
class Change:
    path: str
    old: str
    new: str


@dataclass(frozen=True)
class MigrationPlan:
    """Every change ``apply`` would make, and every consequence to weigh,
    computed without touching a byte."""

    from_major: int
    to_major: int
    changes: tuple[Change, ...]
    notes: tuple[str, ...] = field(default_factory=tuple)


def _workflow_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for directory in _WORKFLOW_DIRS:
        wf = root / directory
        if wf.is_dir():
            files.extend(sorted(wf.glob("*.yml")))
            files.extend(sorted(wf.glob("*.yaml")))
    return files


def _scan_file(root: Path, path: Path) -> list[PinSite]:
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(root).as_posix()
    sites = []
    for match in _PIN.finditer(text):
        sites.append(PinSite(path=rel, major=int(match.group(2)), text=match.group(0)))
    return sites


def pin_sites(root: Path) -> list[PinSite]:
    """Every place the press major is pinned in the book, in a stable order:
    ``requirements.txt`` then each CI workflow."""

    found: list[PinSite] = []
    for name in _PIN_FILES:
        path = root / name
        if path.is_file():
            found.extend(_scan_file(root, path))
    for path in _workflow_files(root):
        found.extend(_scan_file(root, path))
    return found


def diagnose(root: Path) -> Diagnosis:
    """Read the book's current pin and the overrides a migration must carry,
    reporting -- never mutating."""

    sites = tuple(pin_sites(root))
    problems: list[str] = []
    if not sites:
        problems.append(
            "no press pin found in requirements.txt or .github/workflows; "
            "is this a book repository?"
        )
    else:
        majors = {site.major for site in sites}
        if len(majors) > 1:
            listed = ", ".join(f"{s.path} -> v{s.major}" for s in sites)
            problems.append(
                f"the book is pinned to more than one major ({listed}); "
                "reconcile them before migrating"
            )
    overrides = tuple(
        (rel, note) for rel, note in _OVERRIDES.items() if (root / rel).is_file()
    )
    return Diagnosis(sites=sites, overrides=overrides, problems=tuple(problems))


def plan(root: Path, to_major: int) -> MigrationPlan:
    """The exact repin ``apply`` would perform, plus every consequence to
    weigh, computed from a dry read. Raises only when the book cannot be
    migrated at all (no pin, or a split pin)."""

    diagnosis = diagnose(root)
    if diagnosis.problems:
        raise SystemExit("cannot migrate:\n" + "\n".join(
            f"  - {p}" for p in diagnosis.problems))
    from_major = diagnosis.from_major
    assert from_major is not None  # guaranteed by the empty-problems check
    if to_major == from_major:
        raise SystemExit(f"already at v{from_major}; nothing to migrate")

    changes = tuple(
        Change(
            path=site.path,
            old=site.text,
            new=_PIN.sub(lambda m: f"{m.group(1)}{to_major}", site.text),
        )
        for site in diagnosis.sites
    )
    notes = [
        f"design is unchanged: with the house profile, v{to_major} reproduces "
        f"the v{from_major} geometry byte-for-byte. Selecting a non-house "
        "print.profile is a separate, explicit choice.",
        "the manuscript, config, and accepted art are not touched.",
    ]
    for rel, note in diagnosis.overrides:
        notes.append(f"custom override {rel} is preserved as-is: {note}.")
    return MigrationPlan(
        from_major=from_major, to_major=to_major, changes=changes, notes=tuple(notes)
    )


def _state_dir(root: Path) -> Path:
    return root / STATE_DIR


def apply(root: Path, to_major: int) -> Path:
    """Repin the book to ``to_major`` after writing an exact backup, and
    return the receipt path. The only files written are the pin sites and
    the state directory; a matched pin outside a legitimate pin file is
    refused rather than rewritten, so migration can never edit prose."""

    migration = plan(root, to_major)
    touched = sorted({change.path for change in migration.changes})

    # Defensive: every file we are about to edit must be a known pin site.
    for rel in touched:
        legitimate = rel in _PIN_FILES or any(
            rel.startswith(f"{d}/") for d in _WORKFLOW_DIRS
        )
        if not legitimate:
            raise SystemExit(
                f"refusing to edit {rel}: a press pin outside requirements.txt "
                "or a CI workflow is not a migration site"
            )

    state = _state_dir(root)
    state.mkdir(exist_ok=True)
    backup = {
        "from_major": migration.from_major,
        "to_major": migration.to_major,
        "files": {rel: (root / rel).read_text(encoding="utf-8") for rel in touched},
    }
    (state / BACKUP).write_text(json.dumps(backup, indent=2), encoding="utf-8")

    for rel in touched:
        path = root / rel
        text = path.read_text(encoding="utf-8")
        rewritten = _PIN.sub(
            lambda m: f"{m.group(1)}{to_major}" if int(m.group(2)) == migration.from_major
            else m.group(0),
            text,
        )
        path.write_text(rewritten, encoding="utf-8")

    receipt = {
        "from_major": migration.from_major,
        "to_major": migration.to_major,
        "press_version": str(version()),
        "sites": touched,
    }
    receipt_path = state / RECEIPT
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt_path


def rollback(root: Path) -> list[str]:
    """Restore the exact pre-migration bytes of every file the last migration
    touched, then clear the migration state. Returns the restored paths."""

    backup_path = _state_dir(root) / BACKUP
    if not backup_path.is_file():
        raise SystemExit("no migration to roll back (no .press/migration-backup.json)")
    backup = json.loads(backup_path.read_text(encoding="utf-8"))
    restored = []
    for rel, original in backup["files"].items():
        (root / rel).write_text(original, encoding="utf-8")
        restored.append(rel)
    backup_path.unlink()
    receipt = _state_dir(root) / RECEIPT
    if receipt.is_file():
        receipt.unlink()
    return sorted(restored)


def status(root: Path) -> str:
    """A human summary of the book's pin and any recorded migration."""

    diagnosis = diagnose(root)
    if diagnosis.problems:
        return "\n".join(diagnosis.problems)
    lines = [f"pinned to v{diagnosis.from_major}:"]
    for site in diagnosis.sites:
        lines.append(f"  {site.path}: {site.text}")
    receipt = _state_dir(root) / RECEIPT
    if receipt.is_file():
        data = json.loads(receipt.read_text(encoding="utf-8"))
        lines.append(
            f"migrated v{data['from_major']} -> v{data['to_major']} "
            f"(press {data['press_version']}); `press migrate rollback` reverses it"
        )
    return "\n".join(lines)


def render_plan(migration: MigrationPlan) -> str:
    """The dry-run report: every change, then every consequence."""

    lines = [f"migrate v{migration.from_major} -> v{migration.to_major}", "", "changes:"]
    for change in migration.changes:
        lines.append(f"  {change.path}: {change.old}  ->  {change.new}")
    lines.append("")
    lines.append("before you apply:")
    for note in migration.notes:
        lines.append(f"  - {note}")
    lines.append("")
    lines.append("nothing is written until you run `press migrate apply`.")
    return "\n".join(lines)
