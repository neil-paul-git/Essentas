from fastapi import APIRouter

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.dietary_profile import DietaryProfileRead, DietaryProfileUpdate
from app.services import dietary_profiles as profiles_service

router = APIRouter(prefix="/me/dietary-profile", tags=["users"])


@router.get("", response_model=DietaryProfileRead)
def read_dietary_profile(user: CurrentUserDep, session: SessionDep) -> DietaryProfileRead:
    """The caller's diet and allergies. Empty (never 404) if they haven't saved one."""
    return profiles_service.get_profile(session, user.id)


@router.put("", response_model=DietaryProfileRead)
def replace_dietary_profile(
    data: DietaryProfileUpdate, user: CurrentUserDep, session: SessionDep
) -> DietaryProfileRead:
    """Replace the whole profile. Send every field; an omitted one is cleared."""
    return profiles_service.replace_profile(session, user.id, data)
