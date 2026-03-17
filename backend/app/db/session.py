import os

from sqlalchemy import create_engine
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base

DEFAULT_DATABASE_URL = "sqlite+pysqlite:///./ai_news.db"


def _resolve_database_url() -> str:
    raw = os.getenv("DATABASE_URL")
    if raw is None:
        return DEFAULT_DATABASE_URL

    candidate = raw.strip().strip("\"'")
    if not candidate:
        return DEFAULT_DATABASE_URL

    return candidate


DATABASE_URL = _resolve_database_url()

try:
    engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
except ArgumentError:
    DATABASE_URL = DEFAULT_DATABASE_URL
    engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
_db_initialized = False


def init_db() -> None:
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    global _db_initialized
    if not _db_initialized:
        init_db()
        _db_initialized = True

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
