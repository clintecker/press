"""Register press's domain quality checks with celebrimbor.

Importing this module installs every press-specific check -- the ones
celebrimbor cannot know about: editorial rules, the book model, provider
contracts, the render/PDF/EPUB verifiers -- into celebrimbor's default
registry via ``@celebrimbor.check``, so both ``celebrimbor.gate()`` and the
``celebrimbor gate`` CLI (which imports this module through ``[tool.celebrimbor]
check_modules``) run them alongside the framework's own gates.

Registration-by-import is celebrimbor's one documented seam, the same way its
own builtins register when ``load_builtin_checks`` imports them. It is a
registry mutation, not an I/O side effect, so it does not offend celebrimbor's
import-health gate (which forbids network/subprocess/file writes on import).
:func:`register` is idempotent so re-importing the module -- as that gate's
probe does -- does not raise ``DuplicateCheckError`` on the second pass. This
module is imported only when the celebrimbor gate runs (celebrimbor is a dev/CI
dependency, never a book runtime one), so ``import press`` never pulls it in.

This is the registration seam only: the check *bodies* stay in their home
modules (``selftest.check_*`` delegates to ``verify_pdf``, ``jargon_lint``,
``gen_authorities``, ...). Celebrimbor's own builtin checks cover press's former
*infrastructure* checks (imports, registry, invariant ledger, fixture
provenance, producers), so those are NOT registered here -- they are retired
when press's parallel machinery is deleted.

Every registration names the falsifier that turns its check red -- the concrete
negative that proves the gate bites, so celebrimbor's falsifier gate resolves a
real proof rather than a dated promise. Most name a known-bad fixture or a
pytest node that was *run* to confirm the rejection (see the map-falsifiers
audit); the handful whose negatives live inline in the check body as ``else:
raise`` witnesses point at that body (``selftest.py::check_<name>``), which is
the "carry your own falsifier" case celebrimbor is built around.
"""

from __future__ import annotations

from celebrimbor import check
from celebrimbor.result import CheckResult, Finding, Stage

