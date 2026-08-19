import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_business_consulting.db")

import pytest  # noqa: E402

from src.database import models  # noqa: E402,F401
from src.database.database import Base, SessionLocal, engine  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
