

def test_plate_files_counts_both_jpeg_and_png(tmp_path):
    """A plate is a JPEG or a lossless PNG -- `press art enhance` produces
    quantized PNG -- so the pipeline must count either. Before this, the
    woodcut count globbed *.jpg only, so a book whose plates were enhanced to
    PNG silently lost its List of Plates and its plate verification."""

    from press import booklib

    woodcuts = tmp_path / "woodcuts"
    woodcuts.mkdir()
    (woodcuts / "b-plate.png").write_bytes(b"x")
    (woodcuts / "a-plate.jpg").write_bytes(b"x")
    (woodcuts / "notes.txt").write_text("not a plate")

    found = booklib.plate_files(woodcuts)
    assert [p.name for p in found] == ["a-plate.jpg", "b-plate.png"]  # both, sorted


def test_plate_files_empty_dir_is_empty(tmp_path):
    from press import booklib

    woodcuts = tmp_path / "woodcuts"
    woodcuts.mkdir()
    assert booklib.plate_files(woodcuts) == []
