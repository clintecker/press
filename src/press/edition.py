"""Immutable sellable-edition manifests.

An order is trustworthy only if it names the exact release-approved
interior, cover, print specification, and toolchain that will reach the
printer. A path like ``dist/book.pdf`` or a mutable "latest" file cannot
carry that promise. An :class:`EditionManifest` does: it is a canonical,
digest-addressed record of one physical edition, built from the
release-gated artifacts and the accumulated-trust receipts, carrying no
mutable price, secret, or customer data.

Identity is the point. The ``edition_id`` is a sha256 over the
production-affecting facts alone -- the interior and cover bytes, the
print specification, the ISBN, and the toolchain -- so any change that
could alter the physical object mints a new edition. Provenance (the
source commit, the receipt chain) and capability (which providers are
qualified) are recorded but deliberately excluded from identity, because
the plan is explicit that provider availability is not an edition fact:
an edition may be qualified for zero, one, or several providers without
changing what it is.

Determinism is a contract, as it is for receipts: the canonical form
sorts keys and uses no clock or randomness, so the same edition digests
identically across processes and across an installed wheel.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path

SCHEMA_VERSION = 1
MEDIA_TYPE = "application/pdf"

# Fields recorded on the manifest but excluded from the identity digest.
# Provenance (commit, receipts, quality inputs) traces where an edition
# came from; capability (qualifications) says who can print it; a dirty
# tree says it is not sellable. None of these change what the physical
# object is, so none may change the edition_id.
_EXCLUDED_FROM_IDENTITY = frozenset({
    "edition_id", "source_commit", "tree_clean", "input_digests",
    "receipt_digests", "qualifications",
})

# Keys that must never appear anywhere in a manifest: a manifest carries
# identity and print facts, never money, secrets, or a recipient. The
# schema already excludes them; this list turns a future field mistake
# into a caught defect rather than a leak.
_FORBIDDEN_KEYS = frozenset({
    "price", "amount", "cost", "currency", "card", "cvv", "secret",
    "password", "token", "apikey", "api_key", "credential", "email",
    "address", "recipient", "customer", "phone",
})

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ArtifactRef:
    """One immutable file the edition is made of, by content, never path."""

    role: str  # "interior" | "cover"
    sha256: str
    byte_size: int
    media_type: str = MEDIA_TYPE


@dataclass(frozen=True)
class ProviderQualification:
    """Evidence that one provider can print one edition. A capability, not
    an edition fact: it names the edition it was made against so a
    qualification carried over to a different edition reads as stale."""

    provider: str
    product_id: str
    qualified_for: str  # the edition_id this qualification was proven against
    evidence_digest: str


@dataclass(frozen=True)
class EditionManifest:
    schema_version: int
    edition_id: str  # sha256 of the identity fields; verified, never trusted
    slug: str
    title: str
    format: str  # e.g. "paperback"
    isbn: str | None  # validated 13-digit print ISBN, or None when unassigned
    trim_width: float
    trim_height: float
    page_count: int
    paper: str
    spine_width_in: float
    bleed_in: float
    interior: ArtifactRef
    cover: ArtifactRef
    toolchain_digest: str
    source_commit: str
    tree_clean: bool
    input_digests: dict[str, str]
    receipt_digests: tuple[str, ...]
    qualifications: tuple[ProviderQualification, ...] = ()

    def digest(self) -> str:
        """The whole manifest's content hash, provenance included -- the
        value a release receipt records to bind a release to this edition."""

        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Observed:
    """The facts rehashed from the artifacts on disk at verification time,
    the truth a manifest is checked against."""

    interior_sha256: str
    interior_byte_size: int
    interior_pages: int
    cover_sha256: str
    cover_byte_size: int


def _identity_digest(manifest: EditionManifest) -> str:
    """The sha256 of the production-affecting fields alone."""

    data = asdict(manifest)
    for key in _EXCLUDED_FROM_IDENTITY:
        data.pop(key, None)
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _forbidden_keys_present(data: object) -> list[str]:
    """Every forbidden key found anywhere in the nested structure."""

    found: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(key, str) and key.lower() in _FORBIDDEN_KEYS:
                found.append(key)
            found.extend(_forbidden_keys_present(value))
    elif isinstance(data, (list, tuple)):
        for item in data:
            found.extend(_forbidden_keys_present(item))
    return found


# ---- construction (I/O) ----

def _file_facts(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def interior_path(root: Path, slug: str) -> Path:
    return root / "dist" / f"{slug}-interior.pdf"


def cover_path(root: Path, slug: str) -> Path:
    return root / "dist" / f"{slug}-coverwrap.pdf"


def observe(root: Path, slug: str) -> Observed:
    """Rehash the interior and cover artifacts on disk and count the
    interior's pages -- the bytes as they are right now, never cached."""

    from . import gen_coverwrap

    interior = interior_path(root, slug)
    cover = cover_path(root, slug)
    interior_sha, interior_size = _file_facts(interior)
    cover_sha, cover_size = _file_facts(cover)
    pages = gen_coverwrap.interior_page_count(interior)
    return Observed(interior_sha, interior_size, pages, cover_sha, cover_size)


