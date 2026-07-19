# Extracting a general accumulated-trust framework from press

Status: exploration and extraction notebook, not a roadmap commitment.

This document records the domain-neutral software-production machinery that may
eventually be extracted from press into a reusable Python framework. It is
deliberately written before extraction begins so that later work can distinguish
the useful abstraction from the publishing domain that discovered it.

Press remains the proving ground. The framework should be extracted only after
its contracts have survived real use across the trust-foundation, adversarial
artifact, and accumulated-delivery milestones. This note is a place to preserve
ideas, candidate interfaces, invariants, sequencing, and unresolved questions;
it does not authorize a premature package split.

## Thesis

The reusable idea underneath press is not “a build system for books.” It is:

> Declare what a software system produces, what invariants each product must
> satisfy, what evidence proves those invariants, and prevent a higher-level
> workflow or release from claiming more trust than its accumulated evidence
> supports.

That can become a general Python software-production framework for packaged
libraries, CLIs, services, generated clients, containers, documentation sites,
deployment bundles, and other artifact-producing repositories.

The distinctive value would be **claim discipline** rather than task execution.
Existing builders, test runners, linters, type checkers, package backends,
container tools, and CI systems should remain responsible for doing their jobs.
The extracted framework would describe the claims a repository makes, invoke or
observe the relevant tools through typed boundaries, inspect produced objects,
bind evidence to exact identities, and refuse unsupported release claims.

## The accumulated-trust model

Trust accumulates through layers:

```text
L0  inventory and traceability
 ↓
L1  pure functions, policies, parsers, and properties
 ↓
L2  components, adapters, and active-signal contracts
 ↓
L3  damaged objects and verifier-negative proofs
 ↓
L4  compositions, state transitions, concurrency, and scenarios
 ↓
L5  real tools and sandbox integrations
 ↓
L6  clean installed distributions and production-shaped runtime
 ↓
L7  independent consumers, external boundaries, and release identity
```

A higher layer consumes the evidence below it. It does not erase a missing
proof. An end-to-end test cannot compensate for an untested pure policy; a green
source checkout cannot prove an installed wheel; a green release workflow
cannot prove that its wheel, container, or assets are the objects that passed
earlier gates.

The framework should make three states explicit:

- **proven** — the applicable invariant has current evidence bound to the exact
  object and environment in question;
- **violated** — an active proof demonstrated a counterexample;
- **unproven** — evidence is missing, stale, inapplicable, or cannot be bound to
  the object.

“Unproven” must never be projected as green.

## What exists in press today

### Artifact graph

