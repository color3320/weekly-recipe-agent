"""Smoke-test $vectorSearch with auto-embed after index creation."""

from __future__ import annotations

import os
import sys

import _repo_path  # noqa: F401 — add repo root to sys.path

from etl import config
from etl.mongo_client import make_client
from etl.verify import check_vector_index_ready, supports_vector_search

SMOKE_QUERY = "comforting lentil curry"
SMOKE_LIMIT = 3


def run_smoke_search(
    *,
    mongodb_uri: str | None = None,
    query: str = SMOKE_QUERY,
    wait_for_index: bool = True,
) -> list[dict]:
    uri = mongodb_uri or os.environ.get("MONGODB_URI", config.MONGODB_URI)
    client = make_client(uri)
    try:
        if not supports_vector_search(client, uri):
            raise RuntimeError(
                "Deployment does not support vector search. "
                "Use mongodb/mongodb-atlas-local:preview or Atlas."
            )

        collection = client[config.MONGODB_DB][config.RECIPES_COLLECTION]
        if collection.count_documents({}) == 0:
            raise RuntimeError("recipes collection is empty — run python -m etl.run_etl first")

        if wait_for_index:
            status = check_vector_index_ready(client, timeout_sec=600)
            if status != "READY":
                raise RuntimeError(
                    f"Vector index {config.VECTOR_SEARCH_INDEX!r} not READY (status={status!r}). "
                    "Run python scripts/create_atlas_index.py and retry."
                )

        pipeline = [
            {
                "$vectorSearch": {
                    "index": config.VECTOR_SEARCH_INDEX,
                    "path": "embed_text",
                    "query": {"text": query},
                    "numCandidates": 50,
                    "limit": SMOKE_LIMIT,
                    "filter": {"is_main": True},
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "display_name": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]
        return list(collection.aggregate(pipeline))
    finally:
        client.close()


def main() -> int:
    print(f"=== Vector search smoke test ===")
    print(f"  query: {SMOKE_QUERY!r}")
    try:
        results = run_smoke_search()
    except Exception as exc:
        print(f"*** Smoke test failed: {exc}", file=sys.stderr)
        return 1

    if not results:
        print("*** No results returned from $vectorSearch")
        return 1

    print(f"  hits: {len(results)}")
    for row in results:
        score = row.get("score")
        score_s = f"{score:.4f}" if isinstance(score, float) else str(score)
        print(f"    - {row.get('display_name')} (id={row.get('_id')}, score={score_s})")

    print("\nSMOKE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
