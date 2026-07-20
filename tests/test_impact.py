"""The change-impact mapper derives obligations from the ledgers, and
the gate refuses a change that owes a proof it does not have.
"""

from __future__ import annotations

from press import impact


def test_verifier_change_maps_to_its_invariants():
    result = impact.analyze(["verify_pdf"])
    row = result.modules[0]
    assert row.role == "verifier"
    assert row.required
    assert row.invariants  # verify_pdf enforces real invariants
    assert not result.gaps


def test_unclassified_module_is_a_gap():
    result = impact.analyze(["a_module_that_does_not_exist"])
    assert any("not classified" in g for g in result.gaps)


def test_policy_change_with_no_invariant_is_a_gap(monkeypatch):
    # A parser with no invariant naming it owes one.
    monkeypatch.setattr(impact, "_role_of", lambda cfg, m: "parser")
    monkeypatch.setattr(impact, "_invariants_for", lambda ledger, m: ())
    result = impact.analyze(["some_parser"])
    assert any("no invariant names it" in g for g in result.gaps)


def test_pure_helper_change_owes_no_invariant(monkeypatch):
    monkeypatch.setattr(impact, "_role_of", lambda cfg, m: "pure")
    monkeypatch.setattr(impact, "_invariants_for", lambda ledger, m: ())
    result = impact.analyze(["a_pure_module"])
    # Pure code is reported but does not gate on a missing invariant.
    assert result.gaps == ()
    assert not result.modules[0].required


def test_selection_collects_invariants_across_modules():
    result = impact.analyze(["verify_pdf", "verify_pages"])
    assert len(result.selected_invariants) >= 2


def test_no_change_selects_everything():
    result = impact.analyze([])
    assert result.modules == ()
    assert "no press modules changed" in impact.render(result)


def test_render_names_role_and_invariants():
    result = impact.analyze(["package_source"])
    text = impact.render(result)
    assert "package_source" in text
    assert "INV-archive-source-policy" in text


def test_changed_modules_filters_to_press_python(monkeypatch):
    class R:
        stdout = b"src/press/verify_pdf.py\ntests/test_x.py\nsrc/press/desk/app.py\nREADME.md\n"

    monkeypatch.setattr(impact.adapters.process_runner, "run",
                        lambda *a, **k: R())
    stems = impact.changed_modules("origin/main")
    assert stems == ["verify_pdf"]  # tests/, subpackages, and docs excluded
