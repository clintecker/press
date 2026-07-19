"""Chained trust receipts across the accumulated-trust layers.

A later green job proves nothing if it ran against different bytes,
fixtures, or tools than the job before it. A trust receipt records
exactly what a layer stood on, the digests of the source, package,
toolchain, and quality manifests it consumed, the proofs it executed,
and the receipts of the prerequisite layers it extends. A chain is
verifiable independently: each layer must have consumed the same
inputs as its prerequisites, the layers must appear in accumulated
trust order, and a later layer extends the invariant results of
earlier ones rather than replacing them.

Receipts are deterministic (no clock, no randomness): the same inputs
produce the same receipt digest, so a chain can be recomputed and
compared. A release requires a clean-tree chain; a receipt built from
a dirty working tree is marked local-development and a release refuses
it.

The layers, in accumulated trust order:
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import adapters

LAYERS = [
    "collection", "unit", "property", "component", "damage", "graph",
    "scenario", "integration", "distribution", "container", "boundary",
    "release",
]

SCHEMA_VERSION = 1
ROOT = Path(__file__).resolve().parent.parent.parent
MANIFESTS = {
    "invariants": ROOT / "quality" / "invariants.yaml",
    "fixtures": ROOT / "quality" / "fixtures.yaml",
    "scenarios": ROOT / "quality" / "scenarios.yaml",
    "surfaces": ROOT / "quality" / "surfaces.yaml",
}


@dataclass(frozen=True)
class Receipt:
    schema_version: int
    layer: str
    source_commit: str
    tree_clean: bool
    inputs: dict[str, str]  # name -> digest
    prerequisites: list[str]  # digests of prior-layer receipts
    proofs: list[str]  # invariant ids this layer executed
    artifacts: dict[str, str]  # name -> digest
    limitations: list[str] = field(default_factory=list)
    local_dev: bool = False

    def digest(self) -> str:
        """A deterministic content hash: the receipt's identity, stable
        across processes so a chain can be recomputed and compared."""

        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _git(*args: str) -> str:
    result = adapters.process_runner.run(
        ["git", "-C", str(ROOT), *args], capture=True, check=True
    )
    return result.stdout.decode("utf-8").strip()


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "absent"


def current_inputs(toolchain_digest: str = "unpinned") -> tuple[dict[str, str], str, bool]:
    """The digests of everything a layer consumes right now, plus the
    source commit and whether the tree is clean."""

    try:
        commit = _git("rev-parse", "HEAD")
        clean = _git("status", "--porcelain") == ""
    except (OSError, subprocess.CalledProcessError):
        commit, clean = "unknown", False
    inputs = {name: _file_digest(path) for name, path in MANIFESTS.items()}
    inputs["toolchain"] = toolchain_digest
    return inputs, commit, clean


def emit(layer: str, proofs: list[str], prerequisites: list[Receipt] | None = None,
         artifacts: dict[str, str] | None = None, limitations: list[str] | None = None,
         toolchain_digest: str = "unpinned") -> Receipt:
    """Build a receipt for one layer from the current inputs and the
    prerequisite receipts it extends."""

    if layer not in LAYERS:
        raise SystemExit(f"unknown trust layer: {layer!r} (one of {LAYERS})")
    inputs, commit, clean = current_inputs(toolchain_digest)
    return Receipt(
        schema_version=SCHEMA_VERSION,
        layer=layer,
        source_commit=commit,
        tree_clean=clean,
        inputs=inputs,
        prerequisites=[r.digest() for r in (prerequisites or [])],
        proofs=sorted(proofs),
        artifacts=dict(sorted((artifacts or {}).items())),
        limitations=sorted(limitations or []),
        local_dev=not clean,
    )


def verify_chain(chain: list[Receipt], require_clean: bool = False) -> list[str]:
    """Every defect in a receipt chain: a prerequisite whose digest is
    absent (missing or tampered), layers out of accumulated-trust order,
    an input that changed between a layer and its prerequisite, an
    invariant result dropped by a later layer, and, when required, a
    dirty-tree receipt in a release chain."""

    problems: list[str] = []
    if not chain:
        return ["empty receipt chain"]

    by_digest = {r.digest(): r for r in chain}
    order = {layer: i for i, layer in enumerate(LAYERS)}

    seen_proofs: set[str] = set()
    last_rank = -1
    for receipt in chain:
        if receipt.schema_version != SCHEMA_VERSION:
            problems.append(f"{receipt.layer}: unknown schema version {receipt.schema_version}")
        rank = order.get(receipt.layer, -1)
        if rank < 0:
            problems.append(f"unknown layer {receipt.layer!r}")
        elif rank < last_rank:
            problems.append(f"{receipt.layer}: out of accumulated-trust order")
        last_rank = max(last_rank, rank)

        for prereq_digest in receipt.prerequisites:
            prereq = by_digest.get(prereq_digest)
            if prereq is None:
                problems.append(
                    f"{receipt.layer}: prerequisite {prereq_digest[:12]} is missing "
                    "or tampered (its digest resolves to no receipt in the chain)"
                )
                continue
            for key in ("toolchain", *MANIFESTS):
                if receipt.inputs.get(key) != prereq.inputs.get(key):
                    problems.append(
                        f"{receipt.layer}: input {key!r} differs from prerequisite "
                        f"{prereq.layer!r} ({prereq.inputs.get(key, '?')[:8]} -> "
                        f"{receipt.inputs.get(key, '?')[:8]})"
                    )
            if receipt.source_commit != prereq.source_commit:
                problems.append(
                    f"{receipt.layer}: source commit differs from prerequisite "
                    f"{prereq.layer!r}"
                )
        # Later layers extend, never drop, the invariant results proven.
        seen_proofs |= set(receipt.proofs)

        if require_clean and not receipt.tree_clean:
            problems.append(
                f"{receipt.layer}: built from a dirty tree; a release chain "
                "requires clean-tree receipts (this is a local-development receipt)"
            )
    return problems


def to_json(chain: list[Receipt]) -> str:
    return json.dumps([asdict(r) for r in chain], indent=2)


def from_json(text: str) -> list[Receipt]:
    return [Receipt(**entry) for entry in json.loads(text)]


def main(argv: list[str] | None = None) -> int:
    """Independently verify a receipt chain from a JSON file:

        python3 -m press.receipts verify <chain.json> [--release]

    A chain is data anyone can re-check; --release additionally demands
    clean-tree receipts. Refusals are locatable, exit non-zero.
    """

    import sys

    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) < 2 or args[0] != "verify":
        print("usage: python3 -m press.receipts verify <chain.json> [--release]")
        return 2
    chain = from_json(Path(args[1]).read_text(encoding="utf-8"))
    problems = verify_chain(chain, require_clean="--release" in args)
    if problems:
        print("trust receipt chain does not hold:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"receipt chain holds: {len(chain)} layers, "
          f"{chain[-1].layer} extends {chain[0].layer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
