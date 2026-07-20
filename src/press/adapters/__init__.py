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
    UrllibImageClient,
    environment,
    image_client,
    process_runner,
)
from .protocols import (
    Environment,
    HttpImageClient,
    ProcessResult,
    ProcessRunner,
    RetrySource,
)
from .retry import RetryBudget, resolve

__all__ = [
    # protocols
    "ProcessRunner",
    "ProcessResult",
    "Environment",
    "HttpImageClient",
    "RetrySource",
    # production adapters + singletons
    "SubprocessRunner",
    "OsEnvironment",
    "UrllibImageClient",
    "HttpError",
    "process_runner",
    "environment",
    "image_client",
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
