"""Domain results and domain exceptions: the typed vocabulary of the press.

Orchestration used to speak in exit codes, prints, and bare ``SystemExit``,
which forced callers (and tests) to scrape text to learn what happened.
These types name the outcomes directly so a caller can assert on a contract
instead of a printed line.

Two families live here:

* **Results** -- ``BuildReceipt``, ``VerificationReport``, ``CheckResult`` --
  the structured record an orchestrator returns. They carry the facts;
  turning them into console text and an exit code is the CLI boundary's
  job (``__main__``), never theirs.
* **Exceptions** -- ``ConfigError``, ``PolicyError``, ``ToolError``,
  ``ArtifactError`` -- the four shapes a boundary failure takes. They are
  the domain's own errors; the CLI boundary decides whether one becomes a
  ``SystemExit`` with a message or an exit code. Nothing here prints.

The exceptions are deliberately *not* raised by the legacy CLI paths yet:
those still raise ``SystemExit`` so ``__main__`` keeps translating exit
codes exactly as before. New adapter code raises these; adoption by the
orchestrators is incremental and is what later trust issues build on.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# --------------------------------------------------------------------------
# Domain exceptions
# --------------------------------------------------------------------------


class PressError(Exception):
    """Base for every domain error the press raises deliberately.

    Distinct from ``SystemExit`` (a CLI-boundary decision) and from raw
    implementation exceptions (a bug, or an unmodeled failure)."""


class ConfigError(PressError):
    """A book's declared inputs are wrong: missing, malformed, or refused
    by policy. The author can fix it by editing config."""


class PolicyError(PressError):
    """An operation was refused because it would violate a press policy
    (a retry budget exhausted, a publication rule broken, a grant denied).
    Not the author's config, and not the tool's fault."""


class ToolError(PressError):
    """An external boundary -- a subprocess, an HTTP API, a credential
    source -- failed or answered with an error. Carries what the boundary
    reported so the CLI can relay it verbatim."""

    def __init__(self, message: str, *, source: str = "", code: int | None = None,
                 detail: str = "") -> None:
        super().__init__(message)
        self.source = source
        self.code = code
        self.detail = detail


class ArtifactError(PressError):
    """A produced or verified artifact violates its contract: a member
    escaped its root, a witness went missing, the bytes disagree with the
    source. The object is wrong, not the request that made it."""


# --------------------------------------------------------------------------
# Domain results
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckResult:
    """The outcome of one editorial or structural check.

    ``ok`` is the single truth of pass/fail; ``findings`` carries the
    human-readable diagnostics a CLI presenter renders. ``check`` names the
    check so a report can index by it."""

    check: str
    ok: bool
    findings: tuple[str, ...] = ()

    @property
    def failed(self) -> bool:
        return not self.ok

    @classmethod
    def passed(cls, check: str) -> "CheckResult":
        return cls(check=check, ok=True, findings=())

    @classmethod
    def failing(cls, check: str, findings: tuple[str, ...] | list[str]) -> "CheckResult":
        return cls(check=check, ok=False, findings=tuple(findings))


@dataclass(frozen=True)
class BuildReceipt:
    """The record of one artifact build: what target ran, which command
    lines it drove, and the concrete outputs it left on disk.

    A receipt is evidence a build happened and what it produced; it is not
    proof the outputs are correct -- that is a ``VerificationReport``."""

    target: str
    outputs: tuple[str, ...] = ()
    commands: tuple[tuple[str, ...], ...] = ()

    def with_command(self, argv: list[str] | tuple[str, ...]) -> "BuildReceipt":
        return BuildReceipt(
            target=self.target,
            outputs=self.outputs,
            commands=self.commands + (tuple(argv),),
        )

    def with_output(self, path: str) -> "BuildReceipt":
        return BuildReceipt(
            target=self.target,
            outputs=self.outputs + (path,),
            commands=self.commands,
        )


@dataclass(frozen=True)
class VerificationReport:
    """The verdict of inspecting a built artifact as an object.

    ``checks`` is the ordered evidence; ``ok`` is true exactly when every
    check passed, so a report cannot claim success while carrying a
    failure."""

    artifact: str
    checks: tuple[CheckResult, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    @property
    def failures(self) -> tuple[CheckResult, ...]:
        return tuple(check for check in self.checks if check.failed)

    def with_check(self, check: CheckResult) -> "VerificationReport":
        return VerificationReport(artifact=self.artifact, checks=self.checks + (check,))
