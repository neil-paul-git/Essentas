from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.schemas.health import DbHealthResponse, HealthResponse
from app.services.health import database_is_reachable

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """Liveness check: the process is up and serving requests. Does not touch the DB."""
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=settings.environment,
    )


@router.get(
    "/health/db",
    response_model=DbHealthResponse,
    responses={503: {"description": "Database unreachable"}},
)
def health_db(session: Annotated[Session, Depends(get_session)]) -> DbHealthResponse:
    """Readiness check: can we reach the database right now?"""
    if not database_is_reachable(session):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    return DbHealthResponse(status="ok")
