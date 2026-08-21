"""Database engine, sessions, and readiness checks."""

from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings

log = structlog.get_logger()
settings = get_settings()


def build_engine_options(database_url: str, *, debug: bool) -> dict[str, Any]:
    """Return driver-specific SQLAlchemy options without leaking credentials."""
    options: dict[str, Any] = {"echo": debug}
    if database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    elif database_url.startswith("mysql"):
        options["pool_pre_ping"] = True
        options["pool_recycle"] = 300
        options["pool_size"] = 3
        options["max_overflow"] = 2
        options["pool_timeout"] = 10
        options["connect_args"] = {
            "connect_timeout": 5,
            "charset": "utf8mb4",
        }
    return options


engine = create_engine(
    settings.database_url,
    **build_engine_options(settings.database_url, debug=settings.debug),
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def init_db() -> None:
    """Create tables only for local/test SQLite; deployed environments use Alembic."""
    import app.models  # noqa: F401

    if settings.database_backend == "cloudbase_rest":
        return
    if settings.environment.lower() in {"dev", "development", "test"}:
        SQLModel.metadata.create_all(engine)


def check_database() -> bool:
    """Run the smallest useful readiness query; never expose a DSN or DB error."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        log.exception("database_readiness_failed")
        return False
