import os
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def save_upload(project_id: int, filename: str, content: bytes) -> str:
    # Strip any directory components (e.g. "../../etc/passwd") — a client
    # controls `filename` via the multipart upload, so only the basename is
    # trustworthy as a path segment.
    safe_filename = os.path.basename(filename)
    if not safe_filename:
        raise ValueError(f"Invalid filename: {filename!r}")

    project_dir = DATA_DIR / str(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)

    path = project_dir / safe_filename
    if path.exists():
        # Two documents uploaded with the same filename to the same project
        # would otherwise silently overwrite each other on disk — found by a
        # code review of the document-preview endpoint, which made this
        # directly observable (an older document's preview started showing
        # a newer document's content, since both Document rows' storage_path
        # pointed at the one file left standing). Disambiguate with a
        # numeric suffix, same convention as Finder ("pnl.csv" -> "pnl (1).csv").
        stem, suffix = os.path.splitext(safe_filename)
        n = 1
        while path.exists():
            path = project_dir / f"{stem} ({n}){suffix}"
            n += 1

    with open(path, "wb") as f:
        f.write(content)

    return str(path)


def extension_of(filename: str) -> str:
    return os.path.splitext(filename)[1]
