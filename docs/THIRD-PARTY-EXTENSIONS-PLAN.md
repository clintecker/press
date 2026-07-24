# Third-party extensions: the decision record

This is the decision record the extension contract's closing clause calls
for. [`docs/EXTENSION-CONTRACT.md`](EXTENSION-CONTRACT.md) ends by saying
that admitting a code extension "is a new decision record and a new major,
not a hook slipped in under this one." This is that record, and
[#173](https://github.com/clintecker/press/issues/173) is the work it
authorizes. It amends the contract rather than replacing it: everything
`contract-major: 2` promises stays true for a `contract-major: 2` manifest.

## Why the contract has to change at all

The accepted contract (#171) is pure-data and in-package. An extension is a
YAML file under `src/press/data/`, discovered by a sorted glob, and it
contributes only declarations. That works for the four data kinds -- a
design profile, a provider spec, a skill, a workflow -- and it should keep
working exactly as it does.

It cannot express what #173 requires. An *artifact family* is not a
declaration: something has to build the artifact and something has to verify
it, and both are code. And a separately built third-party wheel installs
under its own top-level package, so it can never drop a file into
`src/press/data/` -- the very directory the current lifecycle scans. The
contract's Lifecycle section, which says discovery is "a function of what
files exist," is therefore not merely incomplete for #173; it is
*inconsistent* with #173's stated acceptance criterion ("a separately built
reference wheel adds one artifact family end to end").

So two things change together: discovery learns to read manifests from
installed distributions, and the contract admits declared, typed extension
code. Both land as `contract-major: 3`.

## The seven decisions

Ratified 2026-07-24. Each was chosen against the invariants #173 names:
deterministic registration order, collision-checking before any action,
installed wheels working with no source checkout, and hostile plugins
escaping nothing.

### 1. Executable extension code is admitted, narrowly

An extension may name a **builder** and a **verifier** as dotted callables
within its own package. The press invokes them through a typed protocol;
they must return the existing [`BuildReceipt`](../src/press/results.py) and
`VerificationReport`. Nothing else about the extension is code: the four
pure-data kinds keep their no-code path unchanged, and a `contract-major: 2`
manifest can still contribute only declarations.

*Why:* an artifact family needs a builder and a verifier, and #173's
acceptance demands one end to end. The alternative -- refusing code -- does
not make the requirement go away; it makes press the only party allowed to
add an artifact, which is the composability the v2 milestone exists to end.

### 2. Discovery is a book-declared pinned list, never entry points

A book names its extensions in `config/extensions.yaml`, by distribution and
pinned version, validated by the same typed boundary as every other config
write. The press resolves each through `importlib.metadata.distribution()`
and reads that distribution's packaged `extension.yaml` **as data** -- a
resource read, not an import of the extension's runtime code.

Entry points are rejected as an *activation* mechanism for three reasons,
each fatal on its own: `entry_points()` iteration order is filesystem- and
install-method-dependent, so it fails the determinism invariant outright;
reading an entry point means importing arbitrary module code, which is the
"behavior from the accident of which package imported first" the contract
forbids; and it is precisely the accidental plugin API #171 was opened to
prevent. An extension wheel *may* declare an entry point so `press doctor`
can report "installed but not activated" -- advisory only, never an
activation path.

**The total order** is `sorted()` on the manifest's globally unique
extension name. Uniqueness is enforced (a duplicate name is a refused
collision), so the key is total with no ties; `(distribution, version)` is a
defensive tiebreak that can only fire on an already-refused duplicate.

### 3. Extension wheels enter through the book's hash-pinned lock

The press installs its own runtime dependencies from `requirements-lock.txt`
with `--require-hashes`, then itself with `--no-deps`, so a pinned release
resolves immutable bytes. Extensions must not open a hole in that: they are
carried in the **book's** lock file, with hashes, and the action installs
the book's lock the same way. Extensions are never pip-resolved at CI time.

### 4. The press's own guards extend over extension code

At preflight, the import gate, the import-time side-effect sandbox
(`adapters/import_guard.py`), and the AST surfaces inventory run over each
activated extension's declared modules, exactly as they run over
`press.*`. An extension module that opens a socket, spawns a process, or
writes a file *while being imported* is refused, named. An extension wheel
must also ship its own conformance test, which the book's CI runs.

### 5. The trust chain records the extension set

The build receipt records each extension's name, version, and manifest
digest, plus a digest of the combined registry; the combined-registry digest
joins `receipts.MANIFESTS`. A release chain therefore names the exact
pipeline it stood on, and cannot claim a pipeline different from the
extensions that actually ran.

### 6. Failure isolation: closed at preflight, per-target at runtime

A conformance, version, or collision failure **fails the whole build closed**
at preflight, with a located reason. An extension a book pinned is never
silently dropped -- that would let a book quietly build without the thing it
declared. A *runtime* builder failure fails its own target; but a book that
pinned the extension and ran `press all` fails, because a skipped target is
not a success.

### 7. Third-party commands are allowed, namespaced and collision-checked

An extension may contribute a CLI command. Names are collision-checked
against the canonical targets before anything runs, and a reserved prefix
convention keeps a future core command from being pre-empted by an installed
extension.

## The isolation model, stated honestly

What the press **enforces**:

- **Book-root containment.** Builders run under the existing regime: `cwd`
  is the book root, `BOOK_ROOT` injected.
- **Declared outputs only.** After a builder returns, every path in its
  `BuildReceipt.outputs` must resolve under `dist/` and appear in the
  manifest's declared output set. Undeclared output is refused with the same
  "escaped its root" model that already governs source archives.
- **No shadowing.** The combined-registry collision check refuses any name,
  output path, or capability that shadows core *before* a builder runs;
  sealed capabilities stay unclaimable.
- **No import-time side effects** (decision 4).
- **A verifier and a publication class per artifact.** Assembly refuses an
  artifact-kind manifest that names neither. A builder that does not return
  a `BuildReceipt`, or a verifier that does not return a
  `VerificationReport`, is a typed refusal.

What the press **trusts**, and will say so in the contract: the internal
computation of a builder is arbitrary Python and is not sandboxed. Builders
legitimately shell out to pandoc and LuaLaTeX; CPU, memory, and their own
subprocesses are not bounded. The guarantee is **containment of effects**,
not sandboxing of computation. The existing contract already concedes this
for the data case; admitting code widens the concession, and pretending
otherwise would be the dishonest part.

## What this changes in the tree

These land **with the #173 implementation**, not with this record. In
particular `SUPPORTED_CONTRACT_MAJORS` must not gain `3` before the press can
actually honor a `3` manifest: bumping it early would let such a manifest
pass conformance and then fail somewhere further in, which is exactly the
"learns it is incompatible before it has built anything" promise inverted.

- `SUPPORTED_CONTRACT_MAJORS` gains `3`, in the same change that teaches the
  press to speak it. A `contract-major: 2` manifest keeps conforming,
  unchanged; only a `3` manifest may declare code or arrive from an installed
  distribution.
- The Lifecycle section of the contract gains a discovery source: after the
  in-package sorted glob, the book's declared extension list, resolved from
  installed distributions in sorted-by-name order.
- "What this contract deliberately does not do" is amended to point here: it
  remains true of `contract-major: 2`, and this record is the successor it
  anticipated.
- A **combined registry** becomes the single projection source for the CLI,
  desk, doctor, reference, invariant, and impact surfaces, replacing the
  hardcoded dicts those surfaces read today.

## Why this is a new major

It admits a capability the sealed design contract says requires one; it
changes what the combined registry, the reference projection, and the
surfaces inventory *are*, since each now spans third-party callables; and it
changes what a build can produce and what the published downloads contain.
It ships behind the migration path, not inside a minor.

## The minimal acceptance slice

A separately built, separately versioned wheel -- `press-ext-example` --
adding **one** artifact family: a `notecards` artifact producing
`dist/{slug}-notecards.pdf`, declaring a builder, a verifier, a publication
class, one invariant, and its proof. Proven by the five layers #173 names:

- **Conformance** -- the manifest passes; the hostile variants (collision,
  bad version, sealed claim, unproven obligation, malformed) are each
  refused with their located reason.
- **Damage** -- the verifier turns red on a corrupted `notecards.pdf`.
- **Graph** -- the combined build order stays acyclic, no duplicate outputs,
  and the artifact appears in the downloads by policy.
- **Installed wheel** -- both wheels built and `pip install --no-deps`ed into
  a scaffolded book; `press all` produces *and verifies* the artifact through
  the ordinary graph and receipt path.
- **Consumer** -- a real book pins the extension and builds green.
