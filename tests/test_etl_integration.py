"""Integration tests for recipe ETL against a live MongoDB."""

from __future__ import annotations

import os

import pytest
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

from etl import config
from etl.load import run_load, snapshot_counts
from etl.transform import run_transform
from etl.verify import run_verify


def _mongo_available() -> bool:
    uri = os.environ.get("MONGODB_URI", config.MONGODB_URI)
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        client.close()
        return True
    except ServerSelectionTimeoutError:
        return False


@pytest.mark.integration
@pytest.mark.skipif(not _mongo_available(), reason="MongoDB not reachable")
def test_etl_load_and_verify():
    transform_result = run_transform()
    run_load(transform_result)
    counts = snapshot_counts()
    assert counts["total"] == config.EXPECTED_TOTAL_DOCS
    assert counts["missing_display_name"] == 0
    assert counts["missing_embed_text"] == 0
    assert run_verify() == 0
