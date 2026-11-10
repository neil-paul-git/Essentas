from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import get_settings
from app.services.errors import NotFoundError, ServiceUnavailableError


async def _not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


async def _unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": str(exc)},
        headers={"Retry-After": "60"},
    )


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.include_router(api_router, prefix="/api/v1")
    # Services raise these domain errors; the handlers turn them into HTTP responses,
    # so routes stay thin and services don't know about HTTP.
    app.add_exception_handler(NotFoundError, _not_found_handler)
    app.add_exception_handler(ServiceUnavailableError, _unavailable_handler)
    return app


app = create_app()