def build(chain, *, root: Path | None = None, book=None,
          fmt: str = "paperback",
          qualifications: tuple[ProviderQualification, ...] = ()) -> EditionManifest:
    """Assemble a manifest from the release-gated artifacts, the book
    facts, and the trust-receipt chain. The chain is the release proof the
    edition stands on; its receipts' digests are recorded as provenance."""

    from . import booklib, gen_coverwrap, receipts, registrations

    if root is None:
        root = booklib.root()
    if book is None:
        book = booklib.book()

    observed = observe(root, book.slug)
    inputs, commit, clean = receipts.current_inputs(
        receipts.pinned_toolchain_digest())

    manifest = EditionManifest(
        schema_version=SCHEMA_VERSION,
        edition_id="",  # filled below from the identity digest
        slug=book.slug,
        title=book.title,
        format=fmt,
        isbn=registrations.isbn("print"),
        trim_width=book.trim_width,
        trim_height=book.trim_height,
        page_count=observed.interior_pages,
        paper=str((book.print_config or {}).get("paper", "cream")),
        spine_width_in=round(gen_coverwrap.spine_width(observed.interior_pages), 6),
        bleed_in=gen_coverwrap.BLEED_IN,
        interior=ArtifactRef("interior", observed.interior_sha256,
                             observed.interior_byte_size),
        cover=ArtifactRef("cover", observed.cover_sha256, observed.cover_byte_size),
        toolchain_digest=receipts.pinned_toolchain_digest(),
        source_commit=commit,
        tree_clean=clean,
        input_digests=dict(sorted(inputs.items())),
        receipt_digests=tuple(r.digest() for r in chain),
        qualifications=tuple(qualifications),
    )
    return replace(manifest, edition_id=_identity_digest(manifest))


# ---- verification ----

def _check_identity(manifest: EditionManifest) -> list[str]:
    problems: list[str] = []
    if manifest.schema_version != SCHEMA_VERSION:
        problems.append(
            f"unknown schema version {manifest.schema_version} "
            f"(this press writes {SCHEMA_VERSION})")
    # The stored edition_id must be the digest of the identity fields, so
    # a hand-edited fact cannot keep a trusted id.
    recomputed = _identity_digest(manifest)
    if manifest.edition_id != recomputed:
        problems.append(
            "edition_id does not match the identity digest "
            f"({manifest.edition_id[:12]} != {recomputed[:12]}); a "
            "production-affecting fact was changed without re-deriving identity")
    return problems


def _check_bytes(manifest: EditionManifest, observed: Observed) -> list[str]:
    # Rehash before fulfillment; a rebuild after payment is forbidden, so
    # the recorded digests must match the artifacts now.
    problems: list[str] = []
    if manifest.interior.sha256 != observed.interior_sha256:
        problems.append("interior digest does not match the artifact on disk")
    if manifest.interior.byte_size != observed.interior_byte_size:
        problems.append("interior byte size does not match the artifact on disk")
    if manifest.cover.sha256 != observed.cover_sha256:
        problems.append("cover digest does not match the artifact on disk")
    if manifest.cover.byte_size != observed.cover_byte_size:
        problems.append("cover byte size does not match the artifact on disk")
    if manifest.page_count != observed.interior_pages:
        problems.append(
            f"page count {manifest.page_count} does not match the interior "
            f"({observed.interior_pages} pages)")
    return problems


