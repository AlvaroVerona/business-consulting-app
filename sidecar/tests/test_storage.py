from pathlib import Path

import pytest

import src.storage as storage_module
from src.storage import save_upload

# Imported as a module reference, not `from src.storage import DATA_DIR` —
# that would bind this name at collection time, before the _isolated_data_dir
# autouse fixture (conftest.py) monkeypatches storage_module.DATA_DIR for
# the test, leaving these assertions comparing against the wrong (real,
# pre-patch) directory.


def test_save_upload_writes_inside_project_dir():
    path = Path(save_upload(1, "pnl.csv", b"month,revenue\n"))

    assert path == storage_module.DATA_DIR / "1" / "pnl.csv"
    path.unlink()


def test_save_upload_strips_path_traversal_in_filename():
    path = Path(save_upload(1, "../../../../tmp/evil.txt", b"payload"))

    assert storage_module.DATA_DIR.resolve() in path.resolve().parents
    assert path.name == "evil.txt"
    path.unlink()


def test_save_upload_rejects_filename_that_is_only_traversal():
    with pytest.raises(ValueError):
        save_upload(1, "../../../../", b"payload")


def test_save_upload_disambiguates_same_filename_in_the_same_project():
    """Regression: without this, a second upload with the same filename
    silently overwrote the first on disk — found live via the document
    preview endpoint, which made an older document start showing a newer
    document's content once both Document rows pointed at the one file
    left standing."""
    path1 = Path(save_upload(2, "pnl.csv", b"first"))
    path2 = Path(save_upload(2, "pnl.csv", b"second"))

    assert path1 != path2
    assert path1.read_bytes() == b"first"
    assert path2.read_bytes() == b"second"
    assert path2.name == "pnl (1).csv"

    path1.unlink()
    path2.unlink()


def test_save_upload_disambiguation_handles_repeated_collisions():
    path1 = Path(save_upload(3, "notes.md", b"a"))
    path2 = Path(save_upload(3, "notes.md", b"b"))
    path3 = Path(save_upload(3, "notes.md", b"c"))

    assert {path1.name, path2.name, path3.name} == {"notes.md", "notes (1).md", "notes (2).md"}
    for path, content in zip([path1, path2, path3], [b"a", b"b", b"c"]):
        assert path.read_bytes() == content
        path.unlink()
