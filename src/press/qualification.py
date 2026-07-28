"""Print-provider qualification: the record, and the gate.

Vendor marketing and a published API do not prove a provider can produce
the exact press object, preserve its identity, or fail safely. This
module holds the structured research record (``quality/providers.yaml``)
and, more importantly, the gate that turns research into a qualification:
an edition is qualified for a provider's product and region only when a
physical copy ordered through the real route passes every inspection
point, and that qualification is bound to the edition's identity so a
production-affecting change invalidates it deterministically.

Two rules keep the record honest. Every capability is recorded
explicitly as supported, unsupported, by_approval, or unknown -- an
unsupported capability is never simulated. And marketing claims are
evidence, never qualification: no evidence link can pass the physical
gate, only an inspected copy can.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from . import yamlio

ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE_RECORD = ROOT / "quality" / "providers.yaml"
PACKAGED_RECORD = Path(__file__).resolve().parent / "data" / "providers.yaml"
# Compatibility for callers that link to the repository ledger. Runtime
# loading goes through _record_path() so an installed wheel uses its packaged
# mirror instead of guessing that the repository exists above site-packages.
RECORD = SOURCE_RECORD

# The one canonical provider ledger is quality/providers.yaml. The packaged
# copy an installed wheel loads is a deterministic projection of it: this
# fixed banner, then the canonical bytes verbatim. Generating (rather than
# hand-copying) the mirror is what keeps a maintainer's edit -- a new
# provider, a corrected citation, even a reworded comment -- from silently
# shipping stale in the wheel. Regenerate with `press selftest --write-docs`;
# the selftest fails when regeneration would change the packaged bytes.
PACKAGED_HEADER = (
    "# GENERATED -- DO NOT EDIT. Deterministic projection of\n"
    "# quality/providers.yaml (the one canonical provider ledger): this\n"
    "# banner, then that file verbatim. Edit quality/providers.yaml, then run\n"
    "# `press selftest --write-docs` to regenerate this copy; the selftest\n"
    "# fails when regeneration would change these bytes. The update and review\n"
    "# workflow is docs/PROVIDER-DATA.md.\n"
    "\n"
)


def render_packaged() -> str:
    """The exact bytes the packaged mirror must contain: the fixed banner
    followed by quality/providers.yaml verbatim. Deterministic -- the same
    canonical source always yields the same packaged bytes -- so a byte
    comparison against the committed copy is a real staleness gate, catching
    comment and whitespace drift a semantic (post-YAML-load) compare misses."""

    return PACKAGED_HEADER + SOURCE_RECORD.read_text(encoding="utf-8")


SCHEMA_VERSION = 1
DISPOSITIONS = frozenset({"primary", "secondary", "hosted-candidate", "candidate", "not-fit"})
# A not-fit provider cannot be qualified for production, whatever a copy shows.
PRODUCTION_DISPOSITIONS = frozenset({"primary", "secondary", "hosted-candidate", "candidate"})
CAPABILITY_VALUES = frozenset({"supported", "unsupported", "by_approval", "unknown"})
REQUIRED_CAPABILITIES = frozenset(
    {
        "api",
        "sandbox",
        "one_copy_pod",
        "file_validation",
        "pricing_api",
        "order_creation",
        "shipping",
        "cancellation",
        "webhooks",
        "worldwide",
        "seller_of_record",
    }
)
# The inspection points every provider+product+region must pass, in order.
REQUIRED_CHECKLIST = (
    "content",
    "pagination",
    "trim",
    "bleed",
    "spine",
    "barcode",
    "color",
    "paper",
    "binding",
    "packaging",
    "tracking",
)

PASS = "pass"


@dataclass(frozen=True)
class Provider:
    name: str
    disposition: str
    routes: tuple[str, ...]
    evidence: tuple[dict[str, str], ...]
    capabilities: dict[str, str]
    unknowns: tuple[str, ...]
    notes: str = ""


def _record_path() -> Path:
    return SOURCE_RECORD if SOURCE_RECORD.is_file() else PACKAGED_RECORD


def load(path: Path | None = None) -> dict:
    selected = path if path is not None else _record_path()
    return yamlio.loads(selected.read_text(encoding="utf-8"))


def providers(record: dict | None = None) -> dict[str, Provider]:
    record = record if record is not None else load()
    out: dict[str, Provider] = {}
    for name, raw in (record.get("providers") or {}).items():
        out[name] = Provider(
            name=name,
            disposition=raw.get("disposition", ""),
            routes=tuple(raw.get("routes", ())),
            evidence=tuple(raw.get("evidence", ())),
            capabilities=dict(raw.get("capabilities", {})),
            unknowns=tuple(raw.get("unknowns", ())),
            notes=raw.get("notes", ""),
        )
    return out


def _validate_identity(name: str, prov: Provider) -> list[str]:
    """Disposition, routes-presence, and evidence-completeness defects."""

    problems: list[str] = []
    if prov.disposition not in DISPOSITIONS:
        problems.append(f"{name}: unknown disposition {prov.disposition!r}")
    if not prov.routes:
        problems.append(f"{name}: no routes recorded")
    if not prov.evidence or any(not e.get("claim") or not e.get("url") for e in prov.evidence):
        problems.append(f"{name}: every evidence entry needs a claim and a url")
    return problems


def _validate_capabilities(name: str, prov: Provider) -> list[str]:
    """Capabilities must be exactly the required set, each an explicit value:
    an omitted capability is an implicit claim, which is forbidden."""

    problems: list[str] = []
    missing = REQUIRED_CAPABILITIES - set(prov.capabilities)
    extra = set(prov.capabilities) - REQUIRED_CAPABILITIES
    if missing:
        problems.append(f"{name}: capabilities not declared: {sorted(missing)}")
    if extra:
        problems.append(f"{name}: unknown capabilities: {sorted(extra)}")
    for cap, value in prov.capabilities.items():
        if value not in CAPABILITY_VALUES:
            problems.append(
                f"{name}: capability {cap}={value!r} is not one of {sorted(CAPABILITY_VALUES)}"
            )
    return problems


def _validate_entry_types(name: str, prov: Provider) -> list[str]:
    """A `- text: more` line is YAML for a mapping, not a string; catch that
    so an unknowns or routes entry cannot silently become a dict."""

    problems: list[str] = []
    if any(not isinstance(u, str) for u in prov.unknowns):
        problems.append(
            f"{name}: every 'unknowns' entry must be a string (a colon made one a mapping)"
        )
    if any(not isinstance(r, str) for r in prov.routes):
        problems.append(f"{name}: every 'routes' entry must be a string")
    return problems


def _validate_provider(name: str, prov: Provider) -> list[str]:
    problems: list[str] = []
    problems.extend(_validate_identity(name, prov))
    problems.extend(_validate_capabilities(name, prov))
    problems.extend(_validate_entry_types(name, prov))
    return problems


def _validate_packaged_mirror() -> list[str]:
    """Defects in the packaged wheel mirror of the canonical ledger, checked
    only when the canonical source is present on disk."""

    if not SOURCE_RECORD.is_file():
        return []
    if not PACKAGED_RECORD.is_file():
        return ["packaged provider record is missing: press/data/providers.yaml"]
    if PACKAGED_RECORD.read_text(encoding="utf-8") != render_packaged():
        return [
            "packaged provider record is stale: regenerate it byte-for-byte "
            "from quality/providers.yaml with `press selftest --write-docs`"
        ]
    return []


def _validate_schema_and_checklist(record: dict) -> list[str]:
    """Schema-version and physical-checklist defects for the record."""

    problems: list[str] = []
    if record.get("schema_version") != SCHEMA_VERSION:
        problems.append(
            f"unknown schema version {record.get('schema_version')} "
            f"(this press writes {SCHEMA_VERSION})"
        )
    checklist = tuple(record.get("physical_checklist", ()))
    for point in REQUIRED_CHECKLIST:
        if point not in checklist:
            problems.append(f"physical checklist missing required point: {point}")
    for point in checklist:
        if point not in CHECKLIST_HELP:
            problems.append(f"checklist point {point!r} has no description in CHECKLIST_HELP")
    return problems


def validate(record: dict | None = None) -> list[str]:
    """Every defect in the qualification record: a bad schema, a physical
    checklist missing a required inspection point, or a provider with an
    unknown disposition, no evidence, or an implicit capability."""

    default_record = record is None
    record = record if record is not None else load()
    problems: list[str] = []
    if default_record:
        problems.extend(_validate_packaged_mirror())
    problems.extend(_validate_schema_and_checklist(record))
    for name, prov in providers(record).items():
        problems.extend(_validate_provider(name, prov))
    return problems


@dataclass(frozen=True)
class PhysicalInspection:
    """The result of inspecting one physically ordered copy, scoped to the
    exact edition it was cut from. Each checklist point is dispositioned;
    only a copy with every point 'pass' can qualify a provider."""

    edition_id: str
    provider: str
    product_id: str
    region: str
    inspector: str
    results: dict[str, str]  # checklist point -> "pass" | "fail"

    def digest(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def unresolved(self, checklist: tuple[str, ...] = REQUIRED_CHECKLIST) -> list[str]:
        """Checklist points not recorded as a pass (missing or failed)."""

        return [point for point in checklist if self.results.get(point) != PASS]


def qualify(inspection: PhysicalInspection, edition_id: str, record: dict | None = None):
    """Turn a passed physical inspection into a provider qualification bound
    to the edition, or a list of the reasons it does not qualify. Returns
    ``(ProviderQualification | None, problems)``. Marketing evidence alone
    can never reach here: only a copy with every inspection point passed,
    ordered against this exact edition, qualifies."""

    from . import edition as edition_mod

    record = record if record is not None else load()
    known = providers(record)
    problems: list[str] = []

    prov = known.get(inspection.provider)
    if prov is None:
        problems.append(f"unknown provider {inspection.provider!r}")
    elif prov.disposition not in PRODUCTION_DISPOSITIONS:
        problems.append(
            f"provider {inspection.provider!r} disposition "
            f"{prov.disposition!r} cannot be qualified for production"
        )

    if inspection.edition_id != edition_id:
        problems.append(
            "inspection is for a different edition "
            f"({inspection.edition_id[:12]} != {edition_id[:12]}); "
            "qualification is scoped to an exact edition identity"
        )

    unresolved = inspection.unresolved(tuple(record.get("physical_checklist", REQUIRED_CHECKLIST)))
    if unresolved:
        problems.append(
            f"physical inspection not passed: {unresolved}; a marketing claim "
            "cannot satisfy the physical gate"
        )

    if problems:
        return None, problems

    qualification = edition_mod.ProviderQualification(
        provider=inspection.provider,
        product_id=inspection.product_id,
        qualified_for=edition_id,
        evidence_digest=inspection.digest(),
    )
    return qualification, []


def book_inspections(root: Path) -> list[PhysicalInspection]:
    """The passed physical inspections a book declares in its optional
    ``config/qualification.yaml`` -- the record that an ordered copy of a
    named edition passed every checklist point. Empty when the file is
    absent."""

    path = root / "config" / "qualification.yaml"
    if not path.is_file():
        return []
    data = yamlio.loads(path.read_text(encoding="utf-8")) or {}
    out: list[PhysicalInspection] = []
    for raw in data.get("inspections", ()):
        out.append(
            PhysicalInspection(
                edition_id=str(raw.get("edition_id", "")),
                provider=str(raw.get("provider", "")),
                product_id=str(raw.get("product_id", "")),
                region=str(raw.get("region", "")),
                inspector=str(raw.get("inspector", "")),
                results=dict(raw.get("results", {})),
            )
        )
    return out


# What each physical inspection point actually checks on the ordered copy.
CHECKLIST_HELP = {
    "content": "the interior text matches the release-approved manuscript",
    "pagination": "page count and page order match the manifest",
    "trim": "the cut size matches the declared trim within tolerance",
    "bleed": "full-bleed art reaches the trimmed edge without white slivers",
    "spine": "spine text is centred and square for the page count",
    "barcode": "the EAN-13 scans and matches the declared ISBN",
    "color": "single-ink interior and cover reproduce as specified",
    "paper": "stock weight and shade match the declared paper",
    "binding": "the binding is square, tight, and opens flat enough to read",
    "packaging": "the copy arrives undamaged and appropriately protected",
    "tracking": "the tracking link resolves and matches the destination",
}

_CAP_LABELS = {
    "supported": "Supported",
    "by_approval": "By approval",
    "unsupported": "Unsupported",
    "unknown": "Unknown",
}
_DISPOSITION_TITLE = {
    "primary": "Primary provider",
    "secondary": "Second adapter",
    "hosted-candidate": "Hosted-checkout candidate",
    "candidate": "Candidate",
    "not-fit": "Not a fit",
}


def _evidence_links(prov: Provider) -> str:
    """Render each evidence source as a labeled link. The label is the
    entry's own claim (what the source shows), not the bare hostname, so two
    links to the same host do not read as identical text and an opaque CDN
    URL still has a meaningful label."""

    from urllib.parse import urlparse

    parts = []
    for entry in prov.evidence:
        claim = (entry.get("claim") or "").strip()
        label = claim or urlparse(entry.get("url", "")).netloc or "source"
        if len(label) > 60:
            label = label[:57].rstrip() + "..."
        parts.append(f"[{label}]({entry['url']})")
    return " · ".join(parts)


def render(record: dict | None = None) -> str:
    """The human-readable projection of the record, one card per provider,
    generated so it cannot drift from the evidence it summarizes."""

    record = record if record is not None else load()
    lines = [
        "# Print-provider qualification",
        "",
        "Generated by `press selftest --write-docs` from "
        "`quality/providers.yaml`. Do not edit by hand.",
        "",
        "A provider here is *researched*, not *qualified*: an edition becomes "
        "qualified for a provider only when a physically ordered copy passes "
        "every inspection point below, scoped to that edition's identity.",
        "",
        "**Physical inspection** — order a copy through the real route; every "
        "point must pass, none may be skipped:",
        "",
    ]
    lines += _field_table(
        [(point, CHECKLIST_HELP.get(point, "")) for point in record.get("physical_checklist", ())]
    )
    lines.append("")

    for name, prov in providers(record).items():
        by_value: dict[str, list[str]] = {}
        for cap, value in prov.capabilities.items():
            by_value.setdefault(value, []).append(cap.replace("_", " "))
        rows = [("Routes", ", ".join(prov.routes))]
        for value in ("supported", "by_approval", "unsupported", "unknown"):
            if by_value.get(value):
                rows.append((_CAP_LABELS[value], ", ".join(sorted(by_value[value]))))
        if prov.unknowns:
            rows.append(("Open questions", "; ".join(prov.unknowns)))
        if prov.evidence:
            rows.append(("Evidence", _evidence_links(prov)))
        lines += [
            f"## {name.replace('-', ' ').title()}",
            "",
            f"`{name}` · {_DISPOSITION_TITLE.get(prov.disposition, prov.disposition)}",
            "",
            prov.notes,
            "",
        ]
        lines += _field_table(rows)
        lines.append("")
    return "\n".join(lines)


def _field_table(rows: list[tuple[str, str]]) -> list[str]:
    """A small two-column label/value table (headerless; its empty header
    is hidden on the site) -- one small table per record."""

    lines = ["| | |", "|---|---|"]
    for label, value in rows:
        cell = " ".join(str(value).split()).replace("|", "\\|")
        lines.append(f"| **{label}** | {cell} |")
    return lines


def main(argv: list[str] | None = None) -> int:
    """Validate the qualification record:

        python3 -m press.qualification

    Refusals are locatable and exit non-zero.
    """

    problems = validate()
    if problems:
        print("provider qualification record does not hold:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(
        f"provider qualification record holds: {len(providers())} providers, "
        f"{len(REQUIRED_CHECKLIST)}-point physical checklist"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
