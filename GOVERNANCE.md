# Governance

The press is a single-maintainer project. This document says plainly who
decides what, so a contributor knows how a change lands and what to expect,
without pretending a community structure that does not exist.

## Who maintains it

Clint Ecker (<clint@lgtm.systems>), on behalf of LGTM Systems, LLC. Books
produced with the press appear under the LGTM Publishing imprint. There is
one maintainer; there is no committee.

## Authority

- **Decisions and merges.** The maintainer reviews and merges every change.
  A proposal is judged against the project's laws (facts stated once,
  generators over checkers, artifacts verified as objects) and the
  compatibility contract, not by vote.
- **Releases.** Only the maintainer cuts a release, through
  `scripts/release.sh`; a tag is published only after its release contract
  proves green. See [the architecture guide](docs/ARCHITECTURE.md) for the
  versioning contract.
- **Security.** Vulnerability reports go to the private channel in
  [SECURITY.md](SECURITY.md); the maintainer triages and coordinates fixes.
- **Package and infrastructure.** The maintainer controls the GitHub
  repository, the `ghcr.io/clintecker/press-toolchain` image, the
  documentation site and its domain, the release tags, and the security and
  conduct contacts.

## Conduct

Conduct concerns are handled under [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md),
through a channel (conduct@lgtm.systems) separate from security reporting.

## Bus factor and succession

This is a one-person project, and that is an honest risk. It is mitigated,
not eliminated:

- The pipeline and its contracts are in the repository, under MIT; anyone may
  fork and continue it.
- The release process is a documented, resumable script, not tribal
  knowledge.
- Should the maintainer become unavailable, control of the GitHub
  organization, the toolchain package, the domain, and the release-signing
  and security contacts would pass according to LGTM Systems, LLC's business
  continuity arrangements. A successor maintainer would be announced in this
  file and the README.

## Changing this document

Governance changes are made by pull request and are visible in the
repository's history like any other change.
