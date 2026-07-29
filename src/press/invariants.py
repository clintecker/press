"""Adapter onto the one invariant ledger.

Celebrimbor's ledger (``.celebrimbor/invariants.yaml``, validated by
``celebrimbor.invariants`` on every gate) is the single source of record for
what the press promises and where each promise is kept. Referential integrity
-- every enforcer a real callable, every critical invariant a real negative
proof -- is celebrimbor's job now, not a second validator here.

This module exposes only what press-specific consumers need from that one
ledger, so there is no parallel ledger to drift:

  * :func:`load` -- every invariant as an ``id``-keyed dict, for the pytest
    marker plugin (which validates ``@pytest.mark.invariant`` citations and
    reads ``limitations`` for xfail) and any id-set consumer. It parses the
    YAML directly, with no celebrimbor import, because the marker plugin runs
    on every interpreter -- including the 3.10 matrix leg where celebrimbor
    (Python >=3.11) is absent.
  * :func:`render` -- ``docs/INVARIANTS.md``, rendered by celebrimbor's own
    ``render_docs``. This is a dev/CI operation (docs generation and the
    drift check) that runs where celebrimbor is present; it imports it lazily.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import yamlio

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT.parent.parent / ".celebrimbor" / "invariants.yaml"


def _ledger_path() -> Path:
    """The celebrimbor invariant ledger, a repository file (not packaged).
    In a checkout it sits two levels above the source tree; when the code runs
    from an installed wheel that path lands inside site-packages and does not
    exist, so fall back to the ledger relative to the working directory, which
    is the checkout root."""

    if LEDGER.is_file():
        return LEDGER
    cwd_ledger = Path.cwd() / ".celebrimbor" / "invariants.yaml"
    if cwd_ledger.is_file():
        return cwd_ledger
    return LEDGER  # absent either way; let the caller's open() report it


def load(path: Path | None = None) -> list[dict[str, Any]]:
    """Every invariant as a dict carrying at least ``id`` and ``limitations``.

    Reads the ledger YAML directly (no celebrimbor dependency) so the marker
    plugin works on the celebrimbor-free 3.10 leg. celebrimbor's schema is a
    mapping of id -> entry; flatten it to a list with the id folded in."""

    path = path if path is not None else _ledger_path()
    data = yamlio.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("invariants"), dict):
        raise SystemExit(f"{path}: must be a mapping with an 'invariants' mapping")
    entries: list[dict[str, Any]] = []
    for name, entry in data["invariants"].items():
        row = dict(entry) if isinstance(entry, dict) else {}
        row["id"] = name
        row.setdefault("limitations", [])
        entries.append(row)
    return entries


def render() -> str:
    """``docs/INVARIANTS.md``, rendered from the one ledger by celebrimbor.

    Imported lazily: docs generation and the drift check run where celebrimbor
    is installed (the quality tier), never on a bare or 3.10 environment."""

    from celebrimbor.ledgers.invariants import load_invariants, render_docs

    return render_docs(load_invariants(_ledger_path()))


def main() -> int:
    entries = load()
    print(
        f"Invariant ledger holds: {len(entries)} invariants (validated by celebrimbor.invariants)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
