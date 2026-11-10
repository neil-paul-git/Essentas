from fastapi import APIRouter

from app.api.deps import CurrentUserDep
from app.schemas.user import MeResponse

router = APIRouter(tags=["users"])


@router.get("/me", response_model=MeResponse)
def read_me(user: CurrentUserDep) -> MeResponse:
    """Who am I? Handy for checking that the app's login token works."""
    return MeResponse(id=user.id, email=user.email)
