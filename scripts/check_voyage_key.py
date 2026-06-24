"""Preflight check for Voyage auto-embed (billing + API key)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

import _repo_path  # noqa: F401

from etl import config

EMBEDDING_URL = os.environ.get(
    "EMBEDDING_PROVIDER_ENDPOINT",
    "https://ai.mongodb.com/v1/embeddings",
)


def check_voyage_key() -> int:
    key = os.environ.get("VOYAGE_API_KEY", "").strip()
    if not key:
        print("VOYAGE_API_KEY is not set in .env", file=sys.stderr)
        return 1

    body = json.dumps({"input": ["recipe ETL preflight"], "model": config.EMBEDDING_MODEL}).encode()
    req = urllib.request.Request(
        EMBEDDING_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
            dims = len(payload.get("data", [{}])[0].get("embedding", []))
            print(f"OK: Voyage embed succeeded (model={config.EMBEDDING_MODEL}, dims={dims})")
            return 0
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        print(f"HTTP {exc.code}: {detail}", file=sys.stderr)
        if exc.code == 429:
            print(
                "\nVoyage rate limit — index build will stay at numDocs=0.\n"
                "Fix: Atlas → Billing → add a payment method for this org, then wait a few minutes.\n"
                "Docs: https://www.mongodb.com/docs/voyageai/management/billing/\n"
                "Then: docker compose up -d mongodb --force-recreate\n"
                "      python scripts/create_atlas_index.py  (if index was stuck)\n"
                "      python -m etl.run_etl --verify-only --check-index",
                file=sys.stderr,
            )
        elif exc.code in {401, 403}:
            print(
                "\nInvalid Voyage key. Create a *Model API key* in Atlas:\n"
                "  Organization → AI Models → API Keys (or Project → AI Models → API Keys)\n"
                "Use that key as VOYAGE_API_KEY — not a generic Atlas API key.",
                file=sys.stderr,
            )
        return 1
    except Exception as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(check_voyage_key())
