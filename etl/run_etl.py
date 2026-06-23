"""ETL orchestrator: extract → transform → load → verify."""

from __future__ import annotations

import argparse
import sys

from etl import config
from etl.load import run_load, snapshot_counts
from etl.transform import TransformValidationError, run_transform
from etl.verify import run_verify


def prove_idempotent_reload(transform_result: dict) -> bool:
    """Run load twice; fact/lookup counts must match; verify must pass."""
    before = snapshot_counts()
    run_load(transform_result)
    mid = snapshot_counts()
    run_load(transform_result)
    after = snapshot_counts()

    count_keys = ("stay_rows", "room_type_lookup", "market_code_lookup", "channel_code_lookup")
    identical = all(before[k] == mid[k] == after[k] for k in count_keys)
    as_of_stable = before["as_of_date"] == mid["as_of_date"] == after["as_of_date"]

    print("\n=== Idempotent reload check ===")
    print(f"  1st load: {mid}")
    print(f"  2nd load: {after}")
    if identical and as_of_stable:
        print("  Identical row counts and as_of_date across reloads.")
    else:
        print("  *** Row counts or as_of_date differ between reloads.")
        return False

    if run_verify() != 0:
        print("  *** Verify failed after second reload.")
        return False

    print("  Verify still PASS after second reload.")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the hackathon ETL pipeline.")
    parser.add_argument(
        "--from-cache",
        action="store_true",
        help="Reuse data/raw_*.json; skip scrape steps.",
    )
    parser.add_argument(
        "--skip-idempotency-check",
        action="store_true",
        help="Skip the second load / idempotency proof.",
    )
    args = parser.parse_args(argv)

    if not args.from_cache:
        from etl.extract import main as extract_main
        from etl.scrape_verify import run_scrape_verify

        print("=== Extract ===")
        extract_main()
        print("\n=== Scrape verify ===")
        if run_scrape_verify() != 0:
            print("*** Verify scrape failed")
            return 1
    else:
        print("=== Using cached raw JSON ===")
        print(f"  reservations: {config.OUTPUT_RESERVATIONS}")
        print(f"  lookups:      {config.OUTPUT_LOOKUPS}")
        print(f"  targets:      {config.OUTPUT_VERIFY_TARGETS}")

    print("\n=== Transform ===")
    try:
        transform_result = run_transform()
    except TransformValidationError as exc:
        print(f"*** Transform validation failed ({len(exc.errors)} error(s))")
        for err in exc.errors[:20]:
            print(f"  - {err}")
        return 1
    except Exception as exc:
        print(f"*** Transform failed: {exc}")
        return 1

    print(
        f"  {transform_result['reservation_count']} reservations, "
        f"{transform_result['stay_row_count']} stay rows, "
        f"as_of={transform_result.get('as_of_date')}"
    )

    print("\n=== Load ===")
    try:
        load_result = run_load(transform_result)
    except Exception as exc:
        print(f"*** Load failed: {exc}")
        return 1
    print(f"  loaded {load_result['stay_rows']} stay rows at as_of={load_result['as_of_date']}")

    print("\n=== Verify ===")
    if run_verify() != 0:
        return 1

    if not args.skip_idempotency_check:
        if not prove_idempotent_reload(transform_result):
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
