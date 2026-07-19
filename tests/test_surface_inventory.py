"""The public surface is fully classified, and the gate proves it by
turning red on an unclassified callable.

The callable inventory is mechanical (AST over src/press), so no hand
list can rot; this suite proves the classification covers it and that
the gate actually fails when it should.
"""


from press import surfaces


def test_every_public_callable_is_classified():
    result = surfaces.audit()
    assert result["problems"] == [], result["problems"]


def test_no_stale_overrides_or_exemptions():
    """Config that names a callable the code no longer has is a defect;
    audit() reports it, and the shipped config must be clean."""

    result = surfaces.audit()
    stale = [p for p in result["problems"] if "no live callable" in p]
    assert stale == [], stale


def test_gate_reddens_on_unclassified_module(monkeypatch):
    """A new module with no classification must fail the audit: the
    whole point of the inventory is that a public callable cannot ship
    unclassified."""

    real = surfaces.public_callables

    def with_dummy():
        found = dict(real())
        found["brand_new_module"] = ["do_a_thing"]
        return found

    monkeypatch.setattr(surfaces, "public_callables", with_dummy)
    result = surfaces.audit()
    assert any("brand_new_module.do_a_thing" in p for p in result["problems"])


def test_missing_modules_reports_the_gap(monkeypatch):
    real = surfaces.public_callables

    def with_dummy():
        found = dict(real())
        found["unlisted"] = ["f"]
        return found

    monkeypatch.setattr(surfaces, "public_callables", with_dummy)
    assert "unlisted" in surfaces.missing_modules()


def test_exemptions_carry_reason_and_review():
    config = surfaces.load_config()
    for exemption in config.get("exemptions") or []:
        assert exemption.get("reason"), exemption
        assert exemption.get("review"), exemption
