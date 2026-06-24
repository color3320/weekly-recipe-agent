"""Run recipe ETL against MONGODB_URI (local or Atlas)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    uri = os.environ.get("MONGODB_URI", "").strip()
    if not uri:
        print("Set MONGODB_URI to your MongoDB connection string.", file=sys.stderr)
        return 1

    print(f"Running recipe ETL against {uri.split('@')[-1]} ...")
    result = subprocess.run(
        [sys.executable, "-m", "etl.run_etl"],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
