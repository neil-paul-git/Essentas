"""A user's dietary profile. No row means an empty profile, so nothing is set up at signup."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.core.time import utcnow
from app.models.dietary_profile import DietaryProfile
from app.repositories import dietary_profiles as profiles_repo
from app.schemas.dietary_profile import DietaryProfileRead, DietaryProfileUpdate


def get_profile(session: Session, user_id: UUID) -> DietaryProfileRead:
    profile = profiles_repo.get(session, user_id)
    if profile is None:
        return DietaryProfileRead(
            restrictions=[], allergens=[], preferred_diets=[], dislikes=None, updated_at=None
        )
    return DietaryProfileRead.model_validate(profile)


def replace_profile(
    session: Session, user_id: UUID, data: DietaryProfileUpdate
) -> DietaryProfileRead:
    profile = profiles_repo.get(session, user_id) or DietaryProfile(user_id=user_id)
    _apply(profile, data)
    try:
        saved = profiles_repo.save(session, profile)
    except IntegrityError:
        # Two first-time saves for the same user raced and the other inserted first.
        # PUT replaces the whole profile, so applying ours on top of it is correct.
        session.rollback()
        existing = profiles_repo.get(session, user_id)
        if existing is None:
            raise
        _apply(existing, data)
        saved = profiles_repo.save(session, existing)
    return DietaryProfileRead.model_validate(saved)


def _apply(profile: DietaryProfile, data: DietaryProfileUpdate) -> None:
    profile.restrictions = list(data.restrictions)
    profile.allergens = list(data.allergens)
    profile.preferred_diets = list(data.preferred_diets)
    profile.dislikes = data.dislikes
    profile.updated_at = utcnow()
