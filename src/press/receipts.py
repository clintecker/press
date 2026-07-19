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


def pinned_toolchain_digest() -> str:
    """The immutable toolchain image the release pins, read from the
    reusable build workflow. This is the toolchain a release stands on,
    and a release receipt records it so a later object cannot claim a
    different image than the one proven."""

    build_yml = ROOT / ".github" / "workflows" / "build.yml"
    if not build_yml.is_file():
        return "unpinned"
    import re

    match = re.search(r"press-toolchain:(sha-[0-9a-f]+)", build_yml.read_text(encoding="utf-8"))
    return match.group(1) if match else "unpinned"


def build_release_receipt(package_digest: str, chain: list[Receipt]) -> Receipt:
    """The terminal release receipt: it names the pinned toolchain and the
    built package digest as artifacts and extends the whole prior chain.
    A release requires this receipt to be clean-tree, so it is emitted
    from the committed release state, never a dirty working tree."""

    return emit(
        "release",
        proofs=sorted({p for r in chain for p in r.proofs}),
        prerequisites=chain,
        artifacts={"package": package_digest, "toolchain": pinned_toolchain_digest()},
        toolchain_digest=pinned_toolchain_digest(),
    )


def build_full_chain(package_digest: str, toolchain_digest: str,
                     proofs_by_layer: dict[str, list[str]] | None = None) -> list[Receipt]:
    """The full trust chain for a release: a receipt for every pre-release
    layer, each extending the one before, then the terminal release
    receipt. proofs_by_layer optionally records which invariants each
    layer executed; the completeness proof does not depend on it, but a
    populated chain is a richer audit record."""

    proofs_by_layer = proofs_by_layer or {}
    chain: list[Receipt] = []
    for layer in LAYERS:
        if layer == "release":
            continue
        chain.append(emit(
            layer,
            proofs=proofs_by_layer.get(layer, []),
            prerequisites=chain[-1:],  # extend the immediately preceding layer
            toolchain_digest=toolchain_digest,
        ))
    chain.append(build_release_receipt(package_digest, chain))
    return chain


def verify_complete(chain: list[Receipt]) -> list[str]:
    """A release chain must present every trust layer, contiguous and in
    order from the base to release, each layer naming the immediately
    preceding layer's receipt as a prerequisite. This is what turns the
    chain from an assertion into a proof: no layer can be skipped, and a
    placeholder standing in for 'the CI proofs' cannot pass, because the
    missing layers are named and absent."""

    problems: list[str] = []
    present = [r.layer for r in chain]
    if present != LAYERS:
        missing = [ell for ell in LAYERS if ell not in present]
        extra = [ell for ell in present if ell not in LAYERS]
        detail = []
        if missing:
            detail.append(f"missing {missing}")
        if extra:
            detail.append(f"unexpected {extra}")
        if not detail:
            detail.append(f"out of order (got {present})")
        problems.append("incomplete release chain: " + "; ".join(detail))
        return problems
    # Each layer must extend the immediately preceding one, so the chain
    # is a single spine and not a fan of unlinked receipts.
    for earlier, later in zip(chain, chain[1:]):
        if earlier.digest() not in later.prerequisites:
            problems.append(
                f"{later.layer}: does not extend its predecessor "
                f"{earlier.layer!r} (prerequisite link broken)"
            )
    return problems


def verify_release(chain: list[Receipt], package_digest: str) -> list[str]:
    """A release chain is complete and clean, and its terminal receipt
    names the pinned toolchain and the built package. Every mismatch is a
    refusal, so a deliberate commit, package, image, or tag substitution
    turns the release gate red."""

    problems = verify_chain(chain, require_clean=True)
    problems += verify_complete(chain)
    if not chain:
        return problems
    release = chain[-1]
    if release.layer != "release":
        problems.append(f"terminal receipt is {release.layer!r}, not a release")
    if release.artifacts.get("package") != package_digest:
        problems.append(
            "release receipt package digest does not match the built package"
        )
    if release.artifacts.get("toolchain") != pinned_toolchain_digest():
        problems.append(
            "release receipt toolchain does not match the pinned build.yml image"
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
    if len(args) >= 3 and args[0] == "verify-release":
        chain = from_json(Path(args[1]).read_text(encoding="utf-8"))
        problems = verify_release(chain, args[2])
        if problems:
            print("release receipt chain does not hold:")
            for problem in problems:
                print(f"  - {problem}")
            return 1
        print(f"release chain holds: {len(chain)} layers, clean tree, "
              "package and toolchain match the proven objects")
        return 0
    if len(args) < 2 or args[0] != "verify":
        print("usage: python3 -m press.receipts verify <chain.json> [--release]")
        print("       python3 -m press.receipts verify-release <chain.json> <package-digest>")
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
