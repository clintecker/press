import pytest

from press import verify_formats as vf


def test_labels_present_passes():
    assert vf.require_figure_labels("Figure 1.1. A map. Figure 1.2. A chart.", 2, "EPUB") is None


def test_missing_label_is_named():
    with pytest.raises(SystemExit) as e:
        vf.require_figure_labels("Figure 1.1. A map.", 2, "EPUB")
    assert "EPUB" in str(e.value) and "2" in str(e.value) and "1" in str(e.value)


def test_zero_numbered_figures_is_a_no_op():
    assert vf.require_figure_labels("no figures here", 0, "EPUB") is None


def test_numbered_figure_count_counts_only_informative_kinds(tmp_path, monkeypatch):
    ch = tmp_path / "book" / "chapters"
    ch.mkdir(parents=True)
    (ch / "01.md").write_text(
        "![A plate](a.png)\n\n![A map](b.png){.map #m1}\n\n![A chart](c.png){.chart}\n"
    )
    monkeypatch.setattr(vf.booklib, "root", lambda: tmp_path)
    assert vf.numbered_figure_count(tmp_path) == 2
