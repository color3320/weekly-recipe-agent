"""Verify recipe collection counts and field completeness after load."""

from __future__ import annotations

import os
import sys
import time
from typing import Any
from urllib.parse import urlparse

from pymongo import MongoClient
from pymongo.errors import OperationFailure

from etl import config
from etl.mongo_client import make_client


class VerifyResult:
    __slots__ = ("name", "computed", "target", "passed")

    def __init__(self, name: str, computed: Any, target: Any, passed: bool) -> None:
        self.name = name
        self.computed = computed
        self.target = target
        self.passed = passed


def is_atlas_hosted_uri(uri: str | None = None) -> bool:
    parsed = urlparse(uri or config.MONGODB_URI)
    host = (parsed.hostname or "").lower()
    return host.endswith(".mongodb.net") or "atlas" in host


def supports_vector_search(client: MongoClient, uri: str | None = None) -> bool:
    """True when the deployment exposes MongoDB Vector Search (Atlas or atlas-local)."""
    if os.environ.get("MONGODB_VECTOR_SEARCH", "").strip() in {"1", "true", "yes"}:
        return True
    if is_atlas_hosted_uri(uri):
        return True
    try:
        collection = client[config.MONGODB_DB][config.RECIPES_COLLECTION]
        collection.list_search_indexes()
        return True
    except OperationFailure:
        return False


def compute_metrics(
    client: MongoClient | None = None,
    *,
    mongodb_uri: str | None = None,
) -> dict[str, Any]:
    owns_client = client is None
    if owns_client:
        client = make_client(mongodb_uri or config.MONGODB_URI)

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
        indian_main = collection.count_documents(
            {"is_main": True, "cuisine_group": "Indian"}
        )
        main_indian_pct = round(100 * indian_main / main, 1) if main else 0.0
    finally:
        if owns_client:
            client.close()

    return {
        "total_documents": total,
        "main_documents": main,
        "missing_display_name": missing_display,
        "missing_embed_text": missing_embed,
        "indian_main_documents": indian_main,
        "main_indian_pct": main_indian_pct,
    }


def _index_is_ready(index: dict[str, Any]) -> bool:
    if index.get("queryable") is True:
        return True
    return index.get("status") == "READY"


def check_vector_index_ready(
    client: MongoClient,
    *,
    index_name: str | None = None,
    timeout_sec: int | None = None,
    poll_interval_sec: int = 10,
    log_progress: bool = True,
    fail_fast_stuck_sec: int = 120,
) -> str:
    """Poll until the vector index is queryable. Returns final status label."""
    name = index_name or config.VECTOR_SEARCH_INDEX
    collection = client[config.MONGODB_DB][config.RECIPES_COLLECTION]
    timeout = timeout_sec if timeout_sec is not None else config.INDEX_READY_TIMEOUT_SEC
    deadline = time.monotonic() + timeout
    stuck_deadline = time.monotonic() + fail_fast_stuck_sec
    last_status = "NOT_FOUND"
    last_num_docs: int | None = None
    stuck_warned = False

    while time.monotonic() < deadline:
        found = False
        for index in collection.list_search_indexes():
            if index.get("name") != name:
                continue
            found = True
            last_status = index.get("status", "UNKNOWN")
            last_num_docs = index.get("numDocs")
            queryable = index.get("queryable")

            if log_progress:
                docs = "?" if last_num_docs is None else str(last_num_docs)
                print(
                    f"  index {name!r}: status={last_status}, "
                    f"queryable={queryable}, numDocs={docs}"
                )

            if _index_is_ready(index):
                return "READY"

            if last_status in {"FAILED", "DOES_NOT_EXIST"}:
                return last_status

        if not found and log_progress:
            print(f"  index {name!r}: not found yet")

        if (
            not stuck_warned
            and time.monotonic() >= stuck_deadline
            and last_status == "BUILDING"
            and (last_num_docs or 0) == 0
        ):
            stuck_warned = True
            print(
                "\n  Index still BUILDING with numDocs=0 after "
                f"{fail_fast_stuck_sec}s — likely Voyage rate limits.\n"
                "  Run: python scripts/check_voyage_key.py\n"
                "  Then add a payment method: Atlas → Billing (see Voyage billing docs).\n"
                "  Polling will continue, or Ctrl+C and fix billing first."
            )

        time.sleep(poll_interval_sec)

    if last_status == "BUILDING" and (last_num_docs or 0) == 0:
        print(
            "\n  Hint: auto-embed never indexed any docs. "
            "Run python scripts/check_voyage_key.py and fix Voyage billing/key first."
        )

    return "TIMEOUT"


