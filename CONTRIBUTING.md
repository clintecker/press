# Contributing

The press accepts contributions that follow its laws (see
[the architecture guide](https://github.com/clintecker/press/blob/main/docs/ARCHITECTURE.md):
facts once, generators over checkers over conventions, artifacts verified
as objects, scars become law).

- Run `press doctor`, then `press selftest`, before and after your
  change; both must be green.
- Install the local gates once: `pip install -e '.[dev]'` then
  `pre-commit install`. Every commit then lints every checked-in
  format: ruff (with a cyclomatic-complexity ceiling of 15 for new
  code), mypy, shellcheck, yamllint, pymarkdown, TOML/JSON validity,
  and the selftest. CI runs the identical battery via
  `pre-commit run --all-files`, so the hook only saves you the round
  trip. The complexity ceiling is enforced with no current exceptions;
  do not introduce a `# noqa: C901`, decompose instead.
- Prove changes against a real book: scaffold one (`press new`) or use
  your own, and run `press all`. A green `pip install` is not a
  working pipeline.
- New CLI targets, artifacts, or config keys must land with their
  documentation in the same commit; the selftest enforces the parts it
  can reach mechanically.
- Design changes to rendered output of valid books are breaking
  changes and wait for a new major; say so in your PR.
- CI runs the selftest and the integration gate (wheel build, clean
  scaffold, full gauntlet, tamper test) on every PR. Toolchain PRs
  additionally build and smoke the image without publishing.

## One command to verify

From a clean checkout with `pip install -e '.[dev]'`, run the whole local
proof, fast layers first:

```sh
scripts/verify.sh          # lint + type + selftest + pytest, then the
                           # coverage and mutation ratchets and the site build
scripts/verify.sh --quick  # stop after the fast lint/type/test layer
scripts/verify.sh --full   # also run CI's container gauntlet locally (Docker)
```

CI calls these same tools. `--full` additionally runs the integration gauntlet
in the pinned toolchain image (`scripts/gauntlet.sh`) — build the wheel,
scaffold a stranger's book, run the whole `press all`, and prove tampering
turns the verifier red — so the container tier where rendered-artifact bugs
surface is proven before you push, not on the CI round-trip. It runs natively
on Apple Silicon since the toolchain image went multi-arch (needs Docker).
Only the live second-party proofs (a fork-PR from another account, a private
book in another org) stay CI/human-only. Do not run
`scripts/coverage_ratchet.py --update`: it re-measures on your machine and
can push the committed baselines above the floor CI enforces.

## What a proof has to prove

Coverage measures that a line *ran*, not that its output was *right*. A branch
can execute under an integration test whose only assertion is "it built" — and
ship a wrong result. That is exactly how a title-page generator shipped a
dropped and a clipped cover at 11.5% coverage: the lines ran, the artifact was
never inspected.

So the bar is the artifact, not the line count:

- **Assert what the code produces, not that it ran.** A test for output-making
  code checks a property of the output (the cover is on page 1; the spine width
  equals the computed value), not merely that the function returned.
- **A producer is only proven by a verifier that rejects a broken artifact.**
  Every module classified `producer` in `quality/surfaces.yaml` must name that
  rejection in `PRODUCER_REJECTION_PROOFS` (or sit, visibly, on the shrinking
  pending list); the selftest enforces it. Add a producer, and you add the
  known-bad case its verifier turns red on.
- **A verifier with no known-bad fixture is an untested claim.** Prove a check
  by feeding it something that must fail, not only something that passes.
- **A low coverage floor is a decision on the record.** Below 50% a module must
  give its reason in `LOW_FLOOR_ALLOWED`; the floor is not a place for silence.

## Filing and proposing

Open issues through the [issue forms](https://github.com/clintecker/press/issues/new/choose)
(defect, proposal, documentation); a defect asks for `press doctor`,
`press selftest`, the version, and a minimal reproduction. Report security
vulnerabilities privately per
[the security policy](https://github.com/clintecker/press/blob/main/SECURITY.md),
never as a public issue. Pull requests follow the template: a test that
fails before and passes after, regenerated projections, and the
compatibility impact.

This project has one maintainer; how decisions, releases, and conduct are
handled is in
[the governance doc](https://github.com/clintecker/press/blob/main/GOVERNANCE.md),
and participation is under the
[Code of Conduct](https://github.com/clintecker/press/blob/main/CODE_OF_CONDUCT.md).
