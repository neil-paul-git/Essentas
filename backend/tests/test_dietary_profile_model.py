"""The dietary_profiles table (no endpoints yet)."""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.dietary_profile import Allergen, DietaryProfile, DietaryRestriction, PreferredDiet

# Open Food Facts' tags for the 14 EU allergens, as they appear in allergens_tags.
OFF_ALLERGEN_TAGS = {
    "en:gluten", "en:crustaceans", "en:eggs", "en:fish", "en:peanuts", "en:soybeans",
    "en:milk", "en:nuts", "en:celery", "en:mustard", "en:sesame-seeds",
    "en:sulphur-dioxide-and-sulphites", "en:lupin", "en:molluscs",
}  # fmt: skip


def test_new_profile_is_empty(session) -> None:
    user_id = uuid4()
    session.add(DietaryProfile(user_id=user_id))
    session.commit()
    session.expire_all()

    profile = session.get(DietaryProfile, user_id)

    assert profile is not None
    assert profile.restrictions == profile.allergens == profile.preferred_diets == []
    assert profile.dislikes is None


def test_lists_and_dislikes_round_trip(session) -> None:
    user_id = uuid4()
    session.add(
        DietaryProfile(
            user_id=user_id,
            restrictions=[DietaryRestriction.VEGAN, DietaryRestriction.GLUTEN_FREE],
            allergens=[Allergen.PEANUTS, Allergen.SESAME_SEEDS],
            preferred_diets=[PreferredDiet.HIGH_PROTEIN],
            dislikes="no mushrooms, not too spicy",
        )
    )
    session.commit()
    session.expire_all()  # reload from the DB, not the in-memory object

    profile = session.get(DietaryProfile, user_id)

    assert profile is not None
    # JSON stores plain strings; StrEnum members compare equal to them.
    assert profile.restrictions == ["vegan", "gluten_free"]
    assert profile.allergens == ["peanuts", "sesame_seeds"]
    assert profile.preferred_diets == ["high_protein"]
    assert profile.dislikes == "no mushrooms, not too spicy"


def test_one_profile_per_user(session) -> None:
    user_id = uuid4()
    session.add(DietaryProfile(user_id=user_id))
    session.commit()
    session.expunge_all()  # otherwise the session itself rejects the duplicate

    session.add(DietaryProfile(user_id=user_id))
    with pytest.raises(IntegrityError):
        session.commit()


def test_every_allergen_maps_to_an_off_tag() -> None:
    assert {allergen.off_tag for allergen in Allergen} == OFF_ALLERGEN_TAGS
