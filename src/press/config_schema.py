"""The one registry of every book-configuration field `press config`
knows, and how a proposed edit is validated.

Two rules keep this honest:

- **The typed model is the only validation authority.** This registry
  declares a field's file, type, and shape, but a write is accepted or
  rejected by the real loader for that file (`bookmodel.load`,
  `commerce.validate`, `registrations.failures`, the house-rules regex
  compiler), run against the *proposed* document before a byte is
  written. The registry never re-states a schema law those own.
- **Every documented field is accounted for.** A field is either
  ``writable`` (get/set/unset with a declared type) or carries an explicit
  classification: ``immutable`` (locked in v1, e.g. the trim), ``structured``
  (a list managed by a workflow, e.g. the authorities table), or ``file``
  (a whole file or asset, not a keyed value). A drift test walks the
  configuration reference and fails if a documented key has neither.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# Classifications.
WRITABLE = "writable"
IMMUTABLE = "immutable"
STRUCTURED = "structured"
FILE = "file"

METADATA = "config/metadata.yaml"
HOUSE_RULES = "config/house-rules.yaml"
FRONT_MATTER = "config/front-matter.yaml"
AESTHETIC = "config/aesthetic.yaml"
INDEX_TERMS = "config/index-terms.yaml"
AUTHORITIES = "config/authorities.yaml"


@dataclass(frozen=True)
class Field:
    path: str                       # dotted config path, or a file/area name
    file: str                       # config file that owns it ("" for file-area)
    kind: str = WRITABLE
    type: str = "str"               # a config_store type name (writable only)
    help: str = ""
    required: bool = False
    choices: tuple[str, ...] = ()
    https: bool = False             # value must be an https URL
    secret_guarded: bool = False    # a field a credential could wrongly land in
    manager: str = ""               # for non-writable: what to use instead
    whole_file: bool = False        # this entry classifies the entire file

    @property
    def writable(self) -> bool:
        return self.kind == WRITABLE


def _w(path, file, type="str", help="", **kw) -> Field:
    return Field(path=path, file=file, kind=WRITABLE, type=type, help=help, **kw)


# ---- the registry ----------------------------------------------------

_URL = "must be an https URL"

REGISTRY: tuple[Field, ...] = (
    # config/metadata.yaml — identity
    _w("title", METADATA, help="the book's title", required=True),
    _w("subtitle", METADATA, help="the subtitle; OR clauses stack on the title page"),
    _w("author", METADATA, "list[str]", help="byline, one name per list item", required=True),
    _w("date", METADATA, help="free text; the first year in it dates the EPUB"),
    _w("copyright", METADATA, help="copyright line (required once front-matter.yaml exists)"),
    _w("publisher", METADATA, help="imprint (required with front matter)"),
    _w("publisher-place", METADATA, help="imprint place (required with front matter)"),
    _w("description", METADATA, help="one-sentence blurb for the landing page and stores"),
    _w("slug", METADATA, help="artifact basename; [a-z0-9][a-z0-9-]*", required=True),
    _w("repository", METADATA, help="canonical repo URL (optional)"),
    _w("site-url", METADATA, help="public Pages URL (optional)"),
    _w("keywords", METADATA, "list[str]", help="subject keywords for the formats"),
    _w("lang", METADATA, help="BCP-47 language tag passed through to pandoc"),
    _w("rights", METADATA, help="rights statement passed through to pandoc"),
    _w("verify-sentinels", METADATA, "list[str]",
       help="phrases proven present in every artifact (release needs >=2)"),
    _w("verify-min-pages", METADATA, "int", help="PDF page floor (release needs >=24)"),
    # config/metadata.yaml — trim (derived from the design profile)
    Field("trim", METADATA, IMMUTABLE, help="page trim; derived from print.profile",
          manager="trim is not set directly; choose it with print.profile"),
    # config/metadata.yaml — print pack
    _w("print.profile", METADATA,
       help="design profile id: trim and interior geometry (default house-6x9)"),
    _w("print.provider", METADATA,
       help="provider spec for spine and cover geometry (default house)"),
    _w("print.binding", METADATA, help="binding style",
       choices=("perfect-bound", "saddle-stitch", "coil", "casewrap", "dust-jacket")),
    _w("print.material", METADATA, help="cover material",
       choices=("paperback", "casewrap", "linen")),
    _w("print.paper", METADATA, help="interior stock", choices=("white", "cream")),
    _w("print.page-thickness", METADATA, "float", help="inches per page; overrides paper"),
    # config/metadata.yaml — chapter-opening override (the design profile sets
    # the default; a book may override it for its own chapters)
    _w("chapter-opening.style", METADATA, help="chapter-opening initial",
       choices=("none", "drop-cap", "raised-cap")),
    _w("chapter-opening.lines", METADATA, "int", help="text lines the initial spans"),
    _w("chapter-opening.small-caps-remainder", METADATA, "bool",
       help="set the rest of the first word in small caps"),
    # config/metadata.yaml — registrations
    _w("registrations.isbn.print", METADATA, help="print ISBN (13 digits) or 'pending'"),
    _w("registrations.isbn.epub", METADATA, help="EPUB ISBN or 'pending'"),
    _w("registrations.lccn", METADATA, help="LCCN or 'pending'"),
    _w("registrations.issn", METADATA, help="ISSN or 'pending'"),
    _w("registrations.retail", METADATA, "bool",
       help="true makes missing/pending registrations fail check"),
    _w("registrations.isbn-block.prefix", METADATA,
       help="owned ISBN registrant prefix (e.g. 978-1-960780); 'press isbn assign' mints from it"),
    _w("registrations.isbn-block.size", METADATA, "int",
       help="block size Bowker sold: 10, 100, or 1000"),
    # config/metadata.yaml — commerce (secret-guarded surface)
    _w("commerce.print-ordering.enabled", METADATA, "bool", help="turn the order CTA on"),
    _w("commerce.print-ordering.edition", METADATA, help="the edition sold (e.g. paperback)"),
    _w("commerce.print-ordering.storefront-url", METADATA, help=_URL, https=True,
       secret_guarded=True),
    _w("commerce.print-ordering.seller-of-record", METADATA,
       help="who the reader buys from", secret_guarded=True),
    _w("commerce.print-ordering.support-url", METADATA,
       help=f"support page {_URL} (optional; omit to generate)", https=True, secret_guarded=True),
    _w("commerce.print-ordering.privacy-url", METADATA,
       help=f"privacy page {_URL} (optional; omit to generate)", https=True, secret_guarded=True),
    _w("commerce.print-ordering.refund-url", METADATA,
       help=f"returns page {_URL} (optional; omit to generate)", https=True, secret_guarded=True),
    _w("commerce.print-ordering.policies.support", METADATA,
       help="your own text appended to the generated support page", secret_guarded=True),
    _w("commerce.print-ordering.policies.privacy", METADATA,
       help="your own text appended to the generated privacy page", secret_guarded=True),
    _w("commerce.print-ordering.policies.refund", METADATA,
       help="your own text appended to the generated returns page", secret_guarded=True),

    # config/house-rules.yaml
    _w("banned-patterns", HOUSE_RULES, "mapping",
       help="regex -> label; applied by the style audit"),
    _w("jargon-allow", HOUSE_RULES, "list[str]", help="watchlist terms this book may use"),
    _w("audit-dirs", HOUSE_RULES, "list[str]", help="extra directories to lint beyond book/"),

    # config/front-matter.yaml — presence generates the front matter
    _w("edition-note", FRONT_MATTER, help="edition line (falls back to the date)"),
    _w("dedication", FRONT_MATTER, help="dedication page text"),
    _w("epigraph.quote", FRONT_MATTER, help="epigraph text (gates the epigraph page)"),
    _w("epigraph.attribution", FRONT_MATTER, help="epigraph attribution"),
    _w("acknowledgements", FRONT_MATTER, help="acknowledgements page text"),
    _w("rights-notice", FRONT_MATTER, help="colophon rights line"),
    _w("manufacture", FRONT_MATTER, help="colophon manufacture line"),
    _w("colophon-note", FRONT_MATTER, help="colophon typography note"),
    _w("contact", FRONT_MATTER, help="colophon contact line"),
    _w("motto", FRONT_MATTER, help="colophon motto"),

    # config/aesthetic.yaml — prose (prompt material) and programmatic keys
    _w("name", AESTHETIC, help="the aesthetic's name"),
    _w("register", AESTHETIC, help="the register/voice of the design"),
    _w("cover.style", AESTHETIC,
       help="cover style id from the style library (default penguin-tri-band)"),
    _w("cover.subject", AESTHETIC,
       help="the subject of the cover illustration, one phrase"),
    _w("cover.medium", AESTHETIC, help="cover medium (prompt material)"),
    _w("cover.field", AESTHETIC, help="cover field/composition"),
    _w("cover.ink", AESTHETIC, help="cover ink treatment"),
    _w("cover.type-treatment", AESTHETIC, help="cover type treatment"),
    _w("cover.ornament", AESTHETIC, help="cover ornament"),
    _w("cover.emblem", AESTHETIC, help="cover emblem placement"),
    _w("plates.style", AESTHETIC,
       help="default illustration style id (default wood-engraving)"),
    _w("plates.medium", AESTHETIC, help="interior plate medium"),
    _w("plates.composition", AESTHETIC, help="interior plate composition"),
    _w("logomark.tradition", AESTHETIC, help="logomark tradition"),
    _w("portrait.style", AESTHETIC, help="author portrait style"),
    _w("typography.web-family", AESTHETIC, help="CSS font stack for the web reader"),
    _w("typography.pdf-family", AESTHETIC, help="LaTeX main font ('' keeps Libertinus)"),
    _w("web-palette", AESTHETIC, "mapping", help="light-theme token -> #hex"),
    _w("web-palette-dark", AESTHETIC, "mapping", help="dark-theme token -> #hex"),
    _w("book-colors.ink", AESTHETIC, help="PDF ink color, hex without #"),
    _w("book-colors.muted", AESTHETIC, help="PDF muted color, hex without #"),
    _w("book-colors.accent", AESTHETIC, help="PDF accent color, hex without #"),
    _w("book-colors.link", AESTHETIC, help="PDF link color, hex without #"),

    # Structured lists — managed by their workflows, not scalar-addressable.
    Field("index-terms", "config/index-terms.yaml", STRUCTURED, whole_file=True,
          help="curated subject-index terms (a list)",
          manager="edit config/index-terms.yaml or curate with the index workflow"),
    Field("authorities", "config/authorities.yaml", STRUCTURED, whole_file=True,
          help="the table of authorities (a list)",
          manager="populate with the authorities-research workflow"),
    Field("qualification", "config/qualification.yaml", STRUCTURED, whole_file=True,
          help="physical-inspection records (schema_version + inspections)",
          manager="record a physical qualification; edition_id comes from press"),

    # Whole-file / asset areas — presence toggles, not keyed values.
    Field("tex/title-page.tex", "", FILE, whole_file=True,
          help="hand-authored front matter override",
          manager="author the .tex file directly"),
    Field("assets", "", FILE, whole_file=True,
          help="cover, logo, plates, author photo, and web CSS",
          manager="place the files under assets/ (and art/)"),
)


# ---- lookups ---------------------------------------------------------

_BY_PATH = {f.path: f for f in REGISTRY}


def field_for(path: str) -> Field | None:
    return _BY_PATH.get(path)


def writable_fields() -> list[Field]:
    return [f for f in REGISTRY if f.writable]


def covers(path: str) -> Field | None:
    """The registry field that governs a documented example path: an exact
    match, or an ancestor that is a mapping/structured/whole-file entry
    (so ``web-palette.cloth`` is covered by ``web-palette``)."""

    exact = _BY_PATH.get(path)
    if exact is not None:
        return exact
    parts = path.split(".")
    for i in range(len(parts) - 1, 0, -1):
        ancestor = _BY_PATH.get(".".join(parts[:i]))
        if ancestor is not None and (
            ancestor.type == "mapping" or ancestor.kind in (STRUCTURED, FILE)
        ):
            return ancestor
    return None


# ---- validation routing (the real authorities, on proposed data) -----

def _shape_name(value: object) -> str:
    """A human name for a YAML top-level shape, for a diagnostic that tells
    an author what they wrote instead of the expected structure."""

    if isinstance(value, dict):
        return "a mapping"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, str):
        return "a string"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, (int, float)):
        return "a number"
    if value is None:
        return "empty"
    return type(value).__name__


def _validate_metadata(root: Path, proposed: object) -> list[str]:
    from . import bookmodel, commerce, registrations

    if not isinstance(proposed, dict):
        return [f"must be a YAML mapping, not {_shape_name(proposed)}"]
    problems: list[str] = []
    try:
        bookmodel.load(root, dict(proposed))
    except SystemExit as exc:
        problems.append(str(exc))
    problems += commerce.validate(commerce.load(dict(proposed)))
    problems += registrations.failures(dict(proposed.get("registrations") or {}))
    return problems


def _validate_house_rules(root: Path, proposed: object) -> list[str]:
    from . import style_audit

    if not isinstance(proposed, dict):
        return [f"must be a YAML mapping, not {_shape_name(proposed)}"]
    problems: list[str] = []
    banned = proposed.get("banned-patterns")
    if banned is not None and not isinstance(banned, dict):
        problems.append(
            f"banned-patterns must be a mapping of regex -> label, "
            f"not {_shape_name(banned)}"
        )
    for key in ("jargon-allow", "audit-dirs"):
        value = proposed.get(key)
        if value is not None and (
            not isinstance(value, list)
            or not all(isinstance(item, str) for item in value)
        ):
            problems.append(f"{key} must be a list of strings")
    if problems:
        # A wrong shape would crash the regex compiler or the audit walk with
        # a bare traceback; stop here rather than hand it a malformed value.
        return problems
    try:
        style_audit.banned_book_patterns(dict(proposed))
    except SystemExit as exc:
        return [str(exc)]
    return []


def _validate_front_matter(root: Path, proposed: object) -> list[str]:
    # front-matter.yaml has no typed model, but the build dereferences it as a
    # mapping (gen_front_matter) and reads epigraph as a nested mapping; a
    # wrong shape here crashes the renderer with a bare AttributeError, so the
    # shapes the generator touches are guarded at check time instead.
    if proposed is None or proposed == {}:
        return []
    if not isinstance(proposed, dict):
        return [f"must be a YAML mapping, not {_shape_name(proposed)}"]
    epigraph = proposed.get("epigraph")
    if epigraph is not None and not isinstance(epigraph, dict):
        return [
            "epigraph must be a mapping with quote and attribution, "
            f"not {_shape_name(epigraph)}"
        ]
    return []


def _validate_index_terms(root: Path, proposed: object) -> list[str]:
    """The subject-index ledger gen_index.py reads: a list of {term, match}
    entries. A wrong shape (a terms: wrapper, bare strings) is accepted by no
    other guard and crashes the renderer with `string indices must be
    integers`; refuse it here with a located diagnostic."""

    if proposed is None:
        return []
    if not isinstance(proposed, list):
        return [
            "must be a list of {term, match} entries, "
            f"not {_shape_name(proposed)} (see docs/CONFIGURATION.md)"
        ]
    problems: list[str] = []
    for index, entry in enumerate(proposed, start=1):
        if not isinstance(entry, dict):
            problems.append(
                f"entry {index}: must be a mapping with term and match, "
                f"not {_shape_name(entry)}"
            )
            continue
        term = entry.get("term")
        if not isinstance(term, str) or not term.strip():
            problems.append(f"entry {index}: term is missing or empty")
        match = entry.get("match")
        if not isinstance(match, list) or not match:
            problems.append(
                f"entry {index}: match must be a non-empty list of strings"
            )
        elif not all(isinstance(alt, str) and alt.strip() for alt in match):
            problems.append(f"entry {index}: every match alternative must be a string")
    return problems


def _validate_authorities(root: Path, proposed: object) -> list[str]:
    """The claim ledger gen_authorities.py reads: a list of entries, each a
    mapping with a non-empty claim and authority. The build additionally
    proves each claim still appears in the text; this validates only the
    shape, so a malformed ledger fails at check time with a located
    diagnostic rather than deep in the appendix generator."""

    if proposed is None:
        return []
    if not isinstance(proposed, list):
        return [f"must be a list of claim entries, not {_shape_name(proposed)}"]
    problems: list[str] = []
    for index, entry in enumerate(proposed, start=1):
        if not isinstance(entry, dict):
            problems.append(
                f"entry {index}: must be a mapping, not {_shape_name(entry)}"
            )
            continue
        for key in ("claim", "authority"):
            value = entry.get(key)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"entry {index}: {key} is missing or empty")
    return problems


def _validate_none(root: Path, proposed: object) -> list[str]:
    # aesthetic.yaml has no load-time validator; the build validates it in
    # context. The registry's typed coercion is the guard for a scalar edit.
    return []


FILE_VALIDATORS: dict[str, Callable[[Path, object], list[str]]] = {
    METADATA: _validate_metadata,
    HOUSE_RULES: _validate_house_rules,
    FRONT_MATTER: _validate_front_matter,
    AESTHETIC: _validate_none,
    INDEX_TERMS: _validate_index_terms,
    AUTHORITIES: _validate_authorities,
}

# The optional, build-consumed config files whose shape `press check` proves
# before a byte is rendered: files a malformed edit could otherwise sneak past
# check and crash the renderer on. (metadata is already checked by
# check_source and registrations; aesthetic has no crashing dereference.)
CHECKED_SHAPES: tuple[str, ...] = (INDEX_TERMS, AUTHORITIES, FRONT_MATTER, HOUSE_RULES)


def validate_file(root: Path, file: str, proposed: object) -> list[str]:
    """Run the real validator for a config file against a proposed
    document, returning every problem (empty when it would be accepted).

    The proposed document is read back through the package's plain loader
    first, so the validator judges the parsed types that will land on disk
    (a quoted number as a string, a bare number as an int, a top-level list
    that stays a list), not ruamel's round-trip nodes."""

    from . import config_store, yamlio

    plain = yamlio.loads(config_store.dumps(proposed))
    validator = FILE_VALIDATORS.get(file, _validate_none)
    return validator(root, plain)


def enforce_file(root: Path, file: str, proposed: object) -> None:
    """Raise a located SystemExit if a build-consumed config file has a
    shape the renderer would dereference into a bare TypeError.

    `press check` runs the same shape check up front, but the direct
    format targets (`press pdf`, `press epub`, `press html`, ...) dispatch
    to the build with no check in front, so each generator calls this
    before touching the file. Same guard, same single source of truth as
    check time; a malformed file fails naming itself, not deep in a
    generator with `string indices must be integers`."""

    problems = validate_file(root, file, proposed)
    if problems:
        raise SystemExit(
            f"{file} is malformed (fix it before building):\n"
            + "\n".join(f"  - {p}" for p in problems)
        )
