"""The jargon parity contract: the package checker and the portable skill
copy must agree.

Two byte-for-byte implementations of the jargon checker ship in this repo:
``src/press/jargon_lint.py`` (run by ``press check`` through
``python -m press.jargon_lint``) and the portable copy under
``src/press/data/skills/overused-jargon/scripts/jargon_lint.py`` that an
author or agent runs standalone, without importing the package. They share
only ``references/watchlist.csv``. Nothing but this suite proves they parse,
normalize, match word boundaries, honour the allowlist, and report
identically.

This closes the drift two ways. ``check_jargon_parity`` in the selftest
compares the two sources function by function (the definitive guarantee:
identical shared logic means identical behaviour) and proves both default to
the same watchlist. Here we add the behavioural evidence: a versioned
fixture/contract corpus (``tests/corpus/jargon_parity/``) plus the shipped
known-bad fixtures plus a differential property fuzz, every case driven
through BOTH implementations with identical findings, exit codes, and
refusal messages asserted. A mismatch the fuzzer finds is minimized and
stored under ``corpus/jargon_parity/seeds/`` as a permanent regression case.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from press import yamlio


REPO = Path(__file__).resolve().parent.parent
CORPUS = Path(__file__).resolve().parent / "corpus" / "jargon_parity"
SEEDS = CORPUS / "seeds"
KNOWN_BAD = REPO / "src" / "press" / "data" / "known-bad"
SKILL_COPY = (
    REPO / "src" / "press" / "data" / "skills" / "overused-jargon" / "scripts" / "jargon_lint.py"
)


def _load_skill_copy() -> ModuleType:
    """Load the portable jargon checker directly from its file, the way an
    author running the standalone skill would -- no press package import."""

    spec = importlib.util.spec_from_file_location("jargon_lint_skill", SKILL_COPY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before executing so the module's frozen-annotation dataclasses
    # can resolve their own module via sys.modules, exactly as a standalone run
    # of the script would.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _package_copy() -> ModuleType:
    from press import jargon_lint

    return jargon_lint


PACKAGE_IMPL = _package_copy()
SKILL_IMPL = _load_skill_copy()
BOTH = [("package", PACKAGE_IMPL), ("skill", SKILL_IMPL)]


def _run(impl: ModuleType, argv: list[str]) -> tuple[int, str, str]:
    """Run one checker's main() and capture (exit code, stdout, stderr)."""

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = impl.main(argv)
    return code, out.getvalue(), err.getvalue()


def _both(argv: list[str]) -> tuple[tuple[int, str, str], tuple[int, str, str]]:
    return _run(PACKAGE_IMPL, argv), _run(SKILL_IMPL, argv)


def _cases() -> list[dict]:
    data = yamlio.loads((CORPUS / "cases.yaml").read_text(encoding="utf-8"))
    return data["cases"]


def _argv_for(case: dict) -> list[str]:
    argv = ["--json"]
    watchlist = case.get("watchlist", "default")
    if watchlist != "default":
        argv += ["--watchlist", str(CORPUS / watchlist)]
    for term in case.get("allow", []):
        argv += ["--allow", term]
    argv += ["--fail-on", case.get("fail_on", "rewrite")]
    if case.get("include_quotes"):
        argv += ["--include-quotes"]
    argv += [str(CORPUS / case["input"])]
    return argv


# --------------------------------------------------------------------------
# The corpus is a shared contract, and it is versioned.
# --------------------------------------------------------------------------


@pytest.mark.invariant("INV-editorial-jargon-parity")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_corpus_is_versioned() -> None:
    """The VERSION file and the manifest agree, so a book pinning an older
    press can tell when the contract moved."""

    version = (CORPUS / "VERSION").read_text(encoding="utf-8").strip()
    manifest = yamlio.loads((CORPUS / "cases.yaml").read_text(encoding="utf-8"))
    assert str(manifest["version"]) == version


# --------------------------------------------------------------------------
# Source and configuration parity (mirrors the selftest guarantee).
# --------------------------------------------------------------------------


