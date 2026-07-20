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

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD = ROOT / "quality" / "providers.yaml"

SCHEMA_VERSION = 1
DISPOSITIONS = frozenset({
    "primary", "secondary", "hosted-candidate", "candidate", "not-fit"})
# A not-fit provider cannot be qualified for production, whatever a copy shows.
PRODUCTION_DISPOSITIONS = frozenset({
    "primary", "secondary", "hosted-candidate", "candidate"})
CAPABILITY_VALUES = frozenset({"supported", "unsupported", "by_approval", "unknown"})
REQUIRED_CAPABILITIES = frozenset({
    "api", "sandbox", "one_copy_pod", "file_validation", "pricing_api",
    "order_creation", "shipping", "cancellation", "webhooks", "worldwide",
    "seller_of_record"})
# The inspection points every provider+product+region must pass, in order.
REQUIRED_CHECKLIST = (
    "content", "pagination", "trim", "bleed", "spine", "barcode", "color",
    "paper", "binding", "packaging", "tracking")

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


def load(path: Path = RECORD) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def providers(record: dict | None = None) -> dict[str, Provider]:
    record = record if record is not None else load()
    out: dict[str, Provider] = {}
    for name, raw in (record.get("providers") or {}).items():
        out[name] = Provider(
            name=name, disposition=raw.get("disposition", ""),
            routes=tuple(raw.get("routes", ())),
            evidence=tuple(raw.get("evidence", ())),
            capabilities=dict(raw.get("capabilities", {})),
            unknowns=tuple(raw.get("unknowns", ())),
            notes=raw.get("notes", ""))
    return out


def _validate_provider(name: str, prov: Provider) -> list[str]:
    problems: list[str] = []
    if prov.disposition not in DISPOSITIONS:
        problems.append(f"{name}: unknown disposition {prov.disposition!r}")
    if not prov.routes:
        problems.append(f"{name}: no routes recorded")
    if not prov.evidence or any(
            not e.get("claim") or not e.get("url") for e in prov.evidence):
        problems.append(f"{name}: every evidence entry needs a claim and a url")
    # Capabilities must be exactly the required set, each an explicit value:
    # an omitted capability is an implicit claim, which is forbidden.
    missing = REQUIRED_CAPABILITIES - set(prov.capabilities)
    extra = set(prov.capabilities) - REQUIRED_CAPABILITIES
    if missing:
        problems.append(f"{name}: capabilities not declared: {sorted(missing)}")
    if extra:
        problems.append(f"{name}: unknown capabilities: {sorted(extra)}")
    for cap, value in prov.capabilities.items():
        if value not in CAPABILITY_VALUES:
            problems.append(f"{name}: capability {cap}={value!r} is not one of "
                            f"{sorted(CAPABILITY_VALUES)}")
    # A `- text: more` line is YAML for a mapping, not a string; catch that
    # so an unknowns or routes entry cannot silently become a dict.
    if any(not isinstance(u, str) for u in prov.unknowns):
        problems.append(f"{name}: every 'unknowns' entry must be a string "
                        "(a colon made one a mapping)")
    if any(not isinstance(r, str) for r in prov.routes):
        problems.append(f"{name}: every 'routes' entry must be a string")
    return problems


def validate(record: dict | None = None) -> list[str]:
    """Every defect in the qualification record: a bad schema, a physical
    checklist missing a required inspection point, or a provider with an
    unknown disposition, no evidence, or an implicit capability."""

    record = record if record is not None else load()
    problems: list[str] = []
    if record.get("schema_version") != SCHEMA_VERSION:
        problems.append(
            f"unknown schema version {record.get('schema_version')} "
            f"(this press writes {SCHEMA_VERSION})")
    checklist = tuple(record.get("physical_checklist", ()))
    for point in REQUIRED_CHECKLIST:
        if point not in checklist:
            problems.append(f"physical checklist missing required point: {point}")
    for point in checklist:
        if point not in CHECKLIST_HELP:
            problems.append(f"checklist point {point!r} has no description in CHECKLIST_HELP")
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


def qualify(inspection: PhysicalInspection, edition_id: str,
            record: dict | None = None):
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
            f"{prov.disposition!r} cannot be qualified for production")

    if inspection.edition_id != edition_id:
        problems.append(
            "inspection is for a different edition "
            f"({inspection.edition_id[:12]} != {edition_id[:12]}); "
            "qualification is scoped to an exact edition identity")

    unresolved = inspection.unresolved(tuple(
        record.get("physical_checklist", REQUIRED_CHECKLIST)))
    if unresolved:
        problems.append(
            f"physical inspection not passed: {unresolved}; a marketing claim "
            "cannot satisfy the physical gate")

    if problems:
        return None, problems

    qualification = edition_mod.ProviderQualification(
        provider=inspection.provider, product_id=inspection.product_id,
        qualified_for=edition_id, evidence_digest=inspection.digest())
    return qualification, []


def book_inspections(root: Path) -> list[PhysicalInspection]:
    """The passed physical inspections a book declares in its optional
    ``config/qualification.yaml`` -- the record that an ordered copy of a
    named edition passed every checklist point. Empty when the file is
    absent."""

    path = root / "config" / "qualification.yaml"
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[PhysicalInspection] = []
    for raw in data.get("inspections", ()):
        out.append(PhysicalInspection(
            edition_id=str(raw.get("edition_id", "")),
            provider=str(raw.get("provider", "")),
            product_id=str(raw.get("product_id", "")),
            region=str(raw.get("region", "")),
            inspector=str(raw.get("inspector", "")),
            results=dict(raw.get("results", {}))))
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

_CAP_LABELS = {"supported": "Supported", "by_approval": "By approval",
               "unsupported": "Unsupported", "unknown": "Unknown"}
_DISPOSITION_TITLE = {
    "primary": "Primary provider", "secondary": "Second adapter",
    "hosted-candidate": "Hosted-checkout candidate", "candidate": "Candidate",
    "not-fit": "Not a fit"}


def _evidence_links(prov: Provider) -> str:
    from urllib.parse import urlparse

    parts = []
    for entry in prov.evidence:
        label = urlparse(entry.get("url", "")).netloc or "source"
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
    for point in record.get("physical_checklist", ()):
        help_text = CHECKLIST_HELP.get(point, "")
        lines.append(f"- **{point}** {help_text}" if help_text else f"- {point}")
    lines.append("")

    for name, prov in providers(record).items():
        by_value: dict[str, list[str]] = {}
        for cap, value in prov.capabilities.items():
            by_value.setdefault(value, []).append(cap.replace("_", " "))
        lines += [
            f"## {name.replace('-', ' ').title()}",
            "",
            f"`{name}` · {_DISPOSITION_TITLE.get(prov.disposition, prov.disposition)}",
            "",
            prov.notes,
            "",
            f"- **Routes** {', '.join(prov.routes)}",
        ]
        for value in ("supported", "by_approval", "unsupported", "unknown"):
            if by_value.get(value):
                lines.append(f"- **{_CAP_LABELS[value]}** {', '.join(sorted(by_value[value]))}")
        if prov.unknowns:
            lines.append(f"- **Open questions** {'; '.join(prov.unknowns)}")
        if prov.evidence:
            lines.append(f"- **Evidence** {_evidence_links(prov)}")
        lines.append("")
    return "\n".join(lines)


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
    print(f"provider qualification record holds: {len(providers())} providers, "
          f"{len(REQUIRED_CHECKLIST)}-point physical checklist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
