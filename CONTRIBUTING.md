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
  trip. Functions above the complexity ceiling carry `# noqa: C901`
  as a tracked inventory, not a license; do not add new ones.
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
```

CI calls these same tools. What `verify.sh` cannot run locally — the
integration gauntlet inside the toolchain container, the consumer proof, and
the live second-party proofs — runs on push and on a release tag. Do not run
`scripts/coverage_ratchet.py --update`: it re-measures on your machine and
can push the committed baselines above the floor CI enforces.

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
