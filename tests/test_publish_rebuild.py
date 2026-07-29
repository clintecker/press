"""The retail checklist rebuilds before it blesses (the stale-artifact scar).

`press publish kdp` must never bless a file merely because it exists on
disk: verify_retail rebuilds each retail artifact through the registry and
runs its own verifier, and a verifier that refuses leaves the box unchecked
and turns the command's exit nonzero. This proves the rebuild happens, that
a failing verifier is recorded as unblessed, and that main fails closed.
"""

from __future__ import annotations


def _valid_cover(path):
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), "white").save(path, "JPEG")


def test_verify_retail_rebuilds_before_bless_and_main_fails_on_a_bad_verifier(
    tmp_path, monkeypatch
):
    from tests import factories

    from press import publish, registry, verify_coverwrap, verify_formats, verify_pdf

    handle = factories.minimal().build(tmp_path)
    _valid_cover(handle.root / "assets" / "cover.jpg")

    built: list[str] = []
    monkeypatch.setattr(registry, "build", lambda name: built.append(name))
    # The interior verifier refuses; every other artifact's verifier passes,
    # so the run fails on the interior alone -- not on incidental noise.
    monkeypatch.setattr(verify_pdf, "main", lambda argv: 1)
    monkeypatch.setattr(verify_coverwrap, "main", lambda: None)
    monkeypatch.setattr(verify_formats, "verify_epub", lambda path: None)

    with handle.use():
        results = publish.verify_retail()

        # (a) The interior was REBUILT through the registry before any verdict:
        # rebuild-before-bless. Drop the registry.build("print") call and this
        # is the assertion that goes red.
        assert "print" in built

        # (b) The failing verifier leaves the interior unblessed (box unchecked),
        # carrying the refusal as its note -- never a silent pass on a stale file.
        interior_label = next(label for label in results if label.startswith("Print interior"))
        passed, _path, note = results[interior_label]
        assert passed is False
        assert "print verification" in note

        # (c) main fails closed: any unverified artifact and not report_only -> 1.
        assert publish.main("kdp", report_only=False) == 1
