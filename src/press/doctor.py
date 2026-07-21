"""press doctor: name what this machine can and cannot do.

The press leans on external tools with different failure smells: a
missing pandoc kills every build, a missing lualatex kills only PDFs,
a missing epubcheck merely softens one gate, and a missing claude CLI
disables the operator. The doctor examines each dependency, says what
works, what does not, and what each absence costs, so a new machine's
first failure is a diagnosis instead of a traceback.

The probing and the printing are two separate acts. ``examine`` reaches
the boundary (PATH resolution, a ``--version`` run, the environment,
the interpreter) and returns immutable :class:`DoctorReport` data with
no I/O; ``main`` is a thin renderer over that report. The operator desk
consumes ``examine`` directly for capability gating, so nothing there
prints or scrapes prose.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from typing import Callable

from . import adapters


CHECKS = [
    ("pandoc", "every build target", True),
    ("lualatex", "PDF and print builds", True),
    ("latexmk", "PDF and print builds (multi-pass convergence)", True),
    ("pdftoppm", "PDF verification renders", True),
    ("pdffonts", "font-embedding verification", True),
    ("pdfinfo", "PDF structure verification", True),
    ("pdftotext", "PDF text verification", True),
    ("git", "scaffolding identity and book repositories", True),
    ("epubcheck", "the retail EPUB gate (softens to a warning locally)", False),
    ("claude", "the operator: press improve, research, aesthetic briefs", False),
]

KEYS = [
    ("OPENAI_API_KEY", "press art commission --model openai"),
    ("GEMINI_API_KEY", "press art commission --model gemini"),
]

# A capability in one of these states denies the machine; every other
# state (ok, absent, warn, unset) is reportable but not disqualifying.
# ``broken`` disqualifies even an optional tool: a binary present but
# unrunnable is a machine fault, not a soft absence.
_FAILING_STATES = frozenset({"missing", "broken"})

# How each canonical state prints in the seven-column status gutter.
# Missing and broken shout; the rest are quiet.
_DISPLAY = {
    "ok": "ok",
    "absent": "absent",
    "missing": "MISSING",
    "broken": "BROKEN",
    "warn": "warn",
    "unset": "unset",
}

_NOT_READY_HINT = (
    "(macOS: brew install pandoc mactex-no-gui poppler; "
    "Debian/Ubuntu: see the Dockerfile's package list)"
)


@dataclass(frozen=True)
class Finding:
    """One examined capability, as pure data.

    ``name`` is the identity used in the not-ready roll-call (a tool name,
    an environment key, ``python``, or ``python-deps``). ``category`` is
    one of ``tool``/``python``/``key``/``deps``; ``state`` is one of
    ``ok``/``absent``/``missing``/``broken``/``warn``/``unset``. ``detail``
    is the trailing purpose or message printed after the label, and
    ``required`` records whether the press declares this capability
    mandatory. The state, not the flag, decides the exit code (see
    ``_FAILING_STATES``); the flag is for consumers that gate specific
    actions on specific tools.
    """

    name: str
    category: str
    state: str
    detail: str
    required: bool


@dataclass(frozen=True)
class DoctorReport:
    """The whole examination as immutable data: the findings in report
    order, plus the derived verdict the CLI and the desk both read."""

    findings: tuple[Finding, ...]

    @property
    def failing(self) -> tuple[str, ...]:
        """The names of capabilities whose state denies the machine, in
        report order -- exactly the roll-call the CLI prints."""

        return tuple(f.name for f in self.findings if f.state in _FAILING_STATES)

    @property
    def ready(self) -> bool:
        return not self.failing

    @property
    def exit_code(self) -> int:
        return 0 if self.ready else 1


def tool_runs(tool: str) -> bool:
    try:
        for flag in ("--version", "-v"):
            if adapters.process_runner.run(
                [tool, flag], capture=True, timeout=15
            ).returncode == 0:
                return True
    except (OSError, subprocess.TimeoutExpired):
        return False
    return False


def _default_deps_probe() -> str | None:
    """Return ``None`` when the required Python libraries import, or the
    ImportError message when they do not. The one place doctor touches the
    interpreter's own dependencies."""

    try:
        from PIL import Image  # noqa: F401
        import pypdf  # noqa: F401
        import ruamel.yaml  # noqa: F401
    except ImportError as exc:
        return str(exc)
    return None


def examine(
    *,
    environment: adapters.Environment | None = None,
    runs: Callable[[str], bool] | None = None,
    python_version: tuple[int, int] | None = None,
    deps_probe: Callable[[], str | None] | None = None,
) -> DoctorReport:
    """Probe the machine and return immutable findings without printing.

    Every outward read goes through an injected boundary so a test can
    supply smart probes -- a fixed PATH, a scripted ``--version`` verdict,
    a pinned interpreter version, a canned dependency result -- and never
    touch a real executable, sleep on a timeout, or mutate PATH. Left
    unset, each argument falls back to the real adapter, so production
    routes PATH and process runs through ``press.adapters`` as required.
    """

    env = environment if environment is not None else adapters.environment
    tool_probe = runs if runs is not None else tool_runs
    version = (
        python_version
        if python_version is not None
        else (sys.version_info.major, sys.version_info.minor)
    )
    check_deps = deps_probe if deps_probe is not None else _default_deps_probe

    findings: list[Finding] = []

    for tool, purpose, required in CHECKS:
        if env.which(tool) is None:
            state = "missing" if required else "absent"
            findings.append(Finding(tool, "tool", state, purpose, required))
        elif not tool_probe(tool):
            findings.append(
                Finding(
                    tool,
                    "tool",
                    "broken",
                    f"present but cannot execute; {purpose}",
                    required,
                )
            )
        else:
            findings.append(Finding(tool, "tool", "ok", purpose, required))

    for key, purpose in KEYS:
        state = "ok" if env.get(key) else "unset"
        findings.append(Finding(key, "key", state, purpose, False))

    # The tested Python range; outside it the press may still run but is
    # unproven, so doctor says so rather than staying silent.
    version_str = f"{version[0]}.{version[1]}"
    if (3, 10) <= version <= (3, 14):
        findings.append(
            Finding(
                "python",
                "python",
                "ok",
                f"{version_str} is within the tested range 3.10 to 3.14",
                False,
            )
        )
    else:
        findings.append(
            Finding(
                "python",
                "python",
                "warn",
                f"{version_str} is outside the tested range 3.10 to 3.14 "
                "(see docs/COMPATIBILITY.md)",
                False,
            )
        )

    deps_error = check_deps()
    if deps_error is None:
        findings.append(
            Finding(
                "python-deps",
                "deps",
                "ok",
                "Pillow, pypdf, ruamel.yaml importable",
                True,
            )
        )
    else:
        findings.append(
            Finding("python-deps", "deps", "missing", deps_error, True)
        )

    return DoctorReport(tuple(findings))


def render_finding(finding: Finding) -> str:
    """The one line a finding prints. ``python`` and ``python-deps`` share
    the ``python`` label column; keys are wider than tools."""

    label = "python" if finding.category in ("python", "deps") else finding.name
    width = 16 if finding.category == "key" else 10
    display = _DISPLAY[finding.state]
    return f"  [{display:>7}] {label:<{width}} {finding.detail}"


def main() -> int:
    report = examine()
    print("press doctor")
    for finding in report.findings:
        print(render_finding(finding))
    if report.failing:
        print(f"\nnot ready: {', '.join(report.failing)} {_NOT_READY_HINT}")
    else:
        print("\nthis machine can make books")
    return report.exit_code
