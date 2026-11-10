from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app


def test_health_returns_ok() -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_version="9.9.9", environment="test"
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "9.9.9", "environment": "test"}
