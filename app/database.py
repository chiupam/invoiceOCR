"""Database engine / session management (framework-agnostic)."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_config


class Base(DeclarativeBase):
    pass


def _make_engine():
    url = get_config().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create any missing tables.

    Race-safe for multi-worker servers: concurrent workers may both run
    CREATE TABLE on a fresh SQLite file; "already exists" errors are benign
    (the union of both workers' tables covers the full schema).
    """
    from . import models  # noqa: F401 — register tables on Base.metadata

    try:
        Base.metadata.create_all(bind=engine)
    except OperationalError as e:
        if "already exists" not in str(e):
            raise
    finally:
        # Close connections opened during bootstrap so forked workers do
        # not inherit a pooled SQLite connection.
        engine.dispose(close=False)
