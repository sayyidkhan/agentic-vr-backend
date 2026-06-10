from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
CURRENT_SCHEMA_REVISION = "20260610_0005"
MANAGED_TABLES = {"scenes", "characters", "conversation_turns", "research_contexts", "character_sessions", "videos"}

is_sqlite = settings.database_url.startswith("sqlite")

if settings.database_url.startswith("sqlite:///"):
    sqlite_path = settings.database_url.replace("sqlite:///", "", 1)
    if sqlite_path != ":memory:":
        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if is_sqlite else {"connect_timeout": 5}
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=not is_sqlite,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    from app.models import db  # noqa: F401

    # MVP deploys currently rely on SQLAlchemy metadata creation during startup.
    # This keeps additive schema changes usable even before a full migration runner
    # is wired into the container startup path.
    Base.metadata.create_all(bind=engine)
    _ensure_additive_schema()
    _stamp_current_revision()


def _ensure_additive_schema() -> None:
    inspector = inspect(engine)
    if "videos" not in inspector.get_table_names():
        return

    video_columns = {column["name"] for column in inspector.get_columns("videos")}
    statements = []
    if "description" not in video_columns:
        statements.append("ALTER TABLE videos ADD COLUMN description TEXT")
    if "thumbnail_url" not in video_columns:
        statements.append("ALTER TABLE videos ADD COLUMN thumbnail_url TEXT")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


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
