"""ETL orchestrator: extract → transform → load → verify."""

from __future__ import annotations

import argparse
import sys

from etl.extract import run_extract
from etl.load import run_load, snapshot_counts
from etl.transform import TransformValidationError, run_transform
from etl.verify import run_verify


def prove_idempotent_reload(transform_result: dict) -> bool:
    """Run load twice; counts must match; verify must pass."""
    before = snapshot_counts()
    run_load(transform_result)
    mid = snapshot_counts()
    run_load(transform_result)
    after = snapshot_counts()

    count_keys = ("total", "is_main", "missing_display_name", "missing_embed_text")
    identical = all(before[k] == mid[k] == after[k] for k in count_keys)

    print("\n=== Idempotent reload check ===")
    print(f"  1st load: {mid}")
    print(f"  2nd load: {after}")
    if not identical:
        print("  *** Row counts differ between reloads.")
        return False

    print("  Identical counts across reloads.")
    if run_verify() != 0:
        print("  *** Verify failed after second reload.")
        return False

    print("  Verify still PASS after second reload.")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the recipe ETL pipeline.")
    parser.add_argument(
        "--skip-idempotency-check",
        action="store_true",
        help="Skip the second load / idempotency proof.",
    )
    parser.add_argument(
        "--check-index",
        action="store_true",
        help="Poll vector search index until READY/queryable (Atlas or atlas-local).",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Skip extract/transform/load; run verify only (use with --check-index).",
    )
    args = parser.parse_args(argv)

    if not args.verify_only:
        print("=== Extract ===")
        try:
            rows = run_extract()
            print(f"  {len(rows)} rows from xlsx")
        except Exception as exc:
            print(f"*** Extract failed: {exc}")
            return 1

        print("\n=== Transform ===")
        try:
            transform_result = run_transform(rows)
        except TransformValidationError as exc:
            print(f"*** Transform validation failed ({len(exc.errors)} error(s))")
            for err in exc.errors[:20]:
                print(f"  - {err}")
            return 1
        except Exception as exc:
            print(f"*** Transform failed: {exc}")
            return 1

        print(
            f"  {transform_result['recipe_count']} recipes, "
            f"{transform_result['main_count']} is_main"
        )

        print("\n=== Load ===")
        try:
            load_result = run_load(transform_result)
        except Exception as exc:
            print(f"*** Load failed: {exc}")
            return 1
        print(f"  loaded {load_result['total']} recipes ({load_result['is_main']} is_main)")
    else:
        transform_result = None

    print("\n=== Verify ===")
    if run_verify(check_index=args.check_index) != 0:
        return 1

    if not args.verify_only and not args.skip_idempotency_check:
        if not prove_idempotent_reload(transform_result):
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
