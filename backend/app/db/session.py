from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """One engine (and so one connection pool) per process, created on first use.

    pool_pre_ping checks a pooled connection before handing it out, because
    Supabase's pooler closes idle connections.
    """
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    with Session(get_engine()) as session:
        yield session
