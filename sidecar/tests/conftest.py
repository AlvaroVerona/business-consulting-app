import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_business_consulting.db")

import pytest  # noqa: E402

import src.storage as storage_module  # noqa: E402
from src.database import models  # noqa: E402,F401
from src.database.database import Base, SessionLocal, engine  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    """Without this, save_upload() writes into the real sidecar/data/ dev
    directory — the DB is reset per test (_clean_db above), but on-disk
    files weren't, so uploads from dozens of test functions (many creating
    "project 1" again and again, since _clean_db resets autoincrement each
    time) all landed in the same real sidecar/data/1/ directory. Harmless
    while save_upload silently overwrote same-named files; became a real
    problem once it started disambiguating collisions instead — a live
    developer's actual project data started sharing a folder with test
    debris, and a test's expected exact filename could depend on unrelated
    tests' execution order. tmp_path is a fresh, pytest-managed directory
    per test, auto-cleaned afterward."""
    monkeypatch.setattr(storage_module, "DATA_DIR", tmp_path / "data")


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
