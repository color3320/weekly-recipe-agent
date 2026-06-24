"""Typed recipe records for MongoDB load."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class RecipeDocument:
    _id: int
    display_name: str
    original_name: str
    cuisine: str
    cuisine_group: str
    course: str
    meal_slot: str | None
    is_main: bool
    diet: str
    is_veg: bool
    prep_min: int
    cook_min: int
    total_min: int
    effort_bucket: str
    servings: int
    ingredients: list[str]
    instructions: str
    embed_text: str

    def to_mongo(self) -> dict:
        return asdict(self)
