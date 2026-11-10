from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.main import create_app


def test_health_returns_ok() -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_version="9.9.9", environment="test", database_url="sqlite://"
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "9.9.9", "environment": "test"}


def test_health_db_ok_when_database_reachable(session: Session) -> None:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session

    with TestClient(app) as client:
        response = client.get("/api/v1/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


class _UnreachableSession:
    """Stands in for a Session whose database is down."""

    def connection(self):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))


def test_health_db_returns_503_when_database_down() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _UnreachableSession()

    with TestClient(app) as client:
        response = client.get("/api/v1/health/db")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_database_url_is_switched_to_psycopg_driver() -> None:
    settings = Settings(database_url="postgresql://u:p@host:5432/db")
    assert settings.database_url == "postgresql+psycopg://u:p@host:5432/db"
