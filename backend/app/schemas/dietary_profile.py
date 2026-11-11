from datetime import datetime
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models.dietary_profile import Allergen, DietaryRestriction, PreferredDiet

# Far more than any real profile needs; only stops absurdly large bodies.
_MAX_LIST = 20
Dislikes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]

# Restrictions that can't both hold: carnivore means animal products only.
_CONFLICTS = [
    {DietaryRestriction.CARNIVORE, DietaryRestriction.VEGAN},
    {DietaryRestriction.CARNIVORE, DietaryRestriction.VEGETARIAN},
]


class DietaryProfileUpdate(BaseModel):
    """PUT body: replaces the whole profile, so an omitted field is cleared."""

    model_config = ConfigDict(extra="forbid")

    restrictions: list[DietaryRestriction] = Field(default_factory=list, max_length=_MAX_LIST)
    allergens: list[Allergen] = Field(default_factory=list, max_length=_MAX_LIST)
    preferred_diets: list[PreferredDiet] = Field(default_factory=list, max_length=_MAX_LIST)
    # Free text for the recipe LLM, e.g. "no mushrooms, not too spicy".
    dislikes: Dislikes | None = None

    @field_validator("restrictions", "allergens", "preferred_diets")
    @classmethod
    def _dedupe(cls, values: list) -> list:
        return list(dict.fromkeys(values))  # keeps the first-seen order

    @field_validator("dislikes")
    @classmethod
    def _tidy_dislikes(cls, value: str | None) -> str | None:
        # Collapse newlines and runs of spaces: the text goes into an LLM prompt, and a
        # single line can't pretend to be a new section of it. "" means "none".
        if value is None:
            return None
        return " ".join(value.split()) or None

    @model_validator(mode="after")
    def _no_conflicts(self) -> Self:
        chosen = set(self.restrictions)
        for pair in _CONFLICTS:
            if pair <= chosen:
                a, b = sorted(pair)
                raise ValueError(f"{a} and {b} can't be combined")
        return self


class DietaryProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    restrictions: list[DietaryRestriction]
    allergens: list[Allergen]
    preferred_diets: list[PreferredDiet]
    dislikes: str | None
    updated_at: datetime | None  # None until the user first saves a profile
