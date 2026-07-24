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

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from . import artifact_status, catalog, doctor, registry
from .artifact_status import State


@dataclass(frozen=True)
class ArtifactRow:
    name: str
    state: State
    published: bool


# The doctor's tool/dependency states in the same glyph-plus-word idiom the
# artifact table uses, so a machine's health reads at a glance. Missing and
# broken shout with "!"; everything else stays quiet.
DOCTOR_STATE_GLYPH: dict[str, tuple[str, str]] = {
    "ok": ("*", "ok"),
    "absent": ("-", "absent"),
    "missing": ("!", "missing"),
    "broken": ("!", "broken"),
    "warn": ("~", "warn"),
    "unset": ("-", "unset"),
}


@dataclass(frozen=True)
class DoctorRow:
    """One examined capability projected for the dashboard: its state as a
    glyph and word, its identity, the purpose the doctor printed, and
    whether the press declares it required."""

    glyph: str
    state_word: str
    name: str
    purpose: str
    required: bool


def doctor_rows(report: doctor.DoctorReport) -> tuple[DoctorRow, ...]:
    """Project every doctor finding -- each tool, the API keys, the
    python-version finding, and the dependency finding -- into display
    rows in report order, so the panel matches what ``press doctor``
    prints and cannot invent or drop a capability."""

    rows: list[DoctorRow] = []
    for finding in report.findings:
        glyph, word = DOCTOR_STATE_GLYPH.get(finding.state, ("?", finding.state))
        rows.append(
            DoctorRow(glyph, word, finding.name, finding.detail, finding.required)
        )
    return tuple(rows)


# The named phases a full ``press all`` build passes through, in order, as
# emitted by the pilcrow summary lines the build prints between them.
BUILD_PHASES: tuple[str, ...] = ("check", "typeset", "verify")

# ANSI colour is stripped before parsing so a forced-colour child (the
# pilcrow and phase name arrive wrapped in escape codes) parses identically
# to the plain piped stream the desk normally sees.
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_PHASE_RE = re.compile(r"^\s*¶\s+(\w+)")
_TIMING_RE = re.compile(r"^\s+(\S+) took (\d+(?:\.\d+)?)s\s*$")


class ProgressKind(str, Enum):
    """What a build log line announced: a tool invocation starting, a named
    phase completing, or a per-command timing."""

    INVOCATION = "invocation"
    PHASE = "phase"
    TIMING = "timing"


@dataclass(frozen=True)
class ProgressEvent:
    """A single parsed advancement marker. ``detail`` is the command text
    for an invocation, the phase name for a phase, or the tool name for a
    timing; ``seconds`` is set only for a timing."""

    kind: ProgressKind
    detail: str
    seconds: float | None = None


def progress_event(line: str) -> ProgressEvent | None:
    """Classify one build log line as a progress marker, or ``None`` when it
    carries no advancement. Pure: the same input always yields the same
    event, so a test can replay a captured build without a TUI. A line
    beginning ``+ `` is a tool invocation; a pilcrow line naming a known
    phase is that phase completing; a ``  <tool> took N.Ns`` line is a
    timing."""

    plain = _ANSI.sub("", line)
    if plain.startswith("+ "):
        return ProgressEvent(ProgressKind.INVOCATION, plain[2:].strip())
    phase = _PHASE_RE.match(plain)
    if phase is not None and phase.group(1) in BUILD_PHASES:
        return ProgressEvent(ProgressKind.PHASE, phase.group(1))
    timing = _TIMING_RE.match(plain)
    if timing is not None:
        return ProgressEvent(ProgressKind.TIMING, timing.group(1), float(timing.group(2)))
    return None


@dataclass
class RunProgress:
    """The running tally of a build's advancement, folded from progress
    events. Pure and self-contained -- it touches no widget -- so the
    RunScreen mirrors it into a stage line while a unit test replays a log
    straight into it. It counts the tool invocations seen and remembers
    which named phases have completed, in arrival order."""

    invocations: int = 0
    phases_done: tuple[str, ...] = ()

    def observe(self, event: ProgressEvent | None) -> bool:
        """Fold one event (or ``None``) into the tally and report whether it
        changed the display, so the caller only repaints on real movement."""

        if event is None:
            return False
        if event.kind is ProgressKind.INVOCATION:
            self.invocations += 1
            return True
        if event.kind is ProgressKind.PHASE and event.detail not in self.phases_done:
            self.phases_done = (*self.phases_done, event.detail)
            return True
        return False

    @property
    def fraction(self) -> float:
        """How far through the named phases the build has reached, 0.0 to
        1.0, for a progress bar that fills as phases complete."""

        return len(self.phases_done) / len(BUILD_PHASES)

    def status_line(self) -> str:
        """The one-line stage display: each phase with a tick once complete
        or a dot while pending, then the count of tool steps seen."""

        marks = " ".join(
            f"{'✓' if phase in self.phases_done else '·'} {phase}"
            for phase in BUILD_PHASES
        )
        return f"{marks}    {self.invocations} steps"


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