@pytest.mark.invariant("INV-editorial-jargon-parity")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_status_level_tables_match() -> None:
    assert PACKAGE_IMPL.STATUS_LEVEL == SKILL_IMPL.STATUS_LEVEL


@pytest.mark.invariant("INV-editorial-jargon-parity")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_default_watchlist_is_the_same_file() -> None:
    """Identical matching code still diverges if the two copies read
    different watchlists; they must resolve the same default file and the
    same rule set."""

    pkg_default = PACKAGE_IMPL.parse_args([]).watchlist.resolve()
    skill_default = SKILL_IMPL.parse_args([]).watchlist.resolve()
    assert pkg_default == skill_default

    # The two Rule dataclasses live in different module namespaces, so compare
    # by field values rather than by cross-class dataclass equality.
    import dataclasses

    pkg_rules = [dataclasses.astuple(r) for r in PACKAGE_IMPL.load_rules(pkg_default)]
    skill_rules = [dataclasses.astuple(r) for r in SKILL_IMPL.load_rules(skill_default)]
    assert pkg_rules == skill_rules


@pytest.mark.invariant("INV-editorial-jargon-parity")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
def test_shared_logic_is_byte_identical() -> None:
    """Every top-level definition except parse_args (whose only sanctioned
    difference is default-watchlist resolution) is identical between the two
    copies. A logic change to only one surface fails here."""

    import ast

    def shared_defs(source: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for node in ast.parse(source).body:
            named = isinstance(node, (ast.FunctionDef, ast.ClassDef))
            if named and node.name != "parse_args":
                out[node.name] = ast.get_source_segment(source, node) or ""
        return out

    pkg = shared_defs(Path(PACKAGE_IMPL.__file__).read_text(encoding="utf-8"))
    skill = shared_defs(SKILL_COPY.read_text(encoding="utf-8"))
    assert pkg.keys() == skill.keys()
    drifted = sorted(name for name in pkg if pkg[name] != skill[name])
    assert not drifted, f"jargon logic drifted in: {drifted}"


@pytest.mark.invariant("INV-editorial-jargon-parity")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_portable_skill_does_not_import_the_package() -> None:
    """The standalone skill stays usable without press on the path."""

    source = SKILL_COPY.read_text(encoding="utf-8")
    for forbidden in ("from . import", "import press", "from press "):
        assert forbidden not in source


# --------------------------------------------------------------------------
# Behavioural parity across the versioned corpus.
# --------------------------------------------------------------------------


@pytest.mark.invariant("INV-editorial-jargon-parity")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["id"])
def test_corpus_case_agrees(case: dict) -> None:
    """Both checkers produce identical findings, exit codes, and refusal
    messages for every corpus case: matching, normalization, allowlist,
    non-prose stripping, the regex path, and malformed watchlists."""

    argv = _argv_for(case)
    (pkg_code, pkg_out, pkg_err), (skill_code, skill_out, skill_err) = _both(argv)

    assert pkg_code == skill_code
    assert pkg_out == skill_out
    assert pkg_err == skill_err

    if case.get("expect_error"):
        assert pkg_code == 2
        assert "jargon_lint:" in pkg_err
        assert pkg_out == ""
    else:
        # A real, parseable finding list -- stable rule identity and file/line.
        findings = json.loads(pkg_out)
        assert isinstance(findings, list)
        for finding in findings:
            assert set(finding) >= {"path", "line", "column", "term", "status"}


@pytest.mark.invariant("INV-editorial-jargon-parity")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
def test_corpus_exercises_real_findings() -> None:
    """The corpus is not vacuously equal: at least one case yields findings
    from both checkers, and one silences a term through the allowlist."""

    loud = _argv_for({"input": "inputs/mixed-severity.md", "fail_on": "rewrite"})
    _, pkg_out, _ = _run(PACKAGE_IMPL, loud)
    _, skill_out, _ = _run(SKILL_IMPL, loud)
    assert json.loads(pkg_out) == json.loads(skill_out)
    assert len(json.loads(pkg_out)) >= 3

    allowed = _argv_for({"input": "inputs/allowlist-scenario.md", "allow": ["drift", "parity"]})
    _, allowed_out, _ = _run(PACKAGE_IMPL, allowed)
    terms = {f["term"].lower() for f in json.loads(allowed_out)}
    assert "drift" not in terms and "parity" not in terms


