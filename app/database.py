from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings, resolve_project_path


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str | None = None):
    url = database_url or get_settings().app_database_url
    parsed_url = make_url(url)
    if parsed_url.drivername.startswith("sqlite") and parsed_url.database not in (None, ":memory:"):
        database_path = Path(parsed_url.database)
        if not database_path.is_absolute():
            database_path = resolve_project_path(database_path)
        database_path.parent.mkdir(parents=True, exist_ok=True)

    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


engine = build_engine()
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def configure_database(database_url: str | None = None):
    global engine

    engine.dispose()
    engine = build_engine(database_url)
    SessionLocal.configure(bind=engine)
    return engine


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