def _check_references(manifest: EditionManifest) -> list[str]:
    # Well-formed, immutable references only: content digests, never a path
    # or a "latest" pointer that could resolve to different bytes later.
    problems: list[str] = []
    for ref in (manifest.interior, manifest.cover):
        if not _SHA256.match(ref.sha256):
            problems.append(f"{ref.role} digest is not a sha256")
        if ref.media_type != MEDIA_TYPE:
            problems.append(f"{ref.role} media type {ref.media_type!r} is not {MEDIA_TYPE}")
    for label, value in (("interior", manifest.interior.sha256),
                         ("cover", manifest.cover.sha256),
                         ("toolchain", manifest.toolchain_digest)):
        if "/" in value or "latest" in value.lower() or ".pdf" in value.lower():
            problems.append(f"{label} reference {value!r} looks like a mutable path")
    return problems


def _check_sellable(manifest: EditionManifest) -> list[str]:
    problems: list[str] = []
    forbidden = _forbidden_keys_present(asdict(manifest))
    if forbidden:
        problems.append(
            f"manifest carries forbidden field(s) {sorted(set(forbidden))}; "
            "an edition manifest holds no price, secret, or customer data")
    # Only a release-gated edition may be sold: it needs a receipt chain
    # and a clean-tree build.
    if not manifest.receipt_digests:
        problems.append("no trust-receipt chain: the edition is not release-gated")
    if not manifest.tree_clean:
        problems.append(
            "built from a dirty tree; a sellable edition is cut from a clean "
            "release state (this is a local-development manifest)")
    return problems


def _check_qualifications(manifest: EditionManifest) -> list[str]:
    # A qualification proven against a different edition is stale and must
    # not be honored for this one.
    problems: list[str] = []
    for qual in manifest.qualifications:
        if qual.qualified_for != manifest.edition_id:
            problems.append(
                f"provider {qual.provider!r} qualification is stale: proven "
                f"against {qual.qualified_for[:12]}, not this edition "
                f"{manifest.edition_id[:12]}")
        if not _SHA256.match(qual.evidence_digest):
            problems.append(
                f"provider {qual.provider!r} qualification evidence is not a sha256")
    return problems


def verify_facts(manifest: EditionManifest, observed: Observed) -> list[str]:
    """Every defect in a manifest checked against the observed artifacts:
    a forged identity, a byte or page-fact mismatch, a mutable or
    ill-formed reference, a forbidden field, a manifest not backed by a
    receipt chain, and a stale provider qualification. Pure, so it is
    property-testable without touching disk."""

    return (_check_identity(manifest)
            + _check_bytes(manifest, observed)
            + _check_references(manifest)
            + _check_sellable(manifest)
            + _check_qualifications(manifest))


def verify(manifest: EditionManifest, root: Path) -> list[str]:
    """Verify a manifest against the artifacts under ``root/dist``."""

    try:
        observed = observe(root, manifest.slug)
    except FileNotFoundError as exc:
        return [f"artifact missing, cannot verify: {exc}"]
    return verify_facts(manifest, observed)


def is_sellable(manifest: EditionManifest, observed: Observed) -> bool:
    """A shorthand: the edition is sellable exactly when nothing is wrong."""

    return not verify_facts(manifest, observed)


# ---- serialization ----

def to_json(manifest: EditionManifest) -> str:
    return json.dumps(asdict(manifest), indent=2, sort_keys=True)


def from_json(text: str) -> EditionManifest:
    data = json.loads(text)
    data["interior"] = ArtifactRef(**data["interior"])
    data["cover"] = ArtifactRef(**data["cover"])
    data["receipt_digests"] = tuple(data.get("receipt_digests", ()))
    data["qualifications"] = tuple(
        ProviderQualification(**q) for q in data.get("qualifications", ()))
    return EditionManifest(**data)


def main(argv: list[str] | None = None) -> int:
    """Independently verify an edition manifest from a JSON file:

        python3 -m press.edition verify <manifest.json> [<book-root>]

    A manifest is data anyone can re-check against the artifacts it names.
    Refusals are locatable and exit non-zero.
    """

    import sys

    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) < 2 or args[0] != "verify":
        print("usage: python3 -m press.edition verify <manifest.json> [<book-root>]")
        return 2
    manifest = from_json(Path(args[1]).read_text(encoding="utf-8"))
    root = Path(args[2]) if len(args) >= 3 else Path.cwd()
    problems = verify(manifest, root)
    if problems:
        print("edition manifest does not hold:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"edition manifest holds: {manifest.slug} {manifest.format}, "
          f"{manifest.page_count} pages, identity {manifest.edition_id[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
