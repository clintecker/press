"""Security-control canaries: known-bad fixtures the press's own in-tree
detectors must REJECT, each paired with a clean case they must PASS
(fail-before / pass-after). House law: a checker is only real with a
known-bad fixture it rejects.

Scope, recorded honestly (see SECURITY.md > Canaries):

- The action-pinning gate (canary in ``test_ci_posture.py``) and the
  published-output secret scan (below) are the press's OWN in-tree controls.
  These canaries prove they fire against a known-bad and stay quiet on a
  clean case.
- GitHub secret scanning / push protection and dependency-review
  live-firing are PLATFORM-side detectors. They cannot be seeded here
  without a real credential or a real CVE -- and a real committed secret
  would trip push protection, a real vulnerable dependency would poison the
  lockfile -- so their live firing is proven by the platform on real events,
  not seeded in this repository. The dependency-review canary proves the
  CONFIG is present and armed; the action proves the live firing on a real
  pull request.

Every fixture value that looks like a credential is an obviously-fake dummy
that matches a marker's shape without being any real key, so committing this
file trips no platform detector.
"""

from __future__ import annotations

from pathlib import Path

from press import commerce, yamlio

ROOT = Path(__file__).resolve().parent.parent


# ---- detector-behavior / secret canary -------------------------------------
# The press's published-output secret scan (verify_pages, over every rendered
# page) is exactly commerce._SECRET_MARKERS. These prove it fires on a
# synthetic credential and stays quiet on ordinary page text.


def test_secret_scan_rejects_a_synthetic_credential():
    """A known-bad: text shaped like a leaked credential must be FLAGGED by
    the published-output secret scan. The scanner keys on a credential SHAPE --
    a key with a value, a bearer token, a credential query param -- not a bare
    English word, so a book titled "Secrets of the Trade" is not a leak (that
    tightening is its own test). The fixtures use obvious EXAMPLE placeholders
    with no real entropy, so they exercise the scanner without embedding
    anything a platform detector (or GitHub push protection) would flag."""

    dummy = "config: api_key=EXAMPLE0000NOTREAL; Authorization: Bearer EXAMPLE0000NOTATOKEN"
    assert commerce._SECRET_MARKERS.search(dummy), (
        "secret scan failed to flag credential-shaped text"
    )
    assert commerce._SECRET_MARKERS.search("https://x.test/cb?token=EXAMPLE00000"), (
        "secret scan failed to flag a url carrying a token query param"
    )


def test_secret_scan_passes_clean_output():
    """Fail-before / pass-after: ordinary rendered page text -- a storefront
    URL, a seller name, prose -- must NOT be flagged, or the scan would be
    noise that publishers learn to ignore."""

    clean = (
        "Order a print copy from https://example.test/book. "
        "Sold by Example Press. Returns accepted within 30 days."
    )
    assert commerce._SECRET_MARKERS.search(clean) is None


# ---- vulnerable-dependency canary ------------------------------------------
# Dependency review is a GitHub action that fires on pull requests; it cannot
# be made to fire locally without a real vulnerable dependency (which would
# poison the lockfile). So the canary proves the CONFIG is armed. Live firing
# is proven by the action itself on a real PR, not seedable here without a
# real CVE.


def _dependency_review_severity(workflow_text: str) -> str | None:
    """The ``fail-on-severity`` the dependency-review action is armed with in
    a workflow, or None when the action is absent or unarmed. Pure over the
    workflow text so a canary can feed it a disarmed known-bad snippet."""

    data = yamlio.loads(workflow_text)
    for job in (data.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            if "dependency-review-action" in (step.get("uses") or ""):
                return (step.get("with") or {}).get("fail-on-severity")
    return None


def test_dependency_review_is_armed_to_fail_on_high_severity():
    """The shipped config is armed: dependency-review.yml exists and fails a
    pull request on a high-severity vulnerable dependency addition."""

    wf = ROOT / ".github" / "workflows" / "dependency-review.yml"
    assert wf.is_file(), "dependency-review.yml is missing"
    assert _dependency_review_severity(wf.read_text(encoding="utf-8")) == "high", (
        "dependency review is not armed to fail on high-severity vulns"
    )


def test_dependency_review_canary_flags_a_disarmed_config():
    """Fail-before / pass-after: a workflow whose dependency-review step drops
    ``fail-on-severity`` reads as unarmed (None), while the armed shape reads
    as ``high`` -- so a silent disarming of the gate is caught."""

    disarmed = (
        "on:\n"
        "  pull_request:\n"
        "    branches: [main]\n"
        "jobs:\n"
        "  review:\n"
        "    runs-on: ubuntu-24.04\n"
        "    steps:\n"
        "      - uses: actions/dependency-review-action@abc123 # v5\n"
    )
    armed = disarmed + ("        with:\n          fail-on-severity: high\n")
    assert _dependency_review_severity(disarmed) is None
    assert _dependency_review_severity(armed) == "high"
