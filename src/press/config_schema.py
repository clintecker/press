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

def _validate_metadata(root: Path, proposed: dict) -> list[str]:
    from . import bookmodel, commerce, registrations

    problems: list[str] = []
    try:
        bookmodel.load(root, dict(proposed))
    except SystemExit as exc:
        problems.append(str(exc))
    problems += commerce.validate(commerce.load(dict(proposed)))
    problems += registrations.failures(dict(proposed.get("registrations") or {}))
    return problems


def _validate_house_rules(root: Path, proposed: dict) -> list[str]:
    from . import style_audit

    try:
        style_audit.banned_book_patterns(dict(proposed))
    except SystemExit as exc:
        return [str(exc)]
    return []


def _validate_none(root: Path, proposed: dict) -> list[str]:
    # front-matter.yaml and aesthetic.yaml have no load-time validator; the
    # build validates them in context. The registry's typed coercion is the
    # guard for a scalar edit here.
    return []


FILE_VALIDATORS: dict[str, Callable[[Path, dict], list[str]]] = {
    METADATA: _validate_metadata,
    HOUSE_RULES: _validate_house_rules,
    FRONT_MATTER: _validate_none,
    AESTHETIC: _validate_none,
}


def validate_file(root: Path, file: str, proposed: dict) -> list[str]:
    """Run the real validator for a config file against a proposed
    document, returning every problem (empty when it would be accepted).

    The proposed document is read back through the package's plain loader
    first, so the validator judges the parsed types that will land on disk
    (a quoted number as a string, a bare number as an int), not ruamel's
    round-trip nodes."""

    from . import config_store

    plain = config_store.as_build_reads(proposed)
    validator = FILE_VALIDATORS.get(file, _validate_none)
    return validator(root, plain)
