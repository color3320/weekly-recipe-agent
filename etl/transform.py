"""Transform raw xlsx rows into typed recipe documents with validation."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from typing import Any

from etl import config
from etl.embed import build_embed_text
from etl.extract import run_extract
from etl.models import RecipeDocument

BOM_RE = re.compile(r"^\ufeff+")

# Regional / Indian cuisines in the dataset (after BOM strip on cuisine field).
INDIAN_CUISINES = frozenset(
    {
        "Indian",
        "North Indian Recipes",
        "South Indian Recipes",
        "Bengali Recipes",
        "Maharashtrian Recipes",
        "Kerala Recipes",
        "Tamil Nadu",
        "Karnataka",
        "Rajasthani",
        "Andhra",
        "Gujarati Recipes",
        "Goan Recipes",
        "Punjabi",
        "Chettinad",
        "Kashmiri",
        "Mangalorean",
        "Parsi Recipes",
        "Awadhi",
        "Oriya Recipes",
        "Sindhi",
        "Konkan",
        "Mughlai",
        "Bihari",
        "Hyderabadi",
        "Assamese",
        "North East India Recipes",
        "Himachal",
        "Udupi",
        "Coorg",
        "Coastal Karnataka",
        "North Karnataka",
        "Uttar Pradesh",
        "Lucknowi",
        "Malabar",
        "South Karnataka",
        "Malvani",
        "Uttarakhand-North Kumaon",
        "Haryana",
        "Kongunadu",
        "Jharkhand",
        "Nagaland",
    }
)

BREAKFAST_COURSES = frozenset(
    {
        "South Indian Breakfast",
        "World Breakfast",
        "North Indian Breakfast",
        "Indian Breakfast",
        "Brunch",
    }
)

COURSE_TO_SLOT: dict[str, tuple[str | None, bool]] = {
    "Lunch": ("lunch", True),
    "Dinner": ("dinner", True),
    "Main Course": ("main", True),
    "Vegetarian": (None, False),  # data error — diet comes from Diet column
}


class TransformValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"{len(errors)} validation error(s)")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value != value:  # NaN
        return ""
    text = str(value).replace("\xa0", " ").strip()
    return BOM_RE.sub("", text)


def normalize_cuisine(raw: str) -> str:
    return clean_text(raw)


def classify_cuisine_group(cuisine: str) -> str:
    if cuisine in INDIAN_CUISINES:
        return "Indian"
    return "Variety"


def course_to_meal_slot(course: str) -> tuple[str | None, bool]:
    if course in COURSE_TO_SLOT:
        return COURSE_TO_SLOT[course]
    if course in BREAKFAST_COURSES:
        return ("breakfast", False)
    slug = re.sub(r"[^a-z0-9]+", "_", course.lower()).strip("_")
    return (slug or None, False)


def is_veg_from_diet(diet: str) -> bool:
    return diet not in config.NON_VEG_DIETS


def effort_bucket(total_min: int) -> str:
    if total_min <= 30:
        return "quick"
    if total_min <= 60:
        return "medium"
    return "long"


def split_ingredients(raw: str) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def coerce_int(value: Any, *, field: str, recipe_id: int) -> int:
    if value is None or (isinstance(value, float) and value != value):
        raise ValueError(f"recipe {recipe_id}: required int field {field} is null")
    try:
        return int(float(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"recipe {recipe_id}: invalid int for {field}: {value!r}") from exc


def transform_row(row: dict[str, Any]) -> RecipeDocument:
    recipe_id = coerce_int(row.get("Srno"), field="Srno", recipe_id=-1)
    original_name = clean_text(row.get("RecipeName"))
    display_name = clean_text(row.get("TranslatedRecipeName")) or original_name
    if not display_name:
        raise ValueError(f"recipe {recipe_id}: missing display_name")

    course = clean_text(row.get("Course"))
    diet = clean_text(row.get("Diet"))
    if course not in config.VALID_COURSES:
        raise ValueError(f"recipe {recipe_id}: invalid Course {course!r}")
    if diet not in config.VALID_DIETS:
        raise ValueError(f"recipe {recipe_id}: invalid Diet {diet!r}")

    cuisine = normalize_cuisine(row.get("Cuisine"))
    cuisine_group = classify_cuisine_group(cuisine)
    meal_slot, is_main = course_to_meal_slot(course)

    ingredients_raw = clean_text(row.get("Ingredients"))
    instructions = clean_text(row.get("Instructions"))

    prep_min = coerce_int(row.get("PrepTimeInMins"), field="PrepTimeInMins", recipe_id=recipe_id)
    cook_min = coerce_int(row.get("CookTimeInMins"), field="CookTimeInMins", recipe_id=recipe_id)
    total_min = coerce_int(
        row.get("TotalTimeInMins"), field="TotalTimeInMins", recipe_id=recipe_id
    )
    servings = coerce_int(row.get("Servings"), field="Servings", recipe_id=recipe_id)

    return RecipeDocument(
        _id=recipe_id,
        display_name=display_name,
        original_name=original_name,
        cuisine=cuisine,
        cuisine_group=cuisine_group,
        course=course,
        meal_slot=meal_slot,
        is_main=is_main,
        diet=diet,
        is_veg=is_veg_from_diet(diet),
        prep_min=prep_min,
        cook_min=cook_min,
        total_min=total_min,
        effort_bucket=effort_bucket(total_min),
        servings=servings,
        ingredients=split_ingredients(ingredients_raw),
        instructions=instructions,
        embed_text=build_embed_text(display_name, cuisine, ingredients_raw),
    )


def validate_documents(docs: list[RecipeDocument]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[int] = set()

    for doc in docs:
        if doc._id in seen_ids:
            errors.append(f"duplicate _id: {doc._id}")
        seen_ids.add(doc._id)

        if not doc.display_name:
            errors.append(f"recipe {doc._id}: empty display_name")
        if not doc.embed_text:
            errors.append(f"recipe {doc._id}: empty embed_text")

    if len(docs) != config.EXPECTED_TOTAL_DOCS:
        errors.append(
            f"document count {len(docs)} != expected {config.EXPECTED_TOTAL_DOCS}"
        )

    main_count = sum(1 for d in docs if d.is_main)
    low = config.EXPECTED_MAIN_DOCS - config.MAIN_DOC_TOLERANCE
    high = config.EXPECTED_MAIN_DOCS + config.MAIN_DOC_TOLERANCE
    if not (low <= main_count <= high):
        errors.append(
            f"is_main count {main_count} outside expected "
            f"{config.EXPECTED_MAIN_DOCS} ± {config.MAIN_DOC_TOLERANCE}"
        )

    return errors


def run_transform(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    raw_rows = rows if rows is not None else run_extract()
    docs: list[RecipeDocument] = []
    row_errors: list[str] = []

    for row in raw_rows:
        try:
            docs.append(transform_row(row))
        except ValueError as exc:
            row_errors.append(str(exc))

    errors = row_errors + validate_documents(docs)
    if errors:
        raise TransformValidationError(errors)

    main_count = sum(1 for d in docs if d.is_main)
    indian_main = sum(
        1 for d in docs if d.is_main and d.cuisine_group == "Indian"
    )

    return {
        "recipe_count": len(docs),
        "main_count": main_count,
        "indian_main_count": indian_main,
        "documents": docs,
    }


def _json_default(obj: object) -> object:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def print_transform_report(result: dict) -> None:
    print("\n=== Transform report ===")
    print(f"recipes:    {result['recipe_count']}")
    print(f"is_main:    {result['main_count']}")
    print(f"indian main:{result['indian_main_count']}")

    docs: list[RecipeDocument] = result["documents"]
    if docs:
        print("\n--- Sample record (first doc) ---")
        print(json.dumps(docs[0], indent=2, default=_json_default, ensure_ascii=False))


def main() -> None:
    try:
        result = run_transform()
    except TransformValidationError as exc:
        print("\n=== Transform report ===")
        print(f"validation errors: {len(exc.errors)}")
        for err in exc.errors[:50]:
            print(f"  - {err}")
        if len(exc.errors) > 50:
            print(f"  ... and {len(exc.errors) - 50} more")
        sys.exit(1)
    except (ValueError, FileNotFoundError) as exc:
        print(f"\n*** Transform failed: {exc}")
        sys.exit(1)

    print_transform_report(result)
    sys.exit(0)


if __name__ == "__main__":
    main()
