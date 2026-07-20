"""The selftest's invariant checks, run as individual pytest cases.

Facts once: each test calls the same check_* function the `press
selftest` CLI runs, so the two runners cannot disagree. A check that
fails raises SystemExit or AssertionError; pytest reports which
invariant broke by name instead of the CLI's first-failure exit.
"""

from __future__ import annotations

import pytest

from press import selftest


@pytest.mark.parametrize("check", selftest.CHECKS, ids=lambda c: c.__name__)
def test_invariant_check_passes(check):
    check()


def test_every_check_is_orchestrated():
    """No check_* function may escape the ordered CHECKS list that both
    the CLI and this suite run: a new invariant added to the module but
    not wired into CHECKS would prove nothing anywhere, so it fails
    here."""

    defined = {
        name for name in dir(selftest)
        if name.startswith("check_") and callable(getattr(selftest, name))
    }
    orchestrated = {check.__name__ for check in selftest.CHECKS}
    missing = sorted(defined - orchestrated)
    assert not missing, f"selftest checks not in CHECKS: {missing}"


def test_write_docs_mode_writes_all_generated_contracts(
        tmp_path, monkeypatch, capsys):
    """The documented repair command writes each generated contract from
    its canonical renderer, then runs the same ordered selftest checks."""

    package = tmp_path / "src" / "press"
    package.mkdir(parents=True)
    monkeypatch.setattr(selftest, "__file__", str(package / "selftest.py"))
    ran = []
    monkeypatch.setattr(selftest, "CHECKS", [lambda: ran.append("check")])
    monkeypatch.setattr(selftest, "modules", lambda: [])
    monkeypatch.setattr(selftest, "render_reference", lambda: "reference\n")
    monkeypatch.setattr(selftest.invariants, "render", lambda: "invariants\n")
    from press import qualification
    monkeypatch.setattr(qualification, "render", lambda: "qualification\n")

    assert selftest.main(["--write-docs"]) == 0
    docs = tmp_path / "docs"
    assert (docs / "REFERENCE.md").read_text() == "reference\n"
    assert (docs / "INVARIANTS.md").read_text() == "invariants\n"
    assert (docs / "PROVIDER-QUALIFICATION.md").read_text() == "qualification\n"
    assert ran == ["check"]
    assert "wrote" in capsys.readouterr().out


def test_checkout_only_contract_check_skips_an_installed_wheel(
        tmp_path, monkeypatch):
    package = tmp_path / "site-packages" / "press"
    package.mkdir(parents=True)
    monkeypatch.setattr(selftest, "__file__", str(package / "selftest.py"))

    assert selftest._repo_root() is None
    assert selftest.check_contract_mirror() is None

    monkeypatch.setattr(selftest.invariants, "LEDGER", tmp_path / "missing-ledger.yaml")
    assert selftest.check_invariant_ledger() is None


def test_contract_mirror_names_drift_between_agent_instructions(
        tmp_path, monkeypatch):
    package = tmp_path / "src" / "press"
    package.mkdir(parents=True)
    monkeypatch.setattr(selftest, "__file__", str(package / "selftest.py"))
    (tmp_path / "CLAUDE.md").write_text("# CLAUDE.md\ncanonical\n")
    (tmp_path / "AGENTS.md").write_text("# AGENTS.md\ndrifted\n")

    with pytest.raises(SystemExit, match="AGENTS.md has drifted"):
        selftest.check_contract_mirror()


def test_docs_check_names_a_drifted_provider_qualification_page(
        tmp_path, monkeypatch):
    package = tmp_path / "src" / "press"
    package.mkdir(parents=True)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "PROVIDER-QUALIFICATION.md").write_text("stale\n")
    monkeypatch.setattr(selftest, "__file__", str(package / "selftest.py"))
    from press import qualification
    monkeypatch.setattr(qualification, "render", lambda: "canonical\n")

    with pytest.raises(SystemExit, match="PROVIDER-QUALIFICATION.md drifted"):
        selftest.check_docs()


@pytest.mark.parametrize("slug", selftest.GOOD_SLUGS)
def test_slug_invariant_accepts_good(slug):
    from press import booklib

    assert booklib.validate_slug(slug) == slug


@pytest.mark.parametrize("slug", selftest.BAD_SLUGS)
def test_slug_invariant_rejects_bad(slug):
    from press import booklib

    with pytest.raises(SystemExit):
        booklib.validate_slug(slug)
