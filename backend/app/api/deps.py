"""Dependencies shared by routes: who is calling, and a DB session."""

import logging
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWKClientConnectionError
from sqlmodel import Session

from app.db.session import get_session
from app.providers.auth import TokenVerifier, get_token_verifier
from app.providers.food_data import FoodDataProvider, get_food_data_provider

logger = logging.getLogger(__name__)

# auto_error=False so we return our own 401 (the default varies across FastAPI versions).
# It also adds the "Authorize" button to the /docs page.
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str | None


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
) -> CurrentUser:
    if credentials is None:
        raise _unauthorized("Not authenticated")

    try:
        claims = verifier.verify(credentials.credentials)
    except PyJWKClientConnectionError as exc:
        # We couldn't fetch Supabase's public keys: our problem, not the caller's.
        logger.warning("Could not fetch Supabase JWKS", exc_info=True)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth temporarily unavailable"
        ) from exc
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid or expired token") from exc

    try:
        user_id = UUID(claims["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise _unauthorized("Invalid token subject") from exc

    return CurrentUser(id=user_id, email=claims.get("email"))


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
SessionDep = Annotated[Session, Depends(get_session)]
FoodDataProviderDep = Annotated[FoodDataProvider, Depends(get_food_data_provider)]
