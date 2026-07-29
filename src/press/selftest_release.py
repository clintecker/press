"""The selftest's release, commerce, provider, and print-surface checks.

Split out of ``selftest.py`` alongside :mod:`press.selftest_book`. These
verify the distribution surface: the trust-receipt chain, the edition
manifest, provider qualification and the neutral provider contract, print
profile seals, the commerce config and its release gate, the release-tag
grammar, the CLI command catalog, the CLAUDE.md/AGENTS.md contract mirror,
the generated docs suite, and the v1->v2 migration.

``selftest.py`` re-exports every check defined here, so
``selftest.check_<name>``, the ordered ``CHECKS`` list, and
``quality_checks``' ``getattr(selftest, "check_<name>")`` keep resolving.
Shared helpers (the tag corpus, ``_repo_root``, ``render_reference``) live
in ``selftest.py`` and are imported lazily inside the function bodies to
dodge the re-export import cycle.
"""

from __future__ import annotations

import re
from pathlib import Path


def check_receipt_chain() -> None:
    """The trust-receipt chain refuses a broken chain: a dirty-tree
    release receipt, a release whose package digest does not match the
    built object, and an incomplete chain that skips trust layers are
    each rejected."""

    from . import receipts

    inputs = {
        "invariants": "d",
        "fixtures": "d",
        "scenarios": "d",
        "surfaces": "d",
        "toolchain": "sha-x",
    }
    dirty = receipts.Receipt(
        schema_version=receipts.SCHEMA_VERSION,
        layer="release",
        source_commit="c",
        tree_clean=False,
        inputs=inputs,
        prerequisites=[],
        proofs=[],
        artifacts={"package": "PKG", "toolchain": "sha-x"},
        local_dev=True,
    )
    if not any("dirty tree" in p for p in receipts.verify_chain([dirty], require_clean=True)):
        raise SystemExit("selftest: receipt chain blessed a dirty-tree release")
    clean = receipts.Receipt(
        schema_version=receipts.SCHEMA_VERSION,
        layer="release",
        source_commit="c",
        tree_clean=True,
        inputs=inputs,
        prerequisites=[],
        proofs=[],
        artifacts={"package": "PKG", "toolchain": receipts.pinned_toolchain_digest()},
    )
    if not any("package digest" in p for p in receipts.verify_release([clean], "OTHER")):
        raise SystemExit("selftest: release receipt blessed a package mismatch")
    # A two-layer placeholder standing in for every layer must be refused:
    # completeness is what turns the chain from an assertion into a proof.
    collection = receipts.Receipt(
        schema_version=receipts.SCHEMA_VERSION,
        layer="collection",
        source_commit="c",
        tree_clean=True,
        inputs=inputs,
        prerequisites=[],
        proofs=[],
        artifacts={},
    )
    placeholder_release = receipts.Receipt(
        schema_version=receipts.SCHEMA_VERSION,
        layer="release",
        source_commit="c",
        tree_clean=True,
        inputs=inputs,
        prerequisites=[collection.digest()],
        proofs=[],
        artifacts={"package": "PKG", "toolchain": receipts.pinned_toolchain_digest()},
    )
    if not any(
        "incomplete release chain" in p
        for p in receipts.verify_release([collection, placeholder_release], "PKG")
    ):
        raise SystemExit("selftest: release chain blessed a skipped trust layer")
    # The per-job release (#150) fails closed when a CI tier's receipt is
    # absent: a job that did not run leaves a missing receipt.
    tiers = [
        receipts.Receipt(
            schema_version=receipts.SCHEMA_VERSION,
            layer="quality",
            source_commit="c",
            tree_clean=True,
            inputs=inputs,
            prerequisites=[],
            proofs=[],
            artifacts={},
        )
    ]
    # 'integration' deliberately absent: its job did not run.
    if not any(
        "missing tier receipt 'integration'" in p for p in receipts.verify_ci_release(tiers, "PKG")
    ):
        raise SystemExit("selftest: per-job release blessed a missing CI tier")


