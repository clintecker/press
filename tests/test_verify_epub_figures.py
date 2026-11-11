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


def test_numbered_figure_count_walks_the_files_the_build_typesets(tmp_path, monkeypatch):
    ch = tmp_path / "book" / "chapters"
    ap = tmp_path / "book" / "appendices"
    ch.mkdir(parents=True)
    ap.mkdir(parents=True)
    fig = "![A map](b.png){.map #m1}\n"
    (ch / "01-one.md").write_text("# One\n\n" + fig)
    (ch / "_draft.md").write_text(fig)
    (ap / "notes.md").write_text(fig)
    (ap / "a-glossary.md").write_text("# Glossary\n\n" + fig)
    monkeypatch.setattr(vf.booklib, "root", lambda: tmp_path)
    assert vf.numbered_figure_count(tmp_path) == 2


def test_chapter_zero_label_counts():
    assert vf.require_figure_labels("Figure 1. A map.", 1, "HTML") is None
