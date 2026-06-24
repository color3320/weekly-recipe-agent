"""Create the Atlas Automated Embedding vector search index on recipes."""

from __future__ import annotations

import os
import sys

from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

from etl import config
from etl.mongo_client import make_client


def index_definition() -> dict:
    return {
        "fields": [
            {
                "type": "autoEmbed",
                "modality": "text",
                "path": "embed_text",
                "model": config.EMBEDDING_MODEL,
            },
            {"type": "filter", "path": "is_main"},
            {"type": "filter", "path": "cuisine_group"},
            {"type": "filter", "path": "diet"},
        ]
    }


def main() -> int:
    uri = os.environ.get("MONGODB_URI", config.MONGODB_URI).strip()
    if not uri:
        print("Set MONGODB_URI to your MongoDB connection string.", file=sys.stderr)
        return 1

    client = make_client(uri)
    try:
        collection = client[config.MONGODB_DB][config.RECIPES_COLLECTION]
        existing = {idx.get("name") for idx in collection.list_search_indexes()}
        if config.VECTOR_SEARCH_INDEX in existing:
            print(f"Index {config.VECTOR_SEARCH_INDEX!r} already exists — skipping create.")
            return 0

        model = SearchIndexModel(
            definition=index_definition(),
            name=config.VECTOR_SEARCH_INDEX,
            type="vectorSearch",
        )
        collection.create_search_index(model)
        print(
            f"Created vector search index {config.VECTOR_SEARCH_INDEX!r} "
            f"(model={config.EMBEDDING_MODEL!r}). "
            "Poll status in Atlas UI or run: python -m etl.run_etl --check-index"
        )
    except Exception as exc:
        print(f"*** Index creation failed: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