[`src/press/registry.py`](https://github.com/clintecker/press/blob/main/src/press/registry.py)
states artifact names, outputs, prerequisites, publication roles, optionality,
dependency ordering, and cycle detection once. CLI format lists, build order,
downloads, and documentation derive from it.

The current registry is small and publishing-specific at its execution edge,
but its central law is general:

> A product and every prerequisite needed to create it are declared in one
> graph, and downstream surfaces project from that graph rather than restating
> product names.

### Executable invariant ledger

[`quality/invariants.yaml`](https://github.com/clintecker/press/blob/main/quality/invariants.yaml)
and its generated
[`docs/INVARIANTS.md`](https://github.com/clintecker/press/blob/main/docs/INVARIANTS.md)
are the first concrete form of the reusable invariant ledger. The ledger binds
human claims to real enforcers, negative proofs, layers, and honest limitations.
Its validator rejects references that no longer resolve.

This is more important than any particular verifier. A reusable framework can
make the invariant ledger a first-class extension surface rather than a
press-specific YAML convention.

### Reusable tests and selftest compatibility

The pytest foundation from
[#78](https://github.com/clintecker/press/issues/78) has begun moving the
monolithic selftest into reusable tests while retaining the public `press
selftest` contract. This is the right migration pattern for extraction:
separate reusable assertions and fixtures from a stable domain-facing command,
then let the old command become a projection over the new machinery.

### Tests of the checkers

[`src/press/check_the_checkers.py`](https://github.com/clintecker/press/blob/main/src/press/check_the_checkers.py)
requires each known-bad fixture to fail for its declared diagnostic, reports
extra diagnostics, and requires known-good fixtures to pass. “Some checker
rejected it” is not treated as proof that the intended rule survives.

This yields a general law:

> A negative fixture must violate the named invariant for the named reason, and
> a known-good witness must remain accepted.

### Artifact-object verification

The `verify_*` modules inspect the objects that users receive: rendered PDF
pages, EPUB structure, extracted text, archive members and bytes, website links,
cover geometry, and other format-specific facts. Builders do not certify their
own output merely by exiting zero.

The general law is:

> Build success proves that a process completed. Artifact verification proves
> that the resulting object has the promised properties.

### Publication boundary policy

[`src/press/package_source.py`](https://github.com/clintecker/press/blob/main/src/press/package_source.py)
uses tracked files as the publication allowlist, refuses secret-prone content,
never dereferences symlinks, proves path containment, distinguishes dangerous
files from junk, and emits an auditable exclusion summary. The archive writer
and archive verifier consume the same policy.

This could apply to source distributions, documentation deployments, Lambda
bundles, model packages, container contexts, and release attachments.

### Authoritative registries and checked projections

[`scripts/sync_roadmap.py`](https://github.com/clintecker/press/blob/main/scripts/sync_roadmap.py)
defines a checked-in source of record, a generated human projection, and a
mutable GitHub projection with detectable drift. The direction of authority is
explicit.

The same pattern could govern:

- CLI reference documentation;
- package metadata;
- supported-version matrices;
- deployment environment declarations;
- issue and milestone taxonomies;
- alert and runbook catalogs;
- configuration references;
- public compatibility statements.

### Environment diagnosis

[`src/press/doctor.py`](https://github.com/clintecker/press/blob/main/src/press/doctor.py)
names required and optional capabilities and explains the consequence of their
absence. The current implementation renders directly to the terminal, but the
planned typed findings in
[#103](https://github.com/clintecker/press/issues/103) are a reusable model:
probe deterministically, return structured findings, and let CLI, TUI, CI, and
support output project from the same facts.

## Machinery planned inside press before extraction

The following work should mature in press first:

- [collection-time invariant and proof enforcement #80](https://github.com/clintecker/press/issues/80);
- [public callable classification #81](https://github.com/clintecker/press/issues/81);
- [typed deterministic boundary adapters #82](https://github.com/clintecker/press/issues/82);
- [composable book and artifact factories #83](https://github.com/clintecker/press/issues/83);
- [fixture provenance manifests #84](https://github.com/clintecker/press/issues/84);
- [property-based proofs #85](https://github.com/clintecker/press/issues/85);
- [bounded replayable fuzzing #86](https://github.com/clintecker/press/issues/86);
- [artifact damage operators #88](https://github.com/clintecker/press/issues/88);
- [build–mutate–verify state models #89](https://github.com/clintecker/press/issues/89);
- [pairwise and named high-risk scenarios #90](https://github.com/clintecker/press/issues/90);
- [real-tool artifact runners #91](https://github.com/clintecker/press/issues/91);
- [design-major visual regression #92](https://github.com/clintecker/press/issues/92);
- [chained trust receipts #93](https://github.com/clintecker/press/issues/93);
- [evidence-ordered CI #94](https://github.com/clintecker/press/issues/94);
- [mutation and sabotage ratchets #95](https://github.com/clintecker/press/issues/95);
- [invariant-aware test impact #96](https://github.com/clintecker/press/issues/96);
- [release identity gate #97](https://github.com/clintecker/press/issues/97).

These issue descriptions are design inputs, not evidence that the abstractions
have already stabilized.

## Candidate framework boundary

The framework kernel should own only domain-neutral concepts:

```text
trustforge-core/
├── artifacts       # declarations, dependency graph, identities
├── invariants      # claims, applicability, severity, limitations
├── proofs          # proof declarations, results, diagnostics
├── receipts        # canonical evidence and predecessor chains
├── policy          # pure applicability and capability decisions
├── execution       # injected boundary protocols and active outcomes
├── fixtures        # provenance and expected-diagnostic contracts
├── damage          # artifact mutation protocols and results
├── projection      # render/reconcile contracts and drift
└── serialization   # versioned canonical schemas

pytest-trustforge/   # collection gates, markers, properties, state models
trustforge-python/   # wheel, sdist, entry-point, import, metadata proofs
trustforge-github/   # Actions evidence and GitHub projections
trustforge-container/# image, labels, SBOM, provenance proofs
trustforge-cli/      # graph, verify, explain, doctor, receipt commands
```

`trustforge` is a working name only. Naming should wait until the extracted
contract and audience are clear.

Press would depend on the kernel and supply a publishing plugin containing book
models, Pandoc/TeX builders, PDF/EPUB/site verifiers, print geometry, editorial
law, and book-specific fixtures.

## Candidate core model

### Artifact

An artifact is a named product with prerequisites, outputs, applicability,
identity, builders, verifiers, and publication policy.

```python
Artifact(
    id="python.wheel",
    requires=("source.tree", "tests.fast"),
    produces=(Glob("dist/*.whl"),),
    build=CommandBoundary(("python", "-m", "build", "--wheel")),
    identity=Sha256Files(),
    verifiers=(WheelMetadata(), CleanInstall(), PublicImportSurface()),
    publish=True,
)
```

The declaration should not assume that every build is a subprocess. Builders
and verifiers are injected protocols returning typed outcomes.

### Invariant

An invariant is a stable, human-meaningful claim with applicability, required
proof layers, enforcement references, severity, and an honest limitation.

```python
Invariant(
    id="release.clean-install",
    statement="The wheel operates without a source checkout",
    applies_to=("python.wheel", "release"),
    required_layers=("L2", "L6"),
    enforcers=("trustforge_python.clean_install",),
    negative_proofs=("wheel_missing_package_data",),
    severity="release-blocking",
    limitation="Does not prove optional extras not selected by the matrix",
)
```

Invariant IDs are public compatibility surfaces. Renaming or splitting one
requires a migration, not an untracked string edit.

### Proof declaration and result

A proof declaration states what it can establish and what active signal counts.
A proof result records what actually happened.

```python
Proof(
    id="wheel.clean-install.cli",
    establishes=("release.clean-install",),
    layer="L6",
    subject="python.wheel",
    runner=InstalledCliScenario(),
)

ProofResult(
    proof_id="wheel.clean-install.cli",
    verdict="proven",
    subject_digest="sha256:...",
    diagnostics=(),
    evidence=(EvidenceRef("stdout", "sha256:..."),),
)
```

Proofs should assert active signals: return values, typed exceptions, emitted
events, durable transitions, artifact bytes, and exact external requests.
Private-call observation alone is not proof of behavior.

### Receipt

A receipt binds proof results to exact identities and predecessor evidence.

```python
Receipt(
    schema_version=1,
    stage="installed-wheel",
    subject={"kind": "wheel", "digest": "sha256:..."},
    source_commit="...",
    environment={"python": "3.13.2", "platform": "linux-x86_64"},
    tool_identities={"pytest": "8.x", "ruff": "..."},
    applicable_invariants=(...),
    results=(...),
    predecessors=(ReceiptRef("sha256:..."),),
    omissions=(...),
)
```

Canonical serialization is mandatory. Receipt identity should change when any
claim, subject, environment, proof result, predecessor, or omission changes.
Signing and external transparency may be added later; stable canonical content
must come first.

### Diagnostic

Diagnostics are typed active signals, not prose-only log fragments:

```python
Diagnostic(
    code="artifact.output.missing",
    severity="error",
    subject="python.wheel",
    message="Declared output dist/example.whl was not produced",
    evidence=(...),
    remediation="Inspect the build backend package-data configuration",
)
```

Codes should be stable, messages useful, and attached data serializable and
redactable. CLI and CI annotations project from the same diagnostic.

### Capability and finding

Environment readiness should be modeled without performing domain work:

```python
Capability(
    id="tool.git",
    required_for=("source.identity", "release"),
    required=True,
    probe=ExecutableProbe(("git", "--version")),
)

Finding(
    capability="tool.git",
    state="available",       # available | missing | broken | unknown
    consequence=(...),
    evidence=(...),
)
```

No clock, process, filesystem, network, environment variable, or random value
should be read implicitly by pure policy code.

### Fixture provenance

```python
FixtureManifest(
    id="wheel.missing-package-data",
    kind="known-bad",
    source="production-regression",
    introduced_by="issue-123",
    violates=("release.clean-install",),
    expected_diagnostics=("wheel.package_data.missing",),
    minimized_from="sha256:...",
    bytes_digest="sha256:...",
)
```

Every checked-in regression fixture should answer: where did it come from, what
does it violate, which diagnostic must fire, which version introduced it, and
whether its bytes still match its manifest?

### Damage operator

```python
Damage(
    id="wheel.drop-entry-point",
    applies_to="python.wheel",
    violates=("cli.entry-point-present",),
    mutate=DropWheelMember("*.dist-info/entry_points.txt"),
)
```

A damage test succeeds only when the named verifier actively refuses the
mutated object for the expected reason. It should also prove the undamaged
control object passes.

### Projection

```python
Projection(
    id="supported-python-docs",
    source=Registry("quality/support.yaml"),
    targets=(MarkdownRegion("docs/SUPPORT.md"), GithubActionsMatrix(...)),
    render=render_support,
    compare=byte_exact,
)
```

Remote projections use adapters with `read`, `diff`, and explicit `apply`.
Ordinary checks should be network-free when possible; a remote drift job may
compare separately.

## Framework invariants

The extracted framework should enforce its own laws:

1. Every published artifact has at least one independent verifier.
2. Every declared output has exactly one owning artifact.
3. Artifact prerequisites are acyclic and applicability is deterministic.
4. Every invariant has a stable ID, statement, applicability, limitation, and
   required proof obligation.
5. Every invariant reference resolves to a real enforcer and proof.
6. Every release-blocking invariant has current evidence at every required
   layer.
7. Every public callable is classified by purity, side effects, boundaries,
   failure signals, and proof obligation.
8. Every negative fixture names the invariant and diagnostic it expects.
9. Every known-good fixture remains accepted by the same verifier surface.
10. Every external dependency is behind an injected typed adapter.
11. Wall-clock time, randomness, UUIDs, subprocesses, storage, and networks are
    injectable; tests do not sleep.
12. A timeout or interrupted external request is an unknown outcome, not an
    assumed failure.
13. Every fuzz failure is seeded, replayable, minimized, and promotable to a
    regression fixture.
14. Every higher-layer receipt consumes the required predecessor evidence.
15. Missing or stale evidence is `unproven`, never green.
16. Every receipt binds the exact subject bytes, environment, tools, results,
    omissions, and predecessor digests.
17. Every generated or remote projection declares exactly one source of record.
18. Every projection has a drift check; mutation requires an explicit apply
    operation.
19. The installed distribution, not the source checkout, is authoritative for
    package completeness.
20. A release binds source commit, distributions, runtime/container, published
    artifacts, external configuration identity where applicable, and the full
    receipt chain.

## Pytest integration

The pytest plugin is likely the first useful external surface because Python
projects already organize executable proofs there.

Candidate markers:

```python
@pytest.mark.proof(
    id="wheel.clean-install.cli",
    invariants=("release.clean-install",),
    layer="L6",
    subject="python.wheel",
)
def test_installed_cli(installed_wheel): ...

@pytest.mark.known_bad(
    fixture="wheel.missing-package-data",
    expect="wheel.package_data.missing",
)
def test_missing_package_data_is_refused(case): ...
```

Collection-time gates should detect:

- invariant without the required proof layers;
- proof marker naming an unknown invariant, artifact, fixture, or layer;
- duplicate proof IDs;
- public callable lacking a classification;
- stale/deleted enforcer or fixture paths;
- known-bad fixture without an expected diagnostic;
- known-good fixture without an associated verifier surface;
- test selection that omits a required proof for the requested receipt stage.

The plugin should emit a proof manifest before execution and a receipt fragment
after execution. It should not reinterpret pytest pass/fail as the entire trust
model: skips, xfails, collection errors, deselection, environment mismatch, and
missing fixtures must become explicit evidence states.

## Python artifact plugin

A useful first non-press consumer could be a conventional packaged CLI. The
Python plugin might provide:

- sdist and wheel member-policy verification;
- metadata, license, dependency, and Python-version consistency;
- package-data completeness;
- import-surface and entry-point discovery;
- clean install into an isolated environment;
- source-checkout absence proof;
- editable-versus-wheel behavioral parity;
- CLI exit/output contracts;
- optional-extra and supported-version matrices;
- reproducibility/difference reports;
- generated documentation/reference drift;
- source archive containment and secret policy;
- release tag, commit, wheel, and GitHub asset identity;
- optional container and SBOM linkage.

The plugin should use established build and inspection libraries rather than
inventing a new wheel format implementation.

## CLI and developer experience

Candidate commands:

```text
trustforge graph                    show artifacts and prerequisites
trustforge invariants               show claims, layers, and proof coverage
trustforge explain <invariant>      explain enforcement, evidence, limitation
trustforge verify <artifact>        build prerequisites and verify the object
trustforge damage <artifact>        run applicable negative operators
trustforge doctor                   return/render typed capability findings
trustforge receipt <stage>          emit canonical evidence for a stage
trustforge receipt verify <file>    verify schema, subjects, and predecessor chain
trustforge projection check         detect local projection drift
trustforge projection check-remote  compare remote projections read-only
trustforge projection apply <id>    explicitly reconcile one target
trustforge release check            consume the complete release claim
```

Human output should always expose:

- what was claimed;
- what object the claim concerns;
- which proofs ran;
- which evidence is missing;
- whether failure means violated, broken harness, unavailable capability, or
  unknown external outcome;
- the narrowest useful remediation;
- where the machine-readable receipt lives.

## Relationship to existing tools

The framework should compose with, not replace:

- pytest for test collection and execution;
- Hypothesis for property and rule-based state testing;
- build backends for wheels and sdists;
- tox/nox or CI matrices for environment orchestration;
- linters and type checkers for their respective analyses;
- container builders and scanners;
- provenance/signing systems;
- GitHub Actions or other CI providers;
- deployment and infrastructure tools.

Its job is to state the repository's claims, require the right evidence,
normalize active outcomes, and preserve exact identity through delivery.

## What must remain in press

The extraction must not pull publishing policy into the kernel:

- book metadata and normalization;
- manuscript/chapter concepts;
- Pandoc, LuaLaTeX, and EPUB orchestration;
- typography, TeX templates, CSS, and visual house rules;
- print trim, margins, spine, barcode, and paper mathematics;
- ISBN, ISSN, LCCN, retailer, and registration rules;
- editorial workflows, prose lint, jargon, and authorities;
- book-site templates and reader behavior;
- physical-book qualification and print-provider commerce.

Those become evidence that the generic extension model can support a demanding
domain without knowing the domain.

## What not to extract yet

Do not extract:

- the current `registry.Artifact` unchanged: its executor dispatch is still a
  press-specific conditional and its condition vocabulary is stringly typed;
- the current `doctor` renderer: probe facts and terminal presentation are not
  yet separated;
- the monolithic selftest command as a framework API;
- GitHub milestone synchronization as a core assumption;
- fixed L0–L7 semantics without first proving other repositories can map their
  evidence honestly;
- a universal configuration language before two independent consumers exist;
- a remote service, dashboard, or database merely to store local proof files;
- signing before canonical receipt semantics and identity are stable.

The first extraction should be boring, local, deterministic, and library-first.

## Extraction readiness gates

Extraction may begin when all of these are true:

1. Press uses the executable invariant ledger as an ordinary development and
   release gate, not only documentation.
2. Collection-time enforcement has caught at least one real missing/stale proof.
3. Typed boundary adapters cover process, filesystem, clock, and at least one
   external or real-tool boundary.
4. Fixture provenance has absorbed both hand-authored and discovered
   regressions.
5. Property, fuzz, and damage systems have produced replayable failures.
6. Trust receipts chain through an installed distribution and release candidate.
7. Mutation/sabotage demonstrates that critical guards are test-sensitive.
8. Press can run from its installed wheel while consuming the same declarations.
9. A second, non-publishing Python repository independently needs the same core
   concepts.
10. The candidate extraction removes duplication from both consumers rather
    than adding adapter ceremony around press.

## Recommended extraction sequence

### Phase 0 — dogfood inside press

Complete v1.12–v1.14 with internal modules and explicit seams. Prefer protocols
and pure values but do not create a second distribution yet.

### Phase 1 — stabilize schemas

Version and canonically serialize:

- invariant ledger;
- public callable classification;
- fixture provenance;
- proof manifest and result;
- artifact identity;
- receipt and predecessor reference;
- typed diagnostic.

Write migrations or explicit incompatibility rules before outside consumers
exist.

### Phase 2 — extract the pure kernel

Move graph validation, invariant/proof validation, canonical serialization,
receipt chaining, diagnostic values, and projection interfaces into a small
package. Keep executors and provider integrations out.

Press temporarily tests both the in-tree compatibility facade and the extracted
package against identical fixtures.

### Phase 3 — extract pytest integration

Move markers, collection gates, proof manifests, result capture, fixture
provenance validation, and state-machine helpers. Preserve `press selftest` as a
press-facing projection over pytest and framework checks.

### Phase 4 — add the Python artifact plugin

Prove usefulness in a small non-publishing CLI/library. Exercise wheel, sdist,
entry point, clean install, documentation projection, and release identity.

### Phase 5 — make press a plugin consumer

Replace compatibility facades with explicit press declarations and verifiers.
Run behavioral parity, installed-wheel, consuming-book, and release gates before
removing old code.

### Phase 6 — publish cautiously

Only after two consumers:

- choose durable package names;
- document compatibility and schema versioning;
- publish extension author guidance;
- establish support and security policies;
- decide governance and release cadence;
- create examples that contain no press/book assumptions.

## Migration strategy

Use a strangler migration rather than a rewrite:

1. Introduce pure internal values and protocols behind existing press commands.
2. Make existing CLI/selftest/docs consume those values.
3. Establish golden behavior and receipt fixtures.
4. Move values into the kernel without changing serialized output.
5. Keep a temporary `press` compatibility module that re-exports or adapts the
   new API.
6. Run old/new implementations against the same artifact and damage corpus.
7. Remove compatibility only after installed consumer-book proof passes.

At no point should framework extraction interrupt the book pipeline or weaken a
release gate.

## Candidate seed backlog for a later project

These are ideas, not issues to create yet:

1. Write the minimal domain model and canonical JSON schemas.
2. Extract deterministic artifact DAG validation.
3. Extract invariant/proof/callable-ledger validation.
4. Implement `proven | violated | unproven | harness_error` verdict semantics.
5. Implement stable typed diagnostics and redaction.
6. Implement receipt creation, chaining, and offline verification.
7. Build pytest collection markers and completeness gates.
8. Build fixture-provenance validation and expected-diagnostic helpers.
9. Define damage-operator and build–mutate–verify protocols.
10. Define injected process, filesystem, clock, randomness, and network
    protocols with deterministic fakes.
11. Define projection rendering, drift, and explicit reconciliation protocols.
12. Build wheel/sdist/entry-point/clean-install verifiers.
13. Build installed-distribution and supported-version scenario runners.
14. Bind GitHub Actions jobs and artifacts into receipt fragments.
15. Prove exact commit–wheel–container–asset–tag release identity.
16. Add mutation/sabotage tests for the framework itself.
17. Migrate press behind a compatibility facade.
18. Pilot a second non-publishing repository.
19. Conduct API/schema review based on both consumers.
20. Only then choose names, publish packages, and establish governance.

## Risks

### Premature abstraction

The largest risk is extracting terminology rather than stable behavior. Mitigate
it with the readiness gates and second-consumer requirement.

### Becoming another task runner

If the framework starts owning arbitrary shell workflows, it will compete with
mature orchestration tools and lose its distinctive claim/evidence model. Keep
execution behind narrow adapters.

### Configuration-language gravity

A universal YAML format can become a second programming language. Prefer typed
Python declarations for composition and small versioned schemas for durable
evidence. Support declarative files only where reviewability and external
generation justify them.

### False assurance

A polished proof matrix could make weak evidence look authoritative. Require
limitations, negative proof, subject identity, skipped/omitted evidence, and
mutation of critical enforcement.

### Receipt theater

Receipts are valuable only if they bind exact objects and predecessor evidence.
Do not emit elaborate attestations whose subject identity or proof semantics are
ambiguous.

### Framework coupling

Press must remain able to express publishing-specific laws without putting
those concepts into the kernel. Prefer plugin protocols and opaque domain
metadata over ever-growing core enums.

### Supply-chain recursion

The framework itself becomes part of the release trust base. Its own wheel,
plugins, schemas, and receipt verifier need installed-distribution, mutation,
compatibility, and release-identity proof.

## Success criteria

An extraction is successful when:

- press has less domain-neutral machinery, not more adapter duplication;
- a second Python project can declare artifacts and invariants without importing
  publishing concepts;
- both projects detect missing proof at collection time;
- both prove known-bad fixtures fail for expected diagnostics;
- both emit offline-verifiable receipts bound to installed artifacts;
- release gates reject subject or predecessor mismatches;
- the framework composes with existing Python tooling;
- ordinary fast checks remain local and deterministic;
- maintainers can explain exactly what is proven, unproven, and outside scope;
- removal of a critical guard makes sabotage/mutation gates fail.

## Open questions

1. Is the primary abstraction an artifact graph, an invariant ledger, or a
   receipt graph? They are related but one should lead the API.
2. Are L0–L7 fixed public semantics or a default taxonomy with repository-defined
   extensions?
3. Should artifact and proof declarations be Python-first, schema-first, or a
   carefully bounded hybrid?
4. Which identities are content digests, logical stable IDs, or both?
5. How are nondeterministic but legitimate tools represented without
   normalizing away meaningful differences?
6. What is the minimal receipt that remains useful offline?
7. Which omissions are allowed, and who may authorize a release exception?
8. How does changed-code test impact remain conservative when Python behavior is
   dynamic?
9. How should plugin compatibility and receipt-schema compatibility interact?
10. Which second repository is different enough from press to challenge the
    abstraction honestly?
11. Should the eventual project live in this repository first, a monorepo, or a
    separate repository after the pure kernel exists?
12. What name communicates evidence and production without implying formal
    verification the framework does not provide?

## Decision posture

For now:

- continue building the machinery inside press;
- design internal seams as if extraction may happen;
- avoid framework-specific promises in press's public contract;
- record general lessons and rejected abstractions here;
- require the readiness gates before creating a new package or repository;
- let production scars, not aesthetic API preference, determine the extracted
  shape.

The desired outcome is not maximum reuse. It is a small, honest kernel whose
claims remain meaningful from a pure function through the exact artifact a user
or deployment receives.
