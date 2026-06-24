"""Load transformed recipe documents into MongoDB (drop-and-reload)."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any

from pymongo import MongoClient

from etl import config
from etl.models import RecipeDocument


class LoadError(Exception):
    pass


def get_collection(client: MongoClient | None = None):
    owns_client = client is None
    if owns_client:
        client = MongoClient(config.MONGODB_URI)
    db = client[config.MONGODB_DB]
    return client, db[config.RECIPES_COLLECTION], owns_client


def documents_to_mongo(docs: list[RecipeDocument]) -> list[dict[str, Any]]:
    return [doc.to_mongo() for doc in docs]


def run_load(
    transform_result: dict[str, Any],
    *,
    mongodb_uri: str | None = None,
) -> dict[str, Any]:
    docs: list[RecipeDocument] = transform_result["documents"]
    if not docs:
        raise LoadError("No documents to load")

    uri = mongodb_uri or config.MONGODB_URI
    client = MongoClient(uri)
    try:
        db = client[config.MONGODB_DB]
        collection = db[config.RECIPES_COLLECTION]
        collection.delete_many({})
        collection.insert_many(documents_to_mongo(docs), ordered=False)
    finally:
        client.close()

    loaded_at = datetime.now(timezone.utc)
    main_count = sum(1 for d in docs if d.is_main)
    return {
        "loaded_at": loaded_at.isoformat(),
        "total": len(docs),
        "is_main": main_count,
    }


def snapshot_counts(mongodb_uri: str | None = None) -> dict[str, Any]:
    uri = mongodb_uri or config.MONGODB_URI
    client = MongoClient(uri)
    try:
        collection = client[config.MONGODB_DB][config.RECIPES_COLLECTION]
        total = collection.count_documents({})
        main = collection.count_documents({"is_main": True})
        missing_display = collection.count_documents(
            {"$or": [{"display_name": None}, {"display_name": ""}]}
        )
        missing_embed = collection.count_documents(
            {"$or": [{"embed_text": None}, {"embed_text": ""}]}
        )
    finally:
        client.close()

    return {
        "total": total,
        "is_main": main,
        "missing_display_name": missing_display,
        "missing_embed_text": missing_embed,
    }


def main() -> None:
    from etl.transform import run_transform

    try:
        transform_result = run_transform()
        result = run_load(transform_result)
    except Exception as exc:
        print(f"\n*** Load failed: {exc}")
        sys.exit(1)

    print("\n=== Load complete ===")
    for key, value in result.items():
        print(f"  {key}: {value}")
    sys.exit(0)


if __name__ == "__main__":
    main()
