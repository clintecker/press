"""The DESK read model: the operator desk's home facts, assembled from
the authoritative registries and nothing else.

The desk does not parse YAML, walk dist/, probe tools, or restate
command and artifact names. It reads one typed model built here from
the single sources of truth: book identity from the typed Book model,
the artifact rows from the registry projected through digest-based
evidence, the machine capabilities from the doctor's typed findings,
and the command surface from the one catalog. Building the model is
in-process and read-only; the desk never mutates a book to learn about
it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import artifact_status, catalog, doctor, registry
from .artifact_status import State


@dataclass(frozen=True)
class ArtifactRow:
    name: str
    state: State
    published: bool


@dataclass(frozen=True)
class Identity:
    title: str
    authors: tuple[str, ...]
    slug: str
    trim: str


@dataclass(frozen=True)
class DeskModel:
    identity: Identity
    artifacts: tuple[ArtifactRow, ...]
    capabilities: doctor.DoctorReport
    commands: tuple[catalog.Command, ...]

    @property
    def ready(self) -> bool:
        return self.capabilities.ready

    def blocked_reason(self, command_name: str) -> str | None:
        """Why a command cannot run now, or None. A build command is
        blocked when a required toolchain capability is missing, so the
        desk can gray it out with the reason instead of failing mid-run."""

        failing = set(self.capabilities.failing)
        if command_name in {"pdf", "print", "verify", "verify-print", "all"} \
                and {"pandoc", "lualatex", "latexmk"} & failing:
            missing = sorted({"pandoc", "lualatex", "latexmk"} & failing)
            return f"missing {', '.join(missing)}"
        return None


def build_model(root: Path, evidence: dict[str, str] | None = None,
                report: doctor.DoctorReport | None = None) -> DeskModel:
    """Assemble the desk model from the registries. evidence maps output
    paths to verified digests (empty means everything present is
    unverified); report lets a caller inject doctor findings for a
    deterministic model."""

    from . import booklib

    book = booklib.book()
    slug = book.slug
    evidence = evidence or {}
    # Registry outputs are named relative to dist/, where every artifact
    # lands; evidence keys are relative to the same base.
    dist = root / "dist"
    rows = []
    for artifact in registry.ARTIFACTS.values():
        if not registry.condition_holds(artifact):
            continue
        state = artifact_status.artifact_state(dist, slug, artifact.outputs, evidence)
        rows.append(ArtifactRow(artifact.name, state, artifact.published))

    identity = Identity(
        title=book.title,
        authors=book.authors,
        slug=slug,
        trim=f"{book.trim_width:g} x {book.trim_height:g} in",
    )
    return DeskModel(
        identity=identity,
        artifacts=tuple(rows),
        capabilities=report if report is not None else doctor.examine(),
        commands=catalog.COMMANDS,
    )
