"""The domain result and exception vocabulary.

These types let a caller assert on a contract (this check failed, this
receipt names this output) instead of scraping printed lines. The tests
pin the invariants the rest of the trust program will lean on: a report
cannot claim success while carrying a failure, a receipt is immutable
evidence, and every domain error is a ``PressError`` distinct from
``SystemExit``.
"""

from __future__ import annotations

from press import results
from press.results import (
    ArtifactError,
    BuildReceipt,
    CheckResult,
    ConfigError,
    PolicyError,
    PressError,
    ToolError,
    VerificationReport,
)


# --------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------


def test_domain_exceptions_are_press_errors_and_not_systemexit():
    for exc_type in (ConfigError, PolicyError, ToolError, ArtifactError):
        instance = exc_type("boom")
        assert isinstance(instance, PressError)
        assert not isinstance(instance, SystemExit)


def test_tool_error_carries_source_code_and_detail():
    err = ToolError("api refused", source="api.openai.com", code=429, detail="slow down")
    assert err.source == "api.openai.com"
    assert err.code == 429
    assert err.detail == "slow down"
    assert str(err) == "api refused"


def test_tool_error_defaults_are_empty_not_none_source():
    err = ToolError("plain")
    assert err.source == ""
    assert err.code is None
    assert err.detail == ""


# --------------------------------------------------------------------------
# CheckResult
# --------------------------------------------------------------------------


def test_check_result_passed_and_failing_constructors():
    ok = CheckResult.passed("witnesses")
    assert ok.ok is True
    assert ok.failed is False
    assert ok.findings == ()

    bad = CheckResult.failing("witnesses", ["missing title", "no manuscript line"])
    assert bad.ok is False
    assert bad.failed is True
    assert bad.findings == ("missing title", "no manuscript line")


def test_check_result_is_frozen():
    ok = CheckResult.passed("x")
    try:
        ok.ok = False  # type: ignore[misc]
    except Exception as exc:  # dataclasses raises FrozenInstanceError
        assert "frozen" in type(exc).__name__.lower() or isinstance(exc, AttributeError)
    else:  # pragma: no cover - frozen dataclass must refuse
        raise AssertionError("CheckResult should be immutable")


# --------------------------------------------------------------------------
# BuildReceipt
# --------------------------------------------------------------------------


def test_build_receipt_accumulates_commands_and_outputs_immutably():
    receipt = BuildReceipt(target="pdf")
    assert receipt.commands == ()
    assert receipt.outputs == ()

    with_cmd = receipt.with_command(["pandoc", "in.md", "-o", "out.pdf"])
    with_out = with_cmd.with_output("dist/book.pdf")

    # original is untouched (immutable, builder-style)
    assert receipt.commands == ()
    assert with_cmd.commands == (("pandoc", "in.md", "-o", "out.pdf"),)
    assert with_out.outputs == ("dist/book.pdf",)
    assert with_out.target == "pdf"


# --------------------------------------------------------------------------
# VerificationReport
# --------------------------------------------------------------------------


def test_verification_report_ok_iff_every_check_passed():
    report = VerificationReport(artifact="book.pdf")
    assert report.ok is True  # vacuously, no failures

    report = report.with_check(CheckResult.passed("ink"))
    assert report.ok is True

    report = report.with_check(CheckResult.failing("links", ["dead anchor"]))
    assert report.ok is False
    assert len(report.failures) == 1
    assert report.failures[0].check == "links"


def test_verification_report_cannot_claim_success_with_a_failure():
    report = VerificationReport(
        artifact="site",
        checks=(CheckResult.passed("a"), CheckResult.failing("b", ["x"])),
    )
    assert report.ok is False


def test_module_exposes_the_vocabulary():
    for name in (
        "BuildReceipt", "VerificationReport", "CheckResult",
        "ConfigError", "PolicyError", "ToolError", "ArtifactError",
    ):
        assert hasattr(results, name)
