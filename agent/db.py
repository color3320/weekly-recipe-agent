"""Postgres connection and read-only SQL guard."""

from __future__ import annotations

import os
import re
from typing import Any

import psycopg
from psycopg.rows import dict_row

from etl import config

DATABASE_URL = os.environ.get("DATABASE_URL", config.DATABASE_URL)

_FORBIDDEN = re.compile(
    r"\b("
    r"INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|"
    r"COPY|EXECUTE|CALL|MERGE|REPLACE|VACUUM|ANALYZE|COMMENT|"
    r"SET|RESET|SHOW|PREPARE|DEALLOCATE|LOCK|UNLOCK"
    r")\b",
    re.IGNORECASE,
)


class ReadOnlySQLError(ValueError):
    pass


def get_connection() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def assert_read_only_sql(query: str) -> None:
    """Reject anything that is not a single SELECT or WITH statement."""
    normalized = query.strip().rstrip(";").strip()
    if not normalized:
        raise ReadOnlySQLError("Empty query")

    if ";" in normalized:
        raise ReadOnlySQLError("Multiple statements are not allowed")

    upper = normalized.upper()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        raise ReadOnlySQLError("Only SELECT or WITH queries are allowed")

    if _FORBIDDEN.search(normalized):
        raise ReadOnlySQLError("Query contains forbidden keyword")

    if re.search(r"\bINTO\b", normalized, re.IGNORECASE):
        raise ReadOnlySQLError("SELECT INTO is not allowed")


def fetch_scalar(
    conn: psycopg.Connection,
    sql: str,
    params: dict[str, Any] | None = None,
) -> Any:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params or {})
        row = cur.fetchone()
        if row is None:
            return None
        return next(iter(row.values()))


def fetch_all(
    conn: psycopg.Connection,
    sql: str,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params or {})
        return list(cur.fetchall())


def run_readonly_query(
    conn: psycopg.Connection,
    sql: str,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    assert_read_only_sql(sql)
    return fetch_all(conn, sql, params)
