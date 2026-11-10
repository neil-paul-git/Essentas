import os
import time
from collections.abc import Callable, Iterator
from typing import Any
from uuid import UUID, uuid4

# Set before any app module builds Settings (app.main creates the app at import).
# These override real values in the shell or backend/.env, so tests never touch Supabase.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SUPABASE_URL"] = "https://test-project.supabase.co"
# ".invalid" never resolves, so a provider accidentally left un-mocked fails fast.
os.environ["OFF_BASE_URL"] = "https://off.invalid"

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

import app.models  # noqa: E402, F401  (registers tables for create_all)
from app.core.config import Settings  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import create_app  # noqa: E402
from app.providers.auth import SupabaseTokenVerifier, get_token_verifier  # noqa: E402
from app.providers.food_data import (  # noqa: E402
    FoodDataUnavailableError,
    ProductData,
    get_food_data_provider,
)

TEST_ISSUER = f"{os.environ['SUPABASE_URL']}/auth/v1"
TEST_JWT_SECRET = "test-only-hs256-secret-at-least-32-bytes-long"


class FakeFoodDataProvider:
    """In-memory stand-in for Open Food Facts. Records every barcode it's asked for."""

    source = "fake"

    def __init__(self) -> None:
        self.products: dict[str, ProductData] = {}
        self.unavailable = False
        self.calls: list[str] = []

    def lookup(self, barcode: str) -> ProductData | None:
        self.calls.append(barcode)
        if self.unavailable:
            raise FoodDataUnavailableError("fake outage")
        return self.products.get(barcode)


@pytest.fixture
def food_provider() -> FakeFoodDataProvider:
    return FakeFoodDataProvider()


@pytest.fixture
def session() -> Iterator[Session]:
    """In-memory SQLite with all tables. StaticPool + check_same_thread=False let FastAPI's
    worker threads share the single in-memory connection."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(session: Session, food_provider: FakeFoodDataProvider) -> Iterator[TestClient]:
    """App wired to the test DB and fake providers, verifying tokens signed with
    TEST_JWT_SECRET."""
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_food_data_provider] = lambda: food_provider
    app.dependency_overrides[get_token_verifier] = lambda: SupabaseTokenVerifier(
        Settings(supabase_jwt_secret=TEST_JWT_SECRET)
    )
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_token() -> Callable[..., str]:
    """Build a Supabase-style access token. Keyword args override or add claims."""

    def _make_token(
        *,
        key: Any = TEST_JWT_SECRET,
        algorithm: str = "HS256",
        headers: dict[str, str] | None = None,
        **claims: Any,
    ) -> str:
        now = int(time.time())
        payload = {
            "sub": str(uuid4()),
            "aud": "authenticated",
            "iss": TEST_ISSUER,
            "role": "authenticated",
            "email": "cook@example.com",
            "iat": now,
            "exp": now + 3600,
            **claims,
        }
        return jwt.encode(payload, key, algorithm=algorithm, headers=headers)

    return _make_token


@pytest.fixture
def auth_headers(make_token: Callable[..., str]) -> Callable[..., dict[str, str]]:
    """auth_headers(user_id) -> Authorization header for that user (random user if omitted)."""

    def _auth_headers(user_id: UUID | None = None) -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(sub=str(user_id or uuid4()))}"}

    return _auth_headers
