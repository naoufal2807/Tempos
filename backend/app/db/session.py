from sqlmodel import SQLModel, create_engine, Session
from ..core.config import settings

engine = create_engine(settings.DATABASE_URL, echo=False)

def init_db() -> None:
    from . import models  # noqa: F401
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