# The press domain checks celebrimbor should run:
#   name -> (one-line title, tier, falsified_by).
# The tier mirrors how heavy the check is: FAST = config/pure validation,
# DEFAULT = reads the tree or a scaffolded book, FULL = toolchain/render paths.
# falsified_by is a repo-relative fixture path or a pytest node-id (file::node)
# whose file part celebrimbor's falsifier gate resolves; each was verified to
# redden its check by the map-falsifiers audit (running the negative test, or
# mutating the fixture and watching the check go red).
_DOMAIN: dict[str, tuple[str, Stage, str]] = {
    "arithmetic": (
        "the canonical examples' arithmetic agrees",
        Stage.FAST,
        "src/press/selftest.py::check_arithmetic",
    ),
    "slug_invariant": (
        "book slugs stay valid and stable",
        Stage.FAST,
        "tests/test_selftest_checks.py::test_slug_invariant_rejects_bad",
    ),
    "jargon_parity": (
        "the jargon lint agrees across its corpus",
        Stage.DEFAULT,
        "tests/test_jargon_parity.py::test_shared_logic_is_byte_identical",
    ),
    "source_policy": (
        "the source package excludes what it must",
        Stage.FAST,
        "tests/test_properties_policy.py::test_secret_named_file_is_never_admitted",
    ),
    "pages_verifier": (
        "the reader-site verifier holds its promises",
        Stage.DEFAULT,
        "src/press/selftest.py::check_pages_verifier",
    ),
    "scaffold_neutrality": (
        "a scaffolded book is neutral, no leaked identity",
        Stage.FAST,
        "src/press/data/template/config/metadata.yaml",
    ),
    "book_model": (
        "the book model validates its config",
        Stage.FAST,
        "src/press/selftest.py::check_book_model",
    ),
    "registry": (
        "the build artifact graph is acyclic with unique, resolvable outputs",
        Stage.FAST,
        "tests/test_sabotage.py::test_sabotage_removed_graph_edge_reddens_state_model",
    ),
    "format_witnesses": (
        "every edition carries the manuscript witnesses",
        Stage.DEFAULT,
        "tests/test_selftest_checks.py::test_invariant_check_passes[check_format_witnesses]",
    ),
    "editions_agree": (
        "the editions agree on the book's content",
        Stage.DEFAULT,
        "tests/test_verify_editions.py::test_an_edition_that_drops_a_chapter_is_named_and_refused",
    ),
    "editorial_checkers": (
        "every editorial checker rejects its known-bad",
        Stage.DEFAULT,
        "src/press/data/known-bad/em-dash.md",
    ),
    "site_identity": (
        "the docs site declares its identity correctly",
        Stage.FAST,
        "tests/test_selftest_checks.py::test_invariant_check_passes[check_site_identity]",
    ),
    "authorities_ledger": (
        "the authorities ledger's claims still hold",
        Stage.DEFAULT,
        "tests/test_selftest_checks.py::test_invariant_check_passes[check_authorities_ledger]",
    ),
    "honest_refusals": (
        "the honest-refusal fixtures are refused",
        Stage.FAST,
        "src/press/selftest.py::check_honest_refusals",
    ),
    "release_grammar": (
        "the release grammar is well-formed",
        Stage.FAST,
        "scripts/release.sh",
    ),
    "receipt_chain": (
        "the receipt chain verifies end to end",
        Stage.DEFAULT,
        "tests/test_receipts.py::test_release_refuses_dirty_tree_receipt",
    ),
    "edition_manifest": (
        "the edition manifest is complete and consistent",
        Stage.FAST,
        "tests/test_edition.py::test_forged_identity_is_refused",
    ),
    "provider_qualification": (
        "providers qualify against their spec",
        Stage.DEFAULT,
        "tests/test_qualification.py::test_a_failed_point_cannot_qualify",
    ),
    "profile_seals": (
        "every print profile matches its sealed geometry",
        Stage.FAST,
        "tests/test_profile_lifecycle.py::test_digest_drift_is_refused",
    ),
    "commerce_config": (
        "the commerce config validates",
        Stage.FAST,
        "tests/test_commerce.py::test_an_embedded_secret_is_refused",
    ),
    "commerce_release_gate": (
        "the commerce release gate holds",
        Stage.DEFAULT,
        "tests/test_commerce.py::test_release_gate_refuses_an_unqualified_edition",
    ),
    "provider_contract": (
        "providers honour the neutral contract",
        Stage.DEFAULT,
        "tests/test_provider_conformance.py::test_an_unsupported_capability_is_declared_not_simulated",
    ),
    "coverwrap_detectors": (
        "the cover-wrap detectors fire on their fixtures",
        Stage.DEFAULT,
        "src/press/selftest.py::check_coverwrap_detectors",
    ),
    "aesthetic_schema": (
        "the aesthetic schema validates",
        Stage.FAST,
        "src/press/selftest.py::check_aesthetic_schema",
    ),
    "contract_mirror": (
        "the action.yml contract mirrors the press",
        Stage.FAST,
        "tests/test_selftest_checks.py::test_contract_mirror_names_drift_between_agent_instructions",
    ),
    "migration": (
        "the migration path is sound",
        Stage.DEFAULT,
        "tests/test_migrate.py::test_apply_then_rollback_is_exact",
    ),
    "extension_conformance": (
        "extensions conform to the contract",
        Stage.FAST,
        "src/press/data/extensions/hostile/collision.yaml",
    ),
    "command_catalog": (
        "the command catalogue is complete and parity-clean",
        Stage.FAST,
        "tests/test_catalog.py::test_every_catalog_command_is_dispatchable",
    ),
    "docs": (
        "the docs suite names every target and page",
        Stage.FAST,
        "tests/test_selftest_checks.py::test_docs_check_names_a_drifted_provider_qualification_page",
    ),
}


def _wrap(name: str, title: str):
    """Adapt a press ``check_<name>()`` (raises SystemExit on failure) into a
    celebrimbor check returning a CheckResult. The body is imported lazily so
    registering this module is cheap and import-side-effect free."""

    check_id = f"press.{name}"

    def run(ctx) -> CheckResult:
        from . import selftest

        try:
            getattr(selftest, f"check_{name}")()
        except SystemExit as exc:
            message = str(exc) or f"press check_{name} failed"
            return CheckResult.failed(check_id, title, [Finding(message)])
        return CheckResult.passed(check_id, title)

    run.__name__ = f"_press_{name}"
    return run


def register() -> tuple[str, ...]:
    """Register every domain check into celebrimbor's default registry and
    return the ids, so the load has an inspectable result.

    Called at import (below) so ``check_modules`` and ``load_builtin_checks``
    see the checks the moment they import this module -- celebrimbor's one
    registration seam. Idempotent: an id already present is left alone, so the
    import-side-effect probe (which drops the module and re-imports it) and any
    test that re-runs the gate in one process do not raise
    ``DuplicateCheckError``."""

    from celebrimbor.registry import default_registry

    already = set(default_registry().ids())
    ids = []
    for name, (title, stage, falsified_by) in _DOMAIN.items():
        check_id = f"press.{name}"
        if check_id not in already:
            check(
                id=check_id,
                title=title,
                stage=stage,
                falsified_by=falsified_by,
            )(_wrap(name, title))
        ids.append(check_id)
    return tuple(ids)


register()
