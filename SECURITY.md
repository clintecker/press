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
- **Secret hygiene.** Secret scanning, push protection, non-provider
  patterns, and validity checks are enabled, so a committed credential
  is rejected at push time where the platform supports it.
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

### Accepted limitations

- The toggle drift-check needs `SECURITY_AUDIT_TOKEN` because GitHub
  exposes `security_and_analysis` only to admin credentials; the default
  workflow token cannot read it. That token is repository-scoped and
  read-only.
- Repository-wide enforcement that every workflow action is pinned to a
  full-length commit SHA is a ruleset control still tracked in #153. Every
  action is already SHA-pinned in source and reviewed on change by
  dependency review; the outstanding item is repository-level
  *enforcement*, not the current state.
- Requiring the trust checks to pass on a pull request before a merge to
  `main` (the branch ruleset's merge gate) is deferred by choice: `main` is
  hardened against force-push and deletion, but direct pushes remain allowed
  for now, so the gates run on push rather than blocking a merge. Also
  tracked in #153.
