# Security

Report vulnerabilities privately to [clint@lgtm.systems](mailto:clint@lgtm.systems); expect an
acknowledgement within a week. Do not open public issues for
exploitable defects.

Relevant guarantees the press intends to keep (breakage of any is a
vulnerability): source archives never dereference symlinks and refuse
secret-prone files; every generated output stays beneath the book
root under a validated slug; CI outputs cannot be injected through
book metadata; published sites carry only local, resolving
references; three-part release tags are immutable across pipeline,
action, and toolchain.

## Repository security controls

The controls below form the supported baseline for this public
project. The source-versioned ones are visible in the tree; the
platform toggles are read back by a scheduled drift-check so none can
be turned off unnoticed.

- **Dependency provenance.** `.github/dependabot.yml` watches the
  Python package, the pinned GitHub Actions, and the toolchain base
  image (weekly, grouped, bounded). Dependabot security updates and
  vulnerability alerts are enabled, so a known-vulnerable dependency
  is flagged out of band.
- **Static analysis.** `.github/workflows/codeql.yml` runs CodeQL over
  the Python package on every pull request, every push to `main`, and
  weekly, at least privilege (it writes only security events).
- **Dependency review.** `.github/workflows/dependency-review.yml`
  fails a pull request that adds a high-severity vulnerable dependency
  before it can merge.
- **Secret hygiene.** Secret scanning and push protection are enabled, so
  a committed credential is rejected at push time. Non-provider pattern
  scanning and secret validity checks are Advanced Security sub-features;
  GHAS is not provisioned on this public repository, so they remain off by
  platform limitation, not by choice (recorded below).
- **Protection rulesets.** `main` cannot be force-pushed or deleted, and
  the three-part release tags (`v*.*.*`) are immutable -- they cannot be
  moved or deleted -- so the trust graph a pinned book resolves cannot be
  rewritten under it. Pages deploys only from `main`, through the
  documentation workflow. These are repository rulesets, applied on the
  platform rather than in the tree.
- **Drift detection.** `.github/workflows/security-controls.yml` runs
  weekly and on demand: it asserts the source-versioned controls are
  present, reads the admin-only `security_and_analysis` toggles back
  through a repository-scoped fine-grained token (`SECURITY_AUDIT_TOKEN`,
  Administration: read), and reads the branch and tag protection rulesets
  back, failing loudly if either is removed or weakened.

### Canaries

Each control the press owns in the tree carries a known-bad fixture it
rejects, paired with a clean case it passes (fail-before / pass-after);
house law is that a checker is only real with a known-bad it rejects.

- **Proven in-tree.** The action-pinning gate
  (`tests/test_ci_posture.py::test_unpinned_action_canary`) is fed a
  floating-tag snippet (`uses: actions/checkout@v4`) and must flag it while
  a SHA-pinned snippet passes. The published-output secret scan
  (`tests/test_security_canaries.py`) is fed a synthetic, obviously-fake
  credential and must flag it while ordinary page text passes. Both use
  string fixtures, so no real unpinned action or real secret is ever
  committed.
- **Platform-side, not seedable here.** GitHub secret scanning / push
  protection and dependency-review *live firing* are platform detectors:
  seeding them would require a real credential (which push protection would
  reject) or a real vulnerable dependency (which would poison the lockfile).
  Their live firing is proven by the platform on real pull requests and
  pushes, not by a seeded fixture. The dependency-review canary instead
  proves the *config* is present and armed to fail a PR on a high-severity
  vulnerable dependency; the action proves the firing on a real PR.

### Accepted limitations

- The toggle drift-check needs `SECURITY_AUDIT_TOKEN` because GitHub
  exposes `security_and_analysis` only to admin credentials; the default
  workflow token cannot read it. That token is repository-scoped and
  read-only.
- Non-provider secret patterns and secret validity checks require GitHub
  Advanced Security, which is not available on this public repository
  (`advanced_security` is null, and a PATCH to enable them silently
  no-ops). They are a platform limitation, not drift: the
  `security-controls` check treats them as the documented baseline and
  will demand they be enabled the moment Advanced Security becomes
  available. Secret scanning and push protection -- the controls that
  reject a committed credential at push time -- are on.
- GitHub offers no repository-level control that enforces "every workflow
  action is pinned to a full commit SHA"; there is no such ruleset rule.
  Enforcement therefore lives in the tree:
  `tests/test_ci_posture.py::test_every_action_is_pinned_by_full_commit_sha`
  fails CI on any action not pinned to a 40-hex commit SHA, across every
  workflow file. The control is real and enforced -- in-repo rather than
  platform-side. This is the recorded resolution of the #153/#154 SHA-pin
  item.
- Requiring the trust checks to pass on a pull request before a merge to
  `main` (the branch ruleset's merge gate) is deferred by choice: `main` is
  hardened against force-push and deletion, but direct pushes remain allowed
  for now, so the gates run on push rather than blocking a merge. Also
  tracked in #153.
