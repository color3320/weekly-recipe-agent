"""Apply schema.sql and run ETL from cache against DATABASE_URL (Supabase hosted DB)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import psycopg

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = REPO_ROOT / "schema.sql"


def main() -> int:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        print("Set DATABASE_URL to your Supabase connection string.", file=sys.stderr)
        return 1
    if not SCHEMA.is_file():
        print(f"Missing {SCHEMA}", file=sys.stderr)
        return 1

    print(f"Applying schema from {SCHEMA} ...")
    ddl = SCHEMA.read_text(encoding="utf-8")
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()
    print("Schema applied.")

    print("Running ETL from cache ...")
    env = os.environ.copy()
    result = subprocess.run(
        [sys.executable, "-m", "etl.run_etl", "--from-cache"],
        cwd=REPO_ROOT,
        env=env,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
