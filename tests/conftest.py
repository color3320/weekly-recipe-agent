"""Shared pytest fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import psycopg
import pytest

from etl import config

TARGETS_PATH = Path(config.OUTPUT_VERIFY_TARGETS)


@pytest.fixture(scope="session")
def targets() -> dict:
    return json.loads(TARGETS_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def as_of(targets) -> str:
    return targets["anchor_date"]


@pytest.fixture(scope="session")
def db():
    try:
        conn = psycopg.connect(config.DATABASE_URL)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres unavailable: {exc}")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM reservations_hackathon LIMIT 1")
    except psycopg.Error as exc:
        conn.close()
        pytest.skip(f"Database not loaded: {exc}")
    yield conn
    conn.close()


def invoke(tool, **kwargs):
    """Call a langchain @tool with keyword arguments."""
    return tool.invoke(kwargs)
