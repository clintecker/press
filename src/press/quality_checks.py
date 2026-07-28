"""Register press's domain quality checks with celebrimbor.

Calling :func:`register` installs every press-specific check -- the ones
celebrimbor cannot know about: editorial rules, the book model, provider
contracts, the render/PDF/EPUB verifiers -- into celebrimbor's default
registry via ``@celebrimbor.check``, so ``celebrimbor.gate()`` runs them
alongside the framework's own gates. Registration is explicit (the ``press
gate`` entry calls it), never an import side effect: merely importing this
module must not mutate the registry.

This is the registration seam only: the check *bodies* stay in their home
modules (``selftest.check_*`` delegates to ``verify_pdf``, ``jargon_lint``,
``gen_authorities``, ...). Celebrimbor's own builtin checks cover press's former
*infrastructure* checks (imports, registry, invariant ledger, fixture
provenance, producers), so those are NOT registered here -- they are retired
when press's parallel machinery is deleted.

Each registration carries an ``Unproven`` falsifier with a review date: the
check runs today, and the negative fixture that proves the gate bites is mapped
in a follow-up (the same burn-down discipline as the producer pending list).
"""

from __future__ import annotations

from celebrimbor import Unproven, check
from celebrimbor.result import CheckResult, Finding, Stage

# The press domain checks celebrimbor should run, name -> (one-line title, tier).
# The tier mirrors how heavy the check is: FAST = config/pure validation,
# DEFAULT = reads the tree or a scaffolded book, FULL = toolchain/render paths.
_DOMAIN: dict[str, tuple[str, Stage]] = {
    "arithmetic": ("the canonical examples' arithmetic agrees", Stage.FAST),
    "slug_invariant": ("book slugs stay valid and stable", Stage.FAST),
    "jargon_parity": ("the jargon lint agrees across its corpus", Stage.DEFAULT),
    "source_policy": ("the source package excludes what it must", Stage.FAST),
    "pages_verifier": ("the reader-site verifier holds its promises", Stage.DEFAULT),
    "scaffold_neutrality": ("a scaffolded book is neutral, no leaked identity", Stage.FAST),
    "book_model": ("the book model validates its config", Stage.FAST),
    "format_witnesses": ("every edition carries the manuscript witnesses", Stage.DEFAULT),
    "editions_agree": ("the editions agree on the book's content", Stage.DEFAULT),
    "editorial_checkers": ("every editorial checker rejects its known-bad", Stage.DEFAULT),
    "site_identity": ("the docs site declares its identity correctly", Stage.FAST),
    "authorities_ledger": ("the authorities ledger's claims still hold", Stage.DEFAULT),
    "honest_refusals": ("the honest-refusal fixtures are refused", Stage.FAST),
    "release_grammar": ("the release grammar is well-formed", Stage.FAST),
    "receipt_chain": ("the receipt chain verifies end to end", Stage.DEFAULT),
    "edition_manifest": ("the edition manifest is complete and consistent", Stage.FAST),
    "provider_qualification": ("providers qualify against their spec", Stage.DEFAULT),
    "profile_seals": ("every print profile matches its sealed geometry", Stage.FAST),
    "commerce_config": ("the commerce config validates", Stage.FAST),
    "commerce_release_gate": ("the commerce release gate holds", Stage.DEFAULT),
    "provider_contract": ("providers honour the neutral contract", Stage.DEFAULT),
    "coverwrap_detectors": ("the cover-wrap detectors fire on their fixtures", Stage.DEFAULT),
    "aesthetic_schema": ("the aesthetic schema validates", Stage.FAST),
    "contract_mirror": ("the action.yml contract mirrors the press", Stage.FAST),
    "migration": ("the migration path is sound", Stage.DEFAULT),
    "extension_conformance": ("extensions conform to the contract", Stage.FAST),
    "command_catalog": ("the command catalogue is complete and parity-clean", Stage.FAST),
    "docs": ("the docs suite names every target and page", Stage.FAST),
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

    Called explicitly -- from the ``press gate`` entry, not at import time.
    Registering at import would make merely importing this module mutate the
    global registry, a side effect press's own ``_prove_no_import_side_effects``
    invariant forbids (and celebrimbor's own builtins register only when
    ``load_builtin_checks`` is called, never on import). Idempotent: an id
    already present is left alone, so a second call (a test that re-runs the
    gate in one process) does not raise ``DuplicateCheckError``."""

    from celebrimbor.registry import default_registry

    already = set(default_registry().ids())
    ids = []
    for name, (title, stage) in _DOMAIN.items():
        check_id = f"press.{name}"
        if check_id not in already:
            check(
                id=check_id,
                title=title,
                stage=stage,
                falsified_by=Unproven(
                    f"press check_{name}: map the negative fixture that reddens it",
                    review_by="2027-01-01",
                ),
            )(_wrap(name, title))
        ids.append(check_id)
    return tuple(ids)
