"""Recompute /verify metrics in SQL and compare to verify_targets.json."""

from __future__ import annotations

import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from etl import config
from etl.metric_windows import (
    SQL_ADR_BY_ROOM_TYPE,
    SQL_CANCELLED_RESERVATIONS,
    SQL_CURRENT_RESERVATIONS,
    SQL_DATASET_AS_OF,
    SQL_LAST_YEAR_RESERVATIONS,
    SQL_OTB_NIGHTS_BY_MARKET,
    SQL_OTB_ROOM_NIGHTS,
    SQL_OTB_ROOM_REVENUE,
    SQL_OTB_TOTAL_REVENUE,
    SQL_STLY_ROOM_NIGHTS,
    SQL_STLY_TOTAL_REVENUE,
    SQL_TOTAL_RESERVATIONS,
    SQL_TOTAL_STAY_ROWS,
)


class VerifyResult:
    __slots__ = ("name", "computed", "target", "passed")

    def __init__(self, name: str, computed: Any, target: Any, passed: bool) -> None:
        self.name = name
        self.computed = computed
        self.target = target
        self.passed = passed


def load_targets(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path or config.OUTPUT_VERIFY_TARGETS)
    return json.loads(p.read_text(encoding="utf-8"))


def _quantize_money(value: Decimal | int | float | None) -> Decimal:
    if value is None:
        return Decimal("0")
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _normalize_computed(value: Any, *, is_money: bool = False) -> int | Decimal:
    if value is None:
        return 0 if not is_money else Decimal("0.00")
    if is_money:
        return _quantize_money(value)
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else value
    return int(value)


def _normalize_target(value: Any, *, is_money: bool = False) -> int | Decimal:
    if is_money:
        return _quantize_money(value)
    if isinstance(value, float):
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(value)


def _compare(computed: Any, target: Any, *, is_money: bool = False) -> bool:
    c = _normalize_computed(computed, is_money=is_money)
    t = _normalize_target(target, is_money=is_money)
    return c == t


def _fetch_scalar(cur, sql: str, params: dict[str, Any]) -> Any:
    cur.execute(sql, params)
    row = cur.fetchone()
    if row is None:
        return None
    if isinstance(row, dict):
        return next(iter(row.values()))
    return row[0]


def compute_metrics(
    conn: psycopg.Connection,
    as_of_date: str,
) -> dict[str, Any]:
    params = {"as_of_date": as_of_date}
    metrics: dict[str, Any] = {}

    with conn.cursor(row_factory=dict_row) as cur:
        metrics["total_reservations"] = _fetch_scalar(cur, SQL_TOTAL_RESERVATIONS, params)
        metrics["total_stay_rows"] = _fetch_scalar(cur, SQL_TOTAL_STAY_ROWS, params)
        metrics["current_reservations"] = _fetch_scalar(cur, SQL_CURRENT_RESERVATIONS, params)
        metrics["last_year_reservations"] = _fetch_scalar(cur, SQL_LAST_YEAR_RESERVATIONS, params)
        metrics["cancelled_reservations"] = _fetch_scalar(cur, SQL_CANCELLED_RESERVATIONS, params)
        metrics["otb_room_nights"] = _fetch_scalar(cur, SQL_OTB_ROOM_NIGHTS, params)
        metrics["otb_room_revenue_before_tax"] = _fetch_scalar(cur, SQL_OTB_ROOM_REVENUE, params)
        metrics["otb_total_revenue_before_tax"] = _fetch_scalar(cur, SQL_OTB_TOTAL_REVENUE, params)
        metrics["stly_room_nights"] = _fetch_scalar(cur, SQL_STLY_ROOM_NIGHTS, params)
        metrics["stly_total_revenue_before_tax"] = _fetch_scalar(cur, SQL_STLY_TOTAL_REVENUE, params)

        cur.execute(SQL_ADR_BY_ROOM_TYPE, params)
        metrics["adr_by_room_type"] = {row["space_type"]: row["adr"] for row in cur.fetchall()}

        cur.execute(SQL_OTB_NIGHTS_BY_MARKET, params)
        metrics["otb_room_nights_by_market"] = {
            row["market_code"]: row["room_nights"] for row in cur.fetchall()
        }

        metrics["dataset_as_of_date"] = _fetch_scalar(cur, SQL_DATASET_AS_OF, params)

    return metrics


def build_results(computed: dict[str, Any], targets: dict[str, Any]) -> list[VerifyResult]:
    results: list[VerifyResult] = []
    scalars = targets.get("scalars", {})

    scalar_money = {
        "otb_room_revenue_before_tax",
        "otb_total_revenue_before_tax",
        "stly_total_revenue_before_tax",
    }

    for key in (
        "total_reservations",
        "total_stay_rows",
        "current_reservations",
        "last_year_reservations",
        "cancelled_reservations",
        "otb_room_nights",
        "otb_room_revenue_before_tax",
        "otb_total_revenue_before_tax",
        "stly_room_nights",
        "stly_total_revenue_before_tax",
    ):
        target = scalars.get(key)
        comp = computed.get(key)
        is_money = key in scalar_money
        results.append(
            VerifyResult(
                key,
                _normalize_computed(comp, is_money=is_money),
                _normalize_target(target, is_money=is_money) if target is not None else None,
                _compare(comp, target, is_money=is_money) if target is not None else False,
            )
        )

    anchor = targets.get("anchor_date")
    db_as_of = computed.get("dataset_as_of_date")
    results.append(
        VerifyResult(
            "dataset_metadata.as_of_date",
            str(db_as_of) if db_as_of else None,
            anchor,
            str(db_as_of) == anchor if db_as_of and anchor else False,
        )
    )

    for room, target in sorted(targets.get("adr_by_room_type", {}).items()):
        comp = computed.get("adr_by_room_type", {}).get(room)
        results.append(
            VerifyResult(
                f"adr_by_room_type.{room}",
                _normalize_computed(comp, is_money=True),
                _normalize_target(target, is_money=True),
                _compare(comp, target, is_money=True),
            )
        )

    for market, target in sorted(targets.get("otb_room_nights_by_market", {}).items()):
        comp = computed.get("otb_room_nights_by_market", {}).get(market)
        results.append(
            VerifyResult(
                f"otb_room_nights_by_market.{market}",
                _normalize_computed(comp),
                _normalize_target(target),
                _compare(comp, target),
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


def print_failures(results: list[VerifyResult]) -> None:
    failures = [r for r in results if not r.passed]
    if not failures:
        return
    print("\n*** MISMATCHES ***")
    for r in failures:
        try:
            diff = Decimal(str(r.computed)) - Decimal(str(r.target))
            print(f"  {r.name}: computed={r.computed} target={r.target} diff={diff}")
        except Exception:
            print(f"  {r.name}: computed={r.computed!r} target={r.target!r}")


def run_verify(
    *,
    database_url: str | None = None,
    targets_path: str | Path | None = None,
) -> int:
    targets = load_targets(targets_path)
    as_of = targets.get("anchor_date")
    if not as_of:
        print("*** verify_targets.json missing anchor_date")
        return 1

    url = database_url or config.DATABASE_URL
    with psycopg.connect(url) as conn:
        computed = compute_metrics(conn, as_of)

    results = build_results(computed, targets)
    print_report(results)
    failures = [r for r in results if not r.passed]
    print_failures(results)

    if failures:
        print(f"\n*** VERIFY FAILED ({len(failures)} mismatch(es))")
        return 1

    print("\nVERIFY PASSED")
    return 0


def main() -> None:
    sys.exit(run_verify())


if __name__ == "__main__":
    main()
