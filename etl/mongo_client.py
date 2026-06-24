"""Shared MongoDB client helpers for atlas-local and Atlas."""

from __future__ import annotations

import time

from pymongo import MongoClient
from pymongo.errors import AutoReconnect, NotPrimaryError, ServerSelectionTimeoutError

from etl import config

CLIENT_KWARGS = {
    "serverSelectionTimeoutMS": 60_000,
    "connectTimeoutMS": 20_000,
}


def make_client(uri: str | None = None) -> MongoClient:
    return MongoClient(uri or config.MONGODB_URI, **CLIENT_KWARGS)


def wait_for_writable(
    client: MongoClient,
    *,
    timeout_sec: int = 120,
    poll_interval_sec: int = 3,
) -> None:
    """Block until the deployment accepts writes (atlas-local RS primary election)."""
    deadline = time.monotonic() + timeout_sec
    last_error: Exception | None = None
    db = client[config.MONGODB_DB]
    probe = db["_etl_probe"]

    while time.monotonic() < deadline:
        try:
            client.admin.command("ping")
            probe.insert_one({"_id": 0, "probe": True})
            probe.delete_one({"_id": 0})
            return
        except (NotPrimaryError, AutoReconnect, ServerSelectionTimeoutError) as exc:
            last_error = exc
            time.sleep(poll_interval_sec)

    raise TimeoutError(
        f"MongoDB not writable after {timeout_sec}s"
        + (f": {last_error}" if last_error else "")
    )
