"""Engine and session factories."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import get_settings


def build_engine(url: URL | str | None = None) -> Engine:
    return create_engine(url or get_settings().database_url(), pool_pre_ping=True)


@lru_cache
def get_engine() -> Engine:
    return build_engine()


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one read-only session per request."""
    with _session_factory()() as session:
        yield session