def check_edition_manifest() -> None:
    """The edition manifest holds for a valid release-gated edition and
    refuses a forged identity and a byte mismatch: an order can only name
    the exact bytes the release approved."""

    import dataclasses

    from . import edition

    interior_sha = "1" * 64
    cover_sha = "2" * 64
    base = edition.EditionManifest(
        schema_version=edition.SCHEMA_VERSION,
        edition_id="",
        slug="proof-book",
        title="Proof",
        format="paperback",
        isbn=None,
        trim_width=6.0,
        trim_height=9.0,
        page_count=120,
        paper="cream",
        spine_width_in=0.3,
        bleed_in=0.125,
        interior=edition.ArtifactRef("interior", interior_sha, 4096),
        cover=edition.ArtifactRef("cover", cover_sha, 2048),
        toolchain_digest="sha-abc",
        source_commit="c0ffee",
        tree_clean=True,
        input_digests={"invariants": "d"},
        receipt_digests=("r0",),
    )
    manifest = dataclasses.replace(base, edition_id=edition._identity_digest(base))
    observed = edition.Observed(interior_sha, 4096, 120, cover_sha, 2048)
    if edition.verify_facts(manifest, observed):
        raise SystemExit("selftest: edition manifest rejected a valid edition")
    # A production fact changed without re-deriving identity is a forgery.
    forged = dataclasses.replace(manifest, page_count=manifest.page_count + 10)
    if not any("identity digest" in p for p in edition.verify_facts(forged, observed)):
        raise SystemExit("selftest: edition manifest blessed a forged identity")
    # The artifact on disk no longer hashes to the recorded digest.
    tampered = edition.Observed("0" * 64, 4096, 120, cover_sha, 2048)
    if not any("interior digest" in p for p in edition.verify_facts(manifest, tampered)):
        raise SystemExit("selftest: edition manifest blessed a byte mismatch")


def check_provider_qualification() -> None:
    """The provider record is well-formed, and only a passed physical
    inspection scoped to the edition qualifies a provider: marketing alone
    and a stale or wrong-edition inspection are refused."""

    from . import qualification as q

    problems = q.validate()
    if problems:
        raise SystemExit(f"selftest: provider qualification record invalid: {problems[:2]}")
    passed = {point: q.PASS for point in q.REQUIRED_CHECKLIST}
    # A single failed point cannot qualify: the physical gate is real.
    failed = q.PhysicalInspection(
        "ed1", "lulu", "PB", "US", "inspector", {**passed, "barcode": "fail"}
    )
    qual, probs = q.qualify(failed, "ed1")
    if qual is not None or not any("not passed" in p for p in probs):
        raise SystemExit("selftest: qualification honored a failed physical inspection")
    # A copy inspected against a different edition is stale.
    other = q.PhysicalInspection("edX", "lulu", "PB", "US", "inspector", passed)
    qual2, probs2 = q.qualify(other, "ed1")
    if qual2 is not None or not any("different edition" in p for p in probs2):
        raise SystemExit("selftest: qualification honored a stale inspection")


def check_profile_seals() -> None:
    """Every shipped print profile is sealed under the design contract, and
    the seal gate bites: a profile whose geometry drifts from its sealed
    digest is refused, so appearance cannot change without a deliberate
    re-seal (the design-major law)."""

    from . import profile_lifecycle as pl

    problems = pl.validate()
    if problems:
        raise SystemExit(f"selftest: profile seal ledger does not hold: {problems[:2]}")
    # The gate is real: a seal recording a digest the profile no longer has is
    # drift, and must be refused.
    seals = pl.load_seals()
    if not seals:
        raise SystemExit("selftest: no profile seal ledger shipped")
    victim = next(iter(seals))
    drifted = dict(seals)
    drifted[victim] = pl.Seal(
        profile_id=victim,
        design_major=seals[victim].design_major,
        digest="deadbeefdeadbeef",
        qualified_on=seals[victim].qualified_on,
    )
    if not any("drifted from its seal" in p for p in pl.validate(drifted)):
        raise SystemExit("selftest: profile seal gate did not catch a digest drift")
    # An unsealed shipped profile is refused too.
    without = {k: v for k, v in seals.items() if k != victim}
    if not any("is not sealed" in p for p in pl.validate(without)):
        raise SystemExit("selftest: profile seal gate did not catch an unsealed profile")


