import os
from collections.abc import Iterator

# Set before any app module builds Settings (app.main creates the app at import).
# Overrides any real DATABASE_URL in the shell or backend/.env, so tests never touch Supabase.
os.environ["DATABASE_URL"] = "sqlite://"

import pytest  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlmodel import Session, create_engine  # noqa: E402


@pytest.fixture
def session() -> Iterator[Session]:
    """In-memory SQLite session. StaticPool + check_same_thread=False let FastAPI's
    worker threads share the single in-memory connection."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with Session(engine) as session:
        yield session
