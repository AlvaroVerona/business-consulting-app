from pathlib import Path

import pytest

from src.storage import DATA_DIR, save_upload


def test_save_upload_writes_inside_project_dir():
    path = Path(save_upload(1, "pnl.csv", b"month,revenue\n"))

    assert path == DATA_DIR / "1" / "pnl.csv"
    path.unlink()


def test_save_upload_strips_path_traversal_in_filename():
    path = Path(save_upload(1, "../../../../tmp/evil.txt", b"payload"))

    assert DATA_DIR.resolve() in path.resolve().parents
    assert path.name == "evil.txt"
    path.unlink()


def test_save_upload_rejects_filename_that_is_only_traversal():
    with pytest.raises(ValueError):
        save_upload(1, "../../../../", b"payload")