def check_commerce_config() -> None:
    """The print-order config verifier refuses an insecure origin, an
    unnamed seller, and an embedded secret; a policy page may be linked out
    or generated; and the CTA is emitted only for a sellable edition."""

    from . import commerce

    good = commerce.load(
        {
            "commerce": {
                "print-ordering": {
                    "enabled": True,
                    "edition": "paperback",
                    "storefront-url": "https://store.example.test/x",
                    "seller-of-record": "Lulu",
                    "support-url": "https://ex.test/s",
                }
            }
        }
    )  # privacy/refund omitted -> generated
    if good is None or commerce.validate(good):
        raise SystemExit("selftest: commerce verifier rejected a valid config")
    if good.generated_kinds() != ["privacy", "refund"]:
        raise SystemExit("selftest: an omitted policy link should be generated")
    if not commerce.should_emit(good, sellable=True) or commerce.should_emit(good, sellable=False):
        raise SystemExit("selftest: commerce CTA emission ignored edition sellability")
    bad = commerce.load(
        {
            "commerce": {
                "print-ordering": {
                    "enabled": True,
                    "edition": "paperback",
                    "storefront-url": "http://insecure",
                    "seller-of-record": "",
                    "support-url": "https://ex.test/s?api_key=sk_live_x",
                    "privacy-url": "http://x",
                }
            }
        }
    )
    problems = commerce.validate(bad)
    for needle in (
        "storefront-url must be https",
        "seller-of-record",
        "privacy-url must be https",
        "secret",
    ):
        if not any(needle in p for p in problems):
            raise SystemExit(f"selftest: commerce verifier missed {needle!r}")


def check_commerce_release_gate() -> None:
    """The print-ordering release gate fails closed: a book advertising
    ordering cannot ship unless its edition passed a physical
    qualification; a book that sells nothing ships freely."""

    from . import commerce

    enabled = commerce.load(
        {
            "commerce": {
                "print-ordering": {
                    "enabled": True,
                    "edition": "paperback",
                    "storefront-url": "https://store.example.test/x",
                    "seller-of-record": "Lulu",
                    "support-url": "https://ex.test/s",
                    "privacy-url": "https://ex.test/p",
                    "refund-url": "https://ex.test/r",
                }
            }
        }
    )
    if not any(
        "no passed physical qualification" in p
        for p in commerce.release_problems(enabled, edition_qualified=False)
    ):
        raise SystemExit("selftest: release gate shipped an unqualified commerce edition")
    if commerce.release_problems(enabled, edition_qualified=True):
        raise SystemExit("selftest: release gate blocked a qualified, valid edition")
    disabled = commerce.load({"commerce": {"print-ordering": {"enabled": False}}})
    if commerce.release_problems(disabled, edition_qualified=False):
        raise SystemExit("selftest: release gate blocked a book that sells nothing")


def check_provider_contract() -> None:
    """A print provider adapter keeps the neutral contract: money parses
    without float error, an unsupported capability is a typed refusal, an
    unknown status quarantines, and a submission timeout is an unknown
    outcome -- never a fabricated acceptance or a guessed transition."""

    from .providers import contract, fake

    cents = (contract.Money.parse("USD", "0.1") + contract.Money.parse("USD", "0.2")).minor_units
    if cents != 30:
        raise SystemExit("selftest: provider money parsing lost a cent to float")
    limited = fake.FakeProvider(capabilities=frozenset({contract.Capability.SUBMIT}))
    if not isinstance(limited.cancel("x"), contract.TypedError):
        raise SystemExit("selftest: adapter simulated an unsupported capability")
    if limited.normalize_status("mystery") != contract.ProviderStatus.UNKNOWN:
        raise SystemExit("selftest: adapter guessed an unknown provider status")
    timing_out = fake.FakeProvider()
    timing_out.script_submit("timeout")
    if not isinstance(timing_out.submit(fake.sample_submission()), contract.UnknownOutcome):
        raise SystemExit("selftest: adapter turned a submission timeout into a definite outcome")


