"""Extract raw recipe rows from the Indian Food xlsx dataset."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd

from etl import config


def run_extract(xlsx_path: str | Path | None = None) -> list[dict[str, Any]]:
    path = Path(xlsx_path or config.XLSX_PATH)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found: {path}")

    df = pd.read_excel(path, engine="openpyxl")
    row_count = len(df)
    if row_count != config.EXPECTED_TOTAL_DOCS:
        raise ValueError(
            f"Expected {config.EXPECTED_TOTAL_DOCS} rows, got {row_count} from {path}"
        )

    return df.to_dict(orient="records")


def main() -> None:
    try:
        rows = run_extract()
    except (FileNotFoundError, ValueError) as exc:
        print(f"*** Extract failed: {exc}")
        sys.exit(1)

    print("=== Extract summary ===")
    print(f"  source: {config.XLSX_PATH}")
    print(f"  rows:   {len(rows)}")
    if rows:
        sample = rows[0]
        print(f"  sample: {sample.get('TranslatedRecipeName', sample.get('RecipeName'))}")
    sys.exit(0)


if __name__ == "__main__":
    main()