@pytest.mark.invariant("INV-editorial-jargon-parity")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
@pytest.mark.parametrize("fixture", sorted(KNOWN_BAD.glob("*.md")), ids=lambda p: p.name)
def test_shipped_known_bad_fixtures_agree(fixture: Path) -> None:
    """The known-bad fixtures press check already runs through the package
    checker score identically through the portable skill copy."""

    argv = ["--json", str(fixture)]
    (pkg_code, pkg_out, pkg_err), (skill_code, skill_out, skill_err) = _both(argv)
    assert (pkg_code, pkg_out, pkg_err) == (skill_code, skill_out, skill_err)


# --------------------------------------------------------------------------
# Stored differential seeds: any input that once diverged is replayed forever.
# --------------------------------------------------------------------------


@pytest.mark.invariant("INV-editorial-jargon-parity")
@pytest.mark.layer("unit")
@pytest.mark.proof("positive")
@pytest.mark.parametrize("seed", sorted(SEEDS.glob("*.md")), ids=lambda p: p.name)
def test_stored_seeds_agree(seed: Path) -> None:
    """A stored mismatch seed must now score identically through both
    checkers (the drift it caught stays fixed)."""

    argv = ["--json", str(seed)]
    (pkg_code, pkg_out, _), (skill_code, skill_out, _) = _both(argv)
    assert (pkg_code, pkg_out) == (skill_code, skill_out)


# --------------------------------------------------------------------------
# Differential property fuzz: generated text must score identically, and a
# mismatch is minimized and stored as a permanent seed.
# --------------------------------------------------------------------------

# A vocabulary that mixes watched terms, their near-misses, unicode letters,
# and the markdown constructs strip_nonprose must hide, so the boundary,
# allowlist, and stripping paths are all reachable by the generator.
_WORDS = [
    "seam",
    "seams",
    "seamless",
    "gate",
    "gateway",
    "gating",
    "load-bearing",
    "overload-bearing",
    "blast radius",
    "drift",
    "parity",
    "surface",
    "clean",
    "ship",
    "shipped",
    "substrate",
    "café",
    "señor",
    "élite",
    "the",
    "and",
    "a",
    "wall",
    " ",
    "`",
    ">",
    "-",
    "https://example.com/gate",
]
_token = st.sampled_from(_WORDS)
_line = st.lists(_token, min_size=0, max_size=12).map(" ".join)
_text = st.lists(_line, min_size=1, max_size=8).map("\n".join)


@pytest.mark.invariant("INV-editorial-jargon-parity")
@pytest.mark.layer("unit")
@pytest.mark.proof("negative")
@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(body=_text, allow=st.lists(st.sampled_from(_WORDS), max_size=3))
def test_differential_fuzz_agrees(body: str, allow: list[str], tmp_path_factory) -> None:
    """Random prose scores identically through both checkers. A divergence is
    minimized by hypothesis, written under corpus/jargon_parity/seeds/, and
    fails the run so it becomes a permanent regression case."""

    scratch = tmp_path_factory.mktemp("jargon-fuzz")
    target = scratch / "input.md"
    target.write_text(body, encoding="utf-8")

    argv = ["--json"]
    for term in allow:
        argv += ["--allow", term]
    argv += [str(target)]

    (pkg_code, pkg_out, pkg_err), (skill_code, skill_out, skill_err) = _both(argv)

    if (pkg_code, pkg_out, pkg_err) != (skill_code, skill_out, skill_err):
        digest = hashlib.sha256((body + "\x00" + "\x00".join(allow)).encode("utf-8")).hexdigest()[
            :16
        ]
        SEEDS.mkdir(parents=True, exist_ok=True)
        (SEEDS / f"mismatch-{digest}.md").write_text(body, encoding="utf-8")
        (SEEDS / f"mismatch-{digest}.args").write_text("\n".join(allow), encoding="utf-8")
        pytest.fail(
            "jargon checkers disagreed on generated input; stored seed "
            f"mismatch-{digest}.md (allow={allow})"
        )
