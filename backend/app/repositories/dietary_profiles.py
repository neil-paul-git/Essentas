from uuid import UUID

from sqlmodel import Session

from app.models.dietary_profile import DietaryProfile


def get(session: Session, user_id: UUID) -> DietaryProfile | None:
    return session.get(DietaryProfile, user_id)


def save(session: Session, profile: DietaryProfile) -> DietaryProfile:
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile
