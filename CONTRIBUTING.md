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
