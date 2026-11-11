from datetime import datetime
from enum import StrEnum
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from app.core.time import utcnow


class DietaryRestriction(StrEnum):
    """Strict: enforced by our own rules, never left to the LLM alone."""

    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    GLUTEN_FREE = "gluten_free"
    DAIRY_FREE = "dairy_free"
    HALAL = "halal"
    KOSHER = "kosher"
    CARNIVORE = "carnivore"  # meat, poultry, seafood, eggs and dairy only


class Allergen(StrEnum):
    """Strict. The 14 EU allergens, named after Open Food Facts' tags so each maps
    straight onto one: SESAME_SEEDS <-> "en:sesame-seeds" (see off_tag)."""

    GLUTEN = "gluten"
    CRUSTACEANS = "crustaceans"
    EGGS = "eggs"
    FISH = "fish"
    PEANUTS = "peanuts"
    SOYBEANS = "soybeans"
    MILK = "milk"
    NUTS = "nuts"  # tree nuts
    CELERY = "celery"
    MUSTARD = "mustard"
    SESAME_SEEDS = "sesame_seeds"
    SULPHITES = "sulphur_dioxide_and_sulphites"
    LUPIN = "lupin"
    MOLLUSCS = "molluscs"

    @property
    def off_tag(self) -> str:
        return "en:" + self.value.replace("_", "-")


class PreferredDiet(StrEnum):
    """Loose: passed to the LLM as a preference, not rule-checked."""

    KETO = "keto"
    LOW_CARB = "low_carb"
    HIGH_PROTEIN = "high_protein"
    LOW_SODIUM = "low_sodium"


class DietaryProfile(SQLModel, table=True):
    """One per user. No row means no restrictions or preferences.

    The lists are JSON arrays of the enum values above. Values are validated by the
    API schemas, so adding an option later is a code change with no migration.
    """

    __tablename__ = "dietary_profiles"

    # Users live in Supabase's auth schema, so no foreign key (same as items.user_id).
    user_id: UUID = Field(primary_key=True)
    restrictions: list[DietaryRestriction] = Field(default_factory=list, sa_type=sa.JSON)
    allergens: list[Allergen] = Field(default_factory=list, sa_type=sa.JSON)
    preferred_diets: list[PreferredDiet] = Field(default_factory=list, sa_type=sa.JSON)
    # Free text for the recipe prompt, e.g. "no mushrooms, not too spicy". Capped to keep
    # prompts short; it is user input, so the prompt must treat it as data.
    dislikes: str | None = Field(default=None, max_length=300)
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))