def check_release_grammar() -> None:
    """The release script's tag validation, exercised without any
    network: exactly vN.x.y, and the composite action's command
    grammar rejects shell syntax."""

    from . import adapters
    from .selftest import BAD_TAGS, GOOD_TAGS

    script = Path(__file__).resolve().parent.parent.parent / "scripts" / "release.sh"
    if not script.is_file():
        return  # installed wheel; the script ships with the repo only
    good = GOOD_TAGS
    bad = BAD_TAGS
    for tag in good:
        result = adapters.process_runner.run(
            ["bash", str(script), "--check-tag", tag], capture=True
        )
        if result.returncode != 0:
            raise SystemExit(f"selftest: release grammar rejected valid {tag!r}")
    for tag in bad:
        result = adapters.process_runner.run(
            ["bash", str(script), "--check-tag", tag], capture=True
        )
        if result.returncode == 0:
            raise SystemExit(f"selftest: release grammar accepted invalid {tag!r}")

    action = script.parent.parent / "action.yml"
    text = action.read_text(encoding="utf-8")
    if "${{ inputs.command }}" in text.split("env:")[-1].split("run:")[-1]:
        raise SystemExit("selftest: action.yml interpolates inputs.command into shell text")
    # The action's grammar, proven against the audit's injection string.
    import re as re_mod

    grammar = re_mod.compile(r"^[a-z][a-z0-9-]*( [A-Za-z0-9._/=-]+)*$")
    assert grammar.match("all")
    assert grammar.match("art accept art/candidates/cover-1.png --as=cover")
    assert not grammar.match("all; touch /tmp/pwned")
    assert not grammar.match("all && rm -rf .")
    assert not grammar.match("$(id)")


def check_contract_mirror() -> None:
    """AGENTS.md is a generated mirror of CLAUDE.md (same contract,
    agents.md convention): identical below the heading line, so the
    two cannot drift apart again."""

    from .selftest import _repo_root

    root = _repo_root()
    if root is None:
        return
    claude = (root / "CLAUDE.md").read_text(encoding="utf-8")
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    if agents.split("\n", 1)[1] != claude.split("\n", 1)[1]:
        raise SystemExit(
            "AGENTS.md has drifted from CLAUDE.md; regenerate it "
            "(the body below the heading must be identical)"
        )


def check_command_catalog() -> None:
    """The CLI and the desk read one command catalog, so their surfaces
    cannot drift: every catalog command is dispatchable, every route is
    a catalog command, and the usage text is the catalog's own
    rendering."""

    from . import __main__ as cli, catalog

    routes = set(cli.ROUTES)
    formats = set(cli.FORMATS) | {"print"}
    for command in catalog.COMMANDS:
        target = command.alias_of or command.name
        if not (
            command.name in routes
            or command.name in formats
            or target in routes
            or target in formats
        ):
            raise SystemExit(f"catalog command {command.name!r} is not dispatchable")
    known = catalog.canonical_targets()
    for route in routes:
        if route not in known:
            raise SystemExit(f"route {route!r} is not in the command catalog")
    if cli.USAGE != catalog.render_usage():
        raise SystemExit("cli.USAGE is not the catalog's rendering; regenerate it")


def check_docs() -> None:
    from . import __main__ as cli
    from . import invariants, selftest

    here = Path(selftest.__file__).resolve().parent
    readme = here.parent.parent / "README.md"
    usage_words = set(re.findall(r"[a-z-]{2,}", cli.USAGE.split("usage:")[1]))
    routed = set(cli.ROUTES) | set(cli.FORMATS) | {"print"}
    missing_from_usage = sorted(routed - usage_words)
    if missing_from_usage:
        raise SystemExit(f"targets routed but absent from usage text: {missing_from_usage}")
    if readme.is_file():
        text = readme.read_text(encoding="utf-8")
        undocumented = sorted(t for t in routed if not re.search(rf"\b{re.escape(t)}\b", text))
        if undocumented:
            raise SystemExit(f"targets absent from README: {undocumented}")
    reference = here.parent.parent / "docs" / "REFERENCE.md"
    if reference.is_file() and reference.read_text(encoding="utf-8") != selftest.render_reference():
        raise SystemExit(
            "docs/REFERENCE.md drifted from the registry; regenerate with "
            "`press selftest --write-docs`"
        )
    invariants_doc = here.parent.parent / "docs" / "INVARIANTS.md"
    if invariants_doc.is_file():
        try:
            rendered = invariants.render()
        except ImportError:
            rendered = None  # celebrimbor absent (bare/3.10 leg); the drift
            # check runs on the quality tier, where the gate does.
        if rendered is not None and invariants_doc.read_text(encoding="utf-8") != rendered:
            raise SystemExit(
                "docs/INVARIANTS.md drifted from .celebrimbor/invariants.yaml; "
                "regenerate with `press selftest --write-docs`"
            )
    from . import qualification

    quals_doc = here.parent.parent / "docs" / "PROVIDER-QUALIFICATION.md"
    if quals_doc.is_file() and quals_doc.read_text(encoding="utf-8") != qualification.render():
        raise SystemExit(
            "docs/PROVIDER-QUALIFICATION.md drifted from quality/providers.yaml; "
            "regenerate with `press selftest --write-docs`"
        )


