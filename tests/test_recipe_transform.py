"""Tests for recipe ETL transform logic."""

from __future__ import annotations

import pandas as pd
import pytest

from etl import config
from etl.embed import build_embed_text
from etl.extract import run_extract
from etl.transform import (
    BREAKFAST_COURSES,
    INDIAN_CUISINES,
    TransformValidationError,
    classify_cuisine_group,
    course_to_meal_slot,
    effort_bucket,
    is_veg_from_diet,
    normalize_cuisine,
    run_transform,
    split_ingredients,
    transform_row,
)


def _row(**overrides) -> dict:
    base = {
        "Srno": 1,
        "RecipeName": "Test Recipe",
        "TranslatedRecipeName": "Test Recipe",
        "Ingredients": "onion, tomato, salt",
        "PrepTimeInMins": 10,
        "CookTimeInMins": 20,
        "TotalTimeInMins": 30,
        "Servings": 4,
        "Cuisine": "Indian",
        "Course": "Lunch",
        "Diet": "Vegetarian",
        "Instructions": "Cook it.",
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    ("course", "meal_slot", "is_main"),
    [
        ("Lunch", "lunch", True),
        ("Dinner", "dinner", True),
        ("Main Course", "main", True),
        ("Side Dish", "side_dish", False),
        ("Vegetarian", None, False),
        ("Brunch", "breakfast", False),
    ],
)
def test_course_to_meal_slot(course, meal_slot, is_main):
    assert course_to_meal_slot(course) == (meal_slot, is_main)


@pytest.mark.parametrize("course", sorted(BREAKFAST_COURSES))
def test_breakfast_courses(course):
    slot, is_main = course_to_meal_slot(course)
    assert slot == "breakfast"
    assert is_main is False


@pytest.mark.parametrize(
    ("diet", "expected"),
    [
        ("Vegetarian", True),
        ("Vegan", True),
        ("Diabetic Friendly", True),
        ("Non Vegeterian", False),
        ("High Protein Non Vegetarian", False),
        ("Eggetarian", False),
    ],
)
def test_is_veg_from_diet(diet, expected):
    assert is_veg_from_diet(diet) == expected


@pytest.mark.parametrize(
    ("total_min", "bucket"),
    [(30, "quick"), (31, "medium"), (60, "medium"), (61, "long")],
)
def test_effort_bucket(total_min, bucket):
    assert effort_bucket(total_min) == bucket


def test_split_ingredients():
    assert split_ingredients("a, b ,c") == ["a", "b", "c"]
    assert split_ingredients("") == []


def test_bom_strip_on_cuisine():
    assert normalize_cuisine("\ufeffGujarati Recipes") == "Gujarati Recipes"
    doc = transform_row(_row(Cuisine="\ufeffGujarati Recipes"))
    assert doc.cuisine == "Gujarati Recipes"
    assert doc.cuisine_group == "Indian"


def test_vegetarian_as_course():
    doc = transform_row(_row(Course="Vegetarian", Diet="Vegetarian"))
    assert doc.course == "Vegetarian"
    assert doc.meal_slot is None
    assert doc.is_main is False
    assert doc.is_veg is True


def test_embed_text():
    doc = transform_row(_row())
    assert doc.embed_text == build_embed_text(
        "Test Recipe", "Indian", "onion, tomato, salt"
    )


def test_all_cuisines_classified():
    df = pd.read_excel(config.XLSX_PATH, engine="openpyxl")
    cuisines = {normalize_cuisine(c) for c in df["Cuisine"].dropna().unique()}
    unmapped_indian = cuisines - INDIAN_CUISINES
    variety = {c for c in cuisines if classify_cuisine_group(c) == "Variety"}
    indian = {c for c in cuisines if classify_cuisine_group(c) == "Indian"}
    assert len(indian) + len(variety) == len(cuisines)
    # Every non-Indian cuisine should be intentional Variety (not silent default).
    assert unmapped_indian == variety


def test_full_transform_produces_expected_count():
    result = run_transform()
    assert result["recipe_count"] == config.EXPECTED_TOTAL_DOCS
    low = config.EXPECTED_MAIN_DOCS - config.MAIN_DOC_TOLERANCE
    high = config.EXPECTED_MAIN_DOCS + config.MAIN_DOC_TOLERANCE
    assert low <= result["main_count"] <= high


def test_extract_row_count():
    rows = run_extract()
    assert len(rows) == config.EXPECTED_TOTAL_DOCS


def test_invalid_course_raises():
    with pytest.raises(TransformValidationError):
        run_transform([_row(Course="Not A Course", Srno=99)])
