"""Transform raw scrape JSON into typed records with validation."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from etl import config
from etl.models import (
    ChannelCodeLookup,
    MarketCodeLookup,
    ReservationStay,
    RoomTypeLookup,
)

NULL_MARKERS = frozenset({"", "—", "–", "-", "null", "none", "n/a"})
EM_DASH_RE = re.compile(r"^[\s\u2014\u2013\-]+$")


class TransformValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"{len(errors)} validation error(s)")


def parse_null(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or stripped.lower() in NULL_MARKERS or EM_DASH_RE.match(stripped):
        return None
    return stripped


def parse_date(value: str, *, field: str, reservation_id: str | None = None) -> date:
    cleaned = parse_null(value)
    if cleaned is None:
        ctx = f" for {reservation_id}" if reservation_id else ""
        raise ValueError(f"required date field {field}{ctx} is null/empty")
    return date.fromisoformat(cleaned)


def parse_timestamptz(value: str, *, field: str, reservation_id: str | None = None) -> datetime | None:
    cleaned = parse_null(value)
    if cleaned is None:
        return None
    dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_decimal(value: str, *, field: str, reservation_id: str | None = None) -> Decimal:
    cleaned = parse_null(value)
    if cleaned is None:
        ctx = f" for {reservation_id}" if reservation_id else ""
        raise ValueError(f"required decimal field {field}{ctx} is null/empty")
    try:
        return Decimal(cleaned.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"invalid decimal for {field}: {value!r}") from exc


def parse_int(value: str, *, field: str, reservation_id: str | None = None) -> int:
    cleaned = parse_null(value)
    if cleaned is None:
        ctx = f" for {reservation_id}" if reservation_id else ""
        raise ValueError(f"required int field {field}{ctx} is null/empty")
    return int(cleaned.replace(",", ""))


def parse_bool(value: str, *, field: str, reservation_id: str | None = None) -> bool:
    cleaned = parse_null(value)
    if cleaned is None:
        ctx = f" for {reservation_id}" if reservation_id else ""
        raise ValueError(f"required bool field {field}{ctx} is null/empty")
    lowered = cleaned.lower()
    if lowered in ("true", "1", "yes"):
        return True
    if lowered in ("false", "0", "no"):
        return False
    raise ValueError(f"invalid bool for {field}: {value!r}")


def row_value(row: dict[str, str], *names: str) -> str:
    lowered = {k.lower(): v for k, v in row.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None:
            return value.strip()
    return ""


def transform_room_type_lookup(rows: list[dict[str, str]]) -> list[RoomTypeLookup]:
    return [
        RoomTypeLookup(
            space_type=row_value(row, "SPACE_TYPE", "space_type"),
            room_class=row_value(row, "ROOM_CLASS", "room_class"),
            display_name=row_value(row, "DISPLAY_NAME", "display_name"),
            number_of_rooms=parse_int(
                row_value(row, "NUMBER_OF_ROOMS", "number_of_rooms"),
                field="number_of_rooms",
            ),
        )
        for row in rows
    ]


def transform_market_code_lookup(rows: list[dict[str, str]]) -> list[MarketCodeLookup]:
    return [
        MarketCodeLookup(
            market_code=row_value(row, "MARKET_CODE", "market_code"),
            market_name=row_value(row, "MARKET_NAME", "market_name"),
            macro_group=row_value(row, "MACRO_GROUP", "macro_group"),
            description=parse_null(row_value(row, "DESCRIPTION", "description")),
        )
        for row in rows
    ]


def transform_channel_code_lookup(rows: list[dict[str, str]]) -> list[ChannelCodeLookup]:
    return [
        ChannelCodeLookup(
            channel_code=row_value(row, "CHANNEL_CODE", "channel_code"),
            channel_name=row_value(row, "CHANNEL_NAME", "channel_name"),
            channel_group=row_value(row, "CHANNEL_GROUP", "channel_group"),
        )
        for row in rows
    ]


def transform_lookups(raw: dict) -> tuple[list[RoomTypeLookup], list[MarketCodeLookup], list[ChannelCodeLookup]]:
    room_types = transform_room_type_lookup(raw["room_type_lookup"])
    market_codes = transform_market_code_lookup(raw["market_code_lookup"])
    channel_codes = transform_channel_code_lookup(raw["channel_code_lookup"])
    return room_types, market_codes, channel_codes


def transform_reservation_stays(raw: dict) -> list[ReservationStay]:
    stays: list[ReservationStay] = []
    for reservation in raw["reservations"]:
        reservation_id = reservation["reservation_id"]
        detail = reservation["detail"]
        rid = reservation_id

        arrival_date = parse_date(detail["arrival_date"], field="arrival_date", reservation_id=rid)
        departure_date = parse_date(detail["departure_date"], field="departure_date", reservation_id=rid)
        nights = parse_int(detail["nights"], field="nights", reservation_id=rid)
        reservation_status = parse_null(detail["reservation_status"]) or ""
        create_datetime = parse_timestamptz(
            detail["create_datetime"], field="create_datetime", reservation_id=rid
        )
        if create_datetime is None:
            raise ValueError(f"required create_datetime for {rid} is null/empty")
        cancellation_datetime = parse_timestamptz(
            detail.get("cancellation_datetime", ""), field="cancellation_datetime", reservation_id=rid
        )
        guest_country = parse_null(detail.get("guest_country", ""))
        is_block = parse_bool(detail["is_block"], field="is_block", reservation_id=rid)
        is_walk_in = parse_bool(detail["is_walk_in"], field="is_walk_in", reservation_id=rid)
        number_of_spaces = parse_int(
            detail["number_of_spaces"], field="number_of_spaces", reservation_id=rid
        )
        space_type = parse_null(detail["space_type"]) or ""
        market_code = parse_null(detail["market_code"]) or ""
        channel_code = parse_null(detail["channel_code"]) or ""
        source_name = parse_null(detail["source_name"]) or ""
        rate_plan_code = parse_null(detail["rate_plan_code"]) or ""
        adr_room = parse_decimal(detail["adr_room"], field="adr_room", reservation_id=rid)
        lead_time = parse_int(detail["lead_time"], field="lead_time", reservation_id=rid)
        company_name = parse_null(detail.get("company_name", ""))
        travel_agent_name = parse_null(detail.get("travel_agent_name", ""))

        for stay in reservation["stay_rows"]:
            stay_date = parse_date(
                row_value(stay, "STAY_DATE", "stay_date"),
                field="stay_date",
                reservation_id=rid,
            )
            daily_room = parse_decimal(
                row_value(stay, "DAILY_ROOM_REVENUE_BEFORE_TAX", "daily_room_revenue_before_tax"),
                field="daily_room_revenue_before_tax",
                reservation_id=rid,
            )
            daily_total = parse_decimal(
                row_value(stay, "DAILY_TOTAL_REVENUE_BEFORE_TAX", "daily_total_revenue_before_tax"),
                field="daily_total_revenue_before_tax",
                reservation_id=rid,
            )
            stays.append(
                ReservationStay(
                    reservation_id=reservation_id,
                    arrival_date=arrival_date,
                    departure_date=departure_date,
                    stay_date=stay_date,
                    reservation_status=reservation_status,
                    create_datetime=create_datetime,
                    cancellation_datetime=cancellation_datetime,
                    guest_country=guest_country,
                    is_block=is_block,
                    is_walk_in=is_walk_in,
                    number_of_spaces=number_of_spaces,
                    space_type=space_type,
                    market_code=market_code,
                    channel_code=channel_code,
                    source_name=source_name,
                    rate_plan_code=rate_plan_code,
                    daily_room_revenue_before_tax=daily_room,
                    daily_total_revenue_before_tax=daily_total,
                    nights=nights,
                    adr_room=adr_room,
                    lead_time=lead_time,
                    company_name=company_name,
                    travel_agent_name=travel_agent_name,
                )
            )
    return stays


def validate_stays(
    stays: list[ReservationStay],
    room_types: list[RoomTypeLookup],
    market_codes: list[MarketCodeLookup],
    channel_codes: list[ChannelCodeLookup],
) -> list[str]:
    errors: list[str] = []
    space_types = {r.space_type for r in room_types}
    markets = {m.market_code for m in market_codes}
    channels = {c.channel_code for c in channel_codes}
    seen: set[tuple[str, date]] = set()

    for stay in stays:
        key = (stay.reservation_id, stay.stay_date)
        if key in seen:
            errors.append(f"duplicate (reservation_id, stay_date): {stay.reservation_id} {stay.stay_date}")
        seen.add(key)

        if stay.stay_date < stay.arrival_date:
            errors.append(
                f"{stay.reservation_id} {stay.stay_date}: stay_date < arrival_date ({stay.arrival_date})"
            )
        if stay.stay_date >= stay.departure_date:
            errors.append(
                f"{stay.reservation_id} {stay.stay_date}: stay_date >= departure_date ({stay.departure_date})"
            )
        if stay.space_type not in space_types:
            errors.append(f"{stay.reservation_id}: unknown space_type {stay.space_type!r}")
        if stay.market_code not in markets:
            errors.append(f"{stay.reservation_id}: unknown market_code {stay.market_code!r}")
        if stay.channel_code not in channels:
            errors.append(f"{stay.reservation_id}: unknown channel_code {stay.channel_code!r}")
        if stay.number_of_spaces <= 0:
            errors.append(f"{stay.reservation_id}: number_of_spaces must be > 0")
        if stay.nights <= 0:
            errors.append(f"{stay.reservation_id}: nights must be > 0")
        if stay.adr_room < 0:
            errors.append(f"{stay.reservation_id}: adr_room must be >= 0")
        if stay.lead_time < 0:
            errors.append(f"{stay.reservation_id}: lead_time must be >= 0")
        if not stay.reservation_status:
            errors.append(f"{stay.reservation_id}: reservation_status is required")
        if not stay.source_name:
            errors.append(f"{stay.reservation_id}: source_name is required")
        if not stay.rate_plan_code:
            errors.append(f"{stay.reservation_id}: rate_plan_code is required")

    return errors


def validate_nights_per_reservation(stays: list[ReservationStay]) -> list[str]:
    errors: list[str] = []
    by_reservation: dict[str, list[ReservationStay]] = {}
    for stay in stays:
        by_reservation.setdefault(stay.reservation_id, []).append(stay)
    for reservation_id, rows in by_reservation.items():
        nights = rows[0].nights
        if len(rows) != nights:
            errors.append(
                f"{reservation_id}: nights={nights} but {len(rows)} stay row(s)"
            )
    return errors


def load_raw_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_transform(
    reservations_path: str | Path | None = None,
    lookups_path: str | Path | None = None,
) -> dict:
    reservations_path = reservations_path or config.OUTPUT_RESERVATIONS
    lookups_path = lookups_path or config.OUTPUT_LOOKUPS

    raw_reservations = load_raw_json(reservations_path)
    raw_lookups = load_raw_json(lookups_path)

    room_types, market_codes, channel_codes = transform_lookups(raw_lookups)
    stays = transform_reservation_stays(raw_reservations)

    errors = validate_stays(stays, room_types, market_codes, channel_codes)
    errors.extend(validate_nights_per_reservation(stays))

    reservation_ids = {s.reservation_id for s in stays}
    cancelled = sum(
        1
        for rid in reservation_ids
        if next(s for s in stays if s.reservation_id == rid).reservation_status == "Cancelled"
    )

    metadata = raw_reservations.get("dataset_metadata") or {}
    as_of_date = metadata.get("as_of_date")

    result = {
        "as_of_date": as_of_date,
        "reservation_count": len(reservation_ids),
        "stay_row_count": len(stays),
        "lookup_counts": {
            "room_type_lookup": len(room_types),
            "market_code_lookup": len(market_codes),
            "channel_code_lookup": len(channel_codes),
        },
        "cancelled_count": cancelled,
        "validation_errors": errors,
        "room_types": room_types,
        "market_codes": market_codes,
        "channel_codes": channel_codes,
        "stays": stays,
    }

    if errors:
        raise TransformValidationError(errors)

    return result


def _json_default(obj: object) -> object:
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def print_transform_report(result: dict) -> None:
    print("\n=== Transform report ===")
    print(f"as_of_date:           {result.get('as_of_date')}")
    print(f"reservations:         {result['reservation_count']}")
    print(f"stay rows:            {result['stay_row_count']}")
    lc = result["lookup_counts"]
    print(
        f"lookups:              {lc['room_type_lookup']} / "
        f"{lc['market_code_lookup']} / {lc['channel_code_lookup']}"
    )
    print(f"cancelled:            {result['cancelled_count']}")
    print(f"validation errors:    {len(result['validation_errors'])}")

    stays: list[ReservationStay] = result["stays"]
    if stays:
        sample = stays[0]
        print("\n--- Sample record (first stay row) ---")
        print(json.dumps(sample, indent=2, default=_json_default, ensure_ascii=False))


def main() -> None:
    try:
        result = run_transform()
    except TransformValidationError as exc:
        print("\n=== Transform report ===")
        print(f"validation errors:    {len(exc.errors)}")
        for err in exc.errors[:50]:
            print(f"  - {err}")
        if len(exc.errors) > 50:
            print(f"  ... and {len(exc.errors) - 50} more")
        sys.exit(1)
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"\n*** Transform failed: {exc}")
        sys.exit(1)

    print_transform_report(result)
    sys.exit(0)


if __name__ == "__main__":
    main()
