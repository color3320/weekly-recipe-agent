import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

XLSX_PATH = REPO_ROOT / "IndianFoodDatasetXLS.xlsx"

MONGODB_URI = os.environ.get(
    "MONGODB_URI",
    "mongodb://localhost:27017/weekly_recipes?directConnection=true",
)
MONGODB_DB = os.environ.get("MONGODB_DB", "weekly_recipes")
RECIPES_COLLECTION = "recipes"
VECTOR_SEARCH_INDEX = "recipe_vec"
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "voyage-4-lite")

EXPECTED_TOTAL_DOCS = 6871
EXPECTED_MAIN_DOCS = 2862
MAIN_DOC_TOLERANCE = 5

# Legacy Postgres URL — hotel agent still references this until Phase 2+.
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://hackathon:hackathon@localhost:5432/hotel_hackathon",
)

VALID_COURSES = frozenset(
    {
        "Lunch",
        "Dinner",
        "Main Course",
        "Side Dish",
        "Snack",
        "Dessert",
        "Appetizer",
        "South Indian Breakfast",
        "World Breakfast",
        "North Indian Breakfast",
        "Indian Breakfast",
        "Vegetarian",
        "One Pot Dish",
        "High Protein Vegetarian",
        "Brunch",
        "Vegan",
        "Non Vegeterian",
        "Eggetarian",
        "No Onion No Garlic (Sattvic)",
        "Sugar Free Diet",
    }
)

VALID_DIETS = frozenset(
    {
        "Vegetarian",
        "High Protein Vegetarian",
        "Non Vegeterian",
        "Eggetarian",
        "Diabetic Friendly",
        "High Protein Non Vegetarian",
        "No Onion No Garlic (Sattvic)",
        "Vegan",
        "Gluten Free",
        "Sugar Free Diet",
    }
)

NON_VEG_DIETS = frozenset(
    {
        "Non Vegeterian",
        "High Protein Non Vegetarian",
        "Eggetarian",
    }
)
