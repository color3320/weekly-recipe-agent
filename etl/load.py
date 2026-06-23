"""Load transformed records into Postgres (truncate-and-reload, idempotent)."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from etl import config
from etl.models import (
    ChannelCodeLookup,
    MarketCodeLookup,
    ReservationStay,
    RoomTypeLookup,
)

DATASET_METADATA_DDL = """
CREATE TABLE IF NOT EXISTS public.dataset_metadata (
  id integer PRIMARY KEY CHECK (id = 1),
  as_of_date date NOT NULL,
  loaded_at timestamptz NOT NULL
);
"""


class LoadError(Exception):
    pass


def load_verify_targets(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path or config.OUTPUT_VERIFY_TARGETS)
    return json.loads(p.read_text(encoding="utf-8"))


def pre_load_sanity(transform_result: dict, targets: dict[str, Any]) -> list[str]:
    """Compare transform counts to verify_targets before touching the database."""
    errors: list[str] = []
    scalars = targets.get("scalars", {})
    anchor = targets.get("anchor_date")

    as_of = transform_result.get("as_of_date")
    if anchor and as_of and as_of != anchor:
        errors.append(f"as_of_date mismatch: transform={as_of!r} verify={anchor!r}")

    checks = [
        ("total_reservations", transform_result["reservation_count"]),
        ("total_stay_rows", transform_result["stay_row_count"]),
        ("cancelled_reservations", transform_result["cancelled_count"]),
    ]
    for key, actual in checks:
        expected = scalars.get(key)
        if expected is not None and actual != expected:
            errors.append(f"{key}: transform={actual} verify={expected}")

    lc = transform_result["lookup_counts"]
    lookup_checks = [
        ("room_type_lookup", lc["room_type_lookup"]),
        ("market_code_lookup", lc["market_code_lookup"]),
        ("channel_code_lookup", lc["channel_code_lookup"]),
    ]
    for key, actual in lookup_checks:
        expected = scalars.get(key)
        if expected is None:
            # lookup counts not in scalars; use config EXPECTED
            expected = config.EXPECTED.get(key)
        if expected is not None and actual != expected:
            errors.append(f"{key}: transform={actual} expected={expected}")

    reservations = transform_result["reservation_count"]
    if reservations != 250:
        errors.append(f"wildly off reservation count: {reservations} (expected ~250)")

    stay_rows = transform_result["stay_row_count"]
    if not (513 <= stay_rows <= 516):
        errors.append(f"wildly off stay row count: {stay_rows} (expected ~513-516)")

    return errors


def _adapt_stay(stay: ReservationStay) -> tuple[Any, ...]:
    return (
        stay.reservation_id,
        stay.arrival_date,
        stay.departure_date,
        stay.stay_date,
        stay.reservation_status,
        stay.create_datetime,
        stay.cancellation_datetime,
        stay.guest_country,
        stay.is_block,
        stay.is_walk_in,
        stay.number_of_spaces,
        stay.space_type,
        stay.market_code,
        stay.channel_code,
        stay.source_name,
        stay.rate_plan_code,
        stay.daily_room_revenue_before_tax,
        stay.daily_total_revenue_before_tax,
        stay.nights,
        stay.adr_room,
        stay.lead_time,
        stay.company_name,
        stay.travel_agent_name,
    )


STAY_COLUMNS = (
    "reservation_id",
    "arrival_date",
    "departure_date",
    "stay_date",
    "reservation_status",
    "create_datetime",
    "cancellation_datetime",
    "guest_country",
    "is_block",
    "is_walk_in",
    "number_of_spaces",
    "space_type",
    "market_code",
    "channel_code",
    "source_name",
    "rate_plan_code",
    "daily_room_revenue_before_tax",
    "daily_total_revenue_before_tax",
    "nights",
    "adr_room",
    "lead_time",
    "company_name",
    "travel_agent_name",
)


def run_load(
    transform_result: dict,
    *,
    database_url: str | None = None,
    targets_path: str | Path | None = None,
) -> dict[str, Any]:
    targets = load_verify_targets(targets_path)
    sanity_errors = pre_load_sanity(transform_result, targets)
    if sanity_errors:
        raise LoadError("Pre-load sanity check failed:\n  " + "\n  ".join(sanity_errors))

    as_of_date = date.fromisoformat(
        transform_result["as_of_date"] or targets["anchor_date"]
    )
    room_types: list[RoomTypeLookup] = transform_result["room_types"]
    market_codes: list[MarketCodeLookup] = transform_result["market_codes"]
    channel_codes: list[ChannelCodeLookup] = transform_result["channel_codes"]
    stays: list[ReservationStay] = transform_result["stays"]

    url = database_url or config.DATABASE_URL
    loaded_at = datetime.now(timezone.utc)

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(DATASET_METADATA_DDL)

            cur.execute("BEGIN")
            try:
                cur.execute(
                    "TRUNCATE public.reservations_hackathon, "
                    "public.room_type_lookup, "
                    "public.market_code_lookup, "
                    "public.channel_code_lookup "
                    "RESTART IDENTITY"
                )

                cur.executemany(
                    """
                    INSERT INTO public.room_type_lookup
                      (space_type, room_class, display_name, number_of_rooms)
                    VALUES (%s, %s, %s, %s)
                    """,
                    [
                        (r.space_type, r.room_class, r.display_name, r.number_of_rooms)
                        for r in room_types
                    ],
                )
                cur.executemany(
                    """
                    INSERT INTO public.market_code_lookup
                      (market_code, market_name, macro_group, description)
                    VALUES (%s, %s, %s, %s)
                    """,
                    [
                        (m.market_code, m.market_name, m.macro_group, m.description)
                        for m in market_codes
                    ],
                )
                cur.executemany(
                    """
                    INSERT INTO public.channel_code_lookup
                      (channel_code, channel_name, channel_group)
                    VALUES (%s, %s, %s)
                    """,
                    [
                        (c.channel_code, c.channel_name, c.channel_group)
                        for c in channel_codes
                    ],
                )

                stay_sql = sql.SQL("INSERT INTO public.reservations_hackathon ({}) VALUES ({})").format(
                    sql.SQL(", ").join(map(sql.Identifier, STAY_COLUMNS)),
                    sql.SQL(", ").join(sql.Placeholder() * len(STAY_COLUMNS)),
                )
                cur.executemany(stay_sql, [_adapt_stay(s) for s in stays])

                cur.execute("DELETE FROM public.dataset_metadata")
                cur.execute(
                    """
                    INSERT INTO public.dataset_metadata (id, as_of_date, loaded_at)
                    VALUES (1, %s, %s)
                    """,
                    (as_of_date, loaded_at),
                )
                cur.execute("COMMIT")
            except Exception:
                cur.execute("ROLLBACK")
                raise

    return {
        "as_of_date": as_of_date.isoformat(),
        "loaded_at": loaded_at.isoformat(),
        "room_type_lookup": len(room_types),
        "market_code_lookup": len(market_codes),
        "channel_code_lookup": len(channel_codes),
        "stay_rows": len(stays),
        "reservations": transform_result["reservation_count"],
    }


def snapshot_counts(database_url: str | None = None) -> dict[str, Any]:
    url = database_url or config.DATABASE_URL
    with psycopg.connect(url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM public.reservations_hackathon")
            stays = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM public.room_type_lookup")
            room_types = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM public.market_code_lookup")
            markets = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM public.channel_code_lookup")
            channels = cur.fetchone()["n"]
            cur.execute(
                "SELECT as_of_date, loaded_at FROM public.dataset_metadata WHERE id = 1"
            )
            meta = cur.fetchone()
    return {
        "stay_rows": stays,
        "room_type_lookup": room_types,
        "market_code_lookup": markets,
        "channel_code_lookup": channels,
        "as_of_date": str(meta["as_of_date"]) if meta else None,
        "loaded_at": meta["loaded_at"].isoformat() if meta and meta["loaded_at"] else None,
    }


def main() -> None:
    from etl.transform import run_transform

    try:
        transform_result = run_transform()
        result = run_load(transform_result)
    except LoadError as exc:
        print(f"\n*** Load failed: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"\n*** Load failed: {exc}")
        sys.exit(1)

    print("\n=== Load complete ===")
    for key, value in result.items():
        print(f"  {key}: {value}")
    sys.exit(0)


if __name__ == "__main__":
    main()
