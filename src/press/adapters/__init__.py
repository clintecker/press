"""The boundary adapters: typed seams between the press and the outside.

Import the Protocols to depend on a boundary; the production singletons in
``production`` to run for real; the fakes in ``fakes`` to test. This is the
one approved home for direct ``subprocess``/``os.environ``/``urllib`` calls
-- ``tests/test_adapters_boundary.py`` proves nothing else grows new ones.
"""

from __future__ import annotations

from ..results import (
    ArtifactError,
    BuildReceipt,
    CheckResult,
    ConfigError,
    PolicyError,
    PressError,
    ToolError,
    VerificationReport,
)
from .production import (
    HttpError,
    OsEnvironment,
    SubprocessRunner,
    SystemClock,
    UrllibImageClient,
    clock,
    environment,
    image_client,
    process_runner,
)
from .protocols import (
    Clock,
    Environment,
    HttpImageClient,
    OutputChannel,
    ProcessResult,
    ProcessRunner,
    RetrySource,
    Spawn,
    SpawnedProcess,
)
from .retry import RetryBudget, resolve
from .streaming import default_spawn

__all__ = [
    # protocols
    "ProcessRunner",
    "ProcessResult",
    "Environment",
    "HttpImageClient",
    "RetrySource",
    "OutputChannel",
    "SpawnedProcess",
    "Spawn",
    "Clock",
    # production adapters + singletons
    "SubprocessRunner",
    "OsEnvironment",
    "UrllibImageClient",
    "SystemClock",
    "HttpError",
    "process_runner",
    "environment",
    "image_client",
    "clock",
    "default_spawn",
    # retry
    "RetryBudget",
    "resolve",
    # results + exceptions (re-exported for convenience)
    "BuildReceipt",
    "VerificationReport",
    "CheckResult",
    "PressError",
    "ConfigError",
    "PolicyError",
    "ToolError",
    "ArtifactError",
]
