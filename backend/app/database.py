from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
CURRENT_SCHEMA_REVISION = "20260609_0002"
MANAGED_TABLES = {"scenes", "characters", "conversation_turns", "research_contexts", "character_sessions"}

if settings.database_url.startswith("sqlite:///"):
    sqlite_path = settings.database_url.replace("sqlite:///", "", 1)
    if sqlite_path != ":memory:":
        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    from app.models import db  # noqa: F401

    # MVP deploys currently rely on SQLAlchemy metadata creation during startup.
    # This keeps additive schema changes usable even before a full migration runner
    # is wired into the container startup path.
    Base.metadata.create_all(bind=engine)
    _stamp_current_revision()


def _stamp_current_revision() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS alembic_version (
                    version_num VARCHAR(32) NOT NULL PRIMARY KEY
                )
                """
            )
        )
        version = connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar_one_or_none()
        if version is None:
            connection.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:version_num)"),
                {"version_num": CURRENT_SCHEMA_REVISION},
            )
        elif version != CURRENT_SCHEMA_REVISION:
            connection.execute(
                text("UPDATE alembic_version SET version_num = :version_num"),
                {"version_num": CURRENT_SCHEMA_REVISION},
            )


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