def build_results(
    computed: dict[str, Any],
    *,
    index_status: str | None = None,
    check_index: bool = False,
) -> list[VerifyResult]:
    results: list[VerifyResult] = []

    low = config.EXPECTED_MAIN_DOCS - config.MAIN_DOC_TOLERANCE
    high = config.EXPECTED_MAIN_DOCS + config.MAIN_DOC_TOLERANCE
    main = computed["main_documents"]
    main_ok = low <= main <= high

    checks = [
        (
            "total_documents",
            computed["total_documents"],
            config.EXPECTED_TOTAL_DOCS,
            computed["total_documents"] == config.EXPECTED_TOTAL_DOCS,
        ),
        (
            "main_documents",
            main,
            f"{config.EXPECTED_MAIN_DOCS} ± {config.MAIN_DOC_TOLERANCE}",
            main_ok,
        ),
        ("missing_display_name", computed["missing_display_name"], 0, computed["missing_display_name"] == 0),
        ("missing_embed_text", computed["missing_embed_text"], 0, computed["missing_embed_text"] == 0),
        (
            "main_indian_pct",
            computed["main_indian_pct"],
            ">= 70%",
            computed["main_indian_pct"] >= 70.0,
        ),
    ]

    for name, comp, target, passed in checks:
        results.append(VerifyResult(name, comp, target, passed))

    if check_index:
        results.append(
            VerifyResult(
                f"vector_index.{config.VECTOR_SEARCH_INDEX}",
                index_status or "NOT_FOUND",
                "READY",
                index_status == "READY",
            )
        )

    return results


def print_report(results: list[VerifyResult]) -> None:
    name_w = max(len(r.name) for r in results)
    print(f"\n{'metric'.ljust(name_w)} | {'computed':>14} | {'target':>14} | result")
    print("-" * (name_w + 14 + 14 + 12))
    for r in results:
        comp = "" if r.computed is None else str(r.computed)
        targ = "" if r.target is None else str(r.target)
        status = "PASS" if r.passed else "FAIL"
        print(f"{r.name.ljust(name_w)} | {comp:>14} | {targ:>14} | {status}")


def run_verify(
    *,
    mongodb_uri: str | None = None,
    check_index: bool = False,
) -> int:
    uri = mongodb_uri or config.MONGODB_URI
    client = make_client(uri)
    try:
        computed = compute_metrics(client, mongodb_uri=uri)
        index_status: str | None = None
        if check_index:
            if not supports_vector_search(client, uri):
                print(
                    "*** --check-index skipped: deployment does not support "
                    "vector search (use atlas-local or Atlas)"
                )
            else:
                print(
                    f"Polling vector index {config.VECTOR_SEARCH_INDEX!r} "
                    f"(timeout {config.INDEX_READY_TIMEOUT_SEC}s)..."
                )
                index_status = check_vector_index_ready(client)
    finally:
        client.close()

    results = build_results(computed, index_status=index_status, check_index=check_index)
    print_report(results)

    failures = [r for r in results if not r.passed]
    if failures:
        print(f"\n*** VERIFY FAILED ({len(failures)} mismatch(es))")
        return 1

    print("\nVERIFY PASSED")
    return 0


def main() -> None:
    check_index = "--check-index" in sys.argv
    sys.exit(run_verify(check_index=check_index))


if __name__ == "__main__":
    main()