def _migration_owned_bytes(book) -> dict:
    """The owned content whose bytes migration must never change."""

    return {
        path: path.read_bytes()
        for pattern in ("book/**/*", "config/**/*", "tex/**/*", "assets/**/*")
        for path in book.glob(pattern)
        if path.is_file()
    }


def _migration_diagnose(book, migrate) -> tuple[int, int]:
    """A clean diagnosis with a pin the migration is proven relative to.

    The scaffold pins whatever major the template ships (v1, then v2, ...);
    the migration is proven relative to that, not against a fixed 1.
    """

    diagnosis = migrate.diagnose(book)
    assert not diagnosis.problems, diagnosis.problems
    start = diagnosis.from_major
    assert start is not None, "scaffold produced a split or absent pin"
    target = start + 1
    site_paths = {site.path for site in diagnosis.sites}
    assert "requirements.txt" in site_paths, site_paths
    assert any(p.startswith(".github/workflows/") for p in site_paths), site_paths
    return start, target


def _migration_dry_run_leaves_disk(book, start, target, owned, migrate) -> None:
    """A dry-run plan reports the repin and mutates nothing on disk."""

    plan = migrate.plan(book, target)
    assert plan.from_major == start and plan.to_major == target
    assert plan.changes, "plan produced no changes"
    assert any("design is unchanged" in note for note in plan.notes)
    for path, original in owned.items():
        assert path.read_bytes() == original, f"plan touched {path}"
    assert not (book / migrate.STATE_DIR / migrate.BACKUP).is_file()


def _migration_apply_then_rollback(book, start, target, owned, migrate) -> None:
    """Apply moves only the pin; owned content is untouched; rollback
    restores the exact prior pin."""

    migrate.apply(book, target)
    for site in migrate.pin_sites(book):
        assert site.major == target, f"{site.path} still pinned to v{site.major}"
    for path, original in owned.items():
        assert path.read_bytes() == original, f"apply changed owned file {path}"
    assert (book / migrate.STATE_DIR / migrate.RECEIPT).is_file()

    migrate.rollback(book)
    for site in migrate.pin_sites(book):
        assert site.major == start, f"rollback left {site.path} at v{site.major}"
    assert not (book / migrate.STATE_DIR / migrate.BACKUP).is_file()


def _migration_override_is_surfaced(book, migrate) -> None:
    """A custom override is named by diagnosis so the author re-checks it."""

    (book / "tex").mkdir(exist_ok=True)
    (book / "tex" / "title-page.tex").write_text("% custom\n", encoding="utf-8")
    overrides = dict(migrate.diagnose(book).overrides)
    assert "tex/title-page.tex" in overrides, overrides


def check_migration() -> None:
    """The v1->v2 migration keeps its two promises on a real scaffolded book:
    a dry-run plan reports the repin and changes nothing on disk
    (INV-migration-preview), and apply moves only the pin -- the manuscript,
    config, and art come out byte-for-byte identical -- while rollback
    restores the exact prior pin (INV-migration-safe). A custom override is
    surfaced by diagnosis, not silently carried."""

    import tempfile

    from . import migrate, scaffold

    with tempfile.TemporaryDirectory() as tmp:
        book = Path(tmp) / "migration-proof"
        scaffold.main([str(book), "--author", "Migration Tester"])

        owned = _migration_owned_bytes(book)
        start, target = _migration_diagnose(book, migrate)
        _migration_dry_run_leaves_disk(book, start, target, owned, migrate)
        _migration_apply_then_rollback(book, start, target, owned, migrate)
        _migration_override_is_surfaced(book, migrate)
