from src.database.database import Base, engine
from src.database import models  # noqa: F401  (registers models on Base.metadata)


def init_db():
    Base.metadata.create_all(bind=engine)
