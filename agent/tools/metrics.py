"""Core revenue and segment metrics."""

from __future__ import annotations

from typing import Literal

from langchain_core.tools import tool

from agent.db import fetch_all, get_connection
from agent.semantic import (
    CURRENT_LOOKBACK_DAYS,
    DatePurpose,
    FACT_TABLE,
    RevenueMeasure,
    adr_by_room_type,
    adr_by_room_type_detail,
    bind_params,
    count_reservations,
    date_column,
    fetch_lookup_codes,
    fetch_room_capacity,
    fetch_verify_scalars,
    get_as_of_date,
    label_maps_from_lookups,
    make_envelope,
    otb_window_description,
    otb_stay_predicate,
    quantize_money,
    resolve_month,
    revenue_column,
    stay_month_filter,
    sum_revenue,
    sum_room_nights,
)


@tool
def describe_dataset() -> dict:
    """Report dataset context: as-of date, room capacity, lookup codes, and OTB window definition."""
    with get_connection() as conn:
        as_of = get_as_of_date(conn)
        lookups = fetch_lookup_codes(conn)
        label_maps = label_maps_from_lookups(lookups)
        capacity = fetch_room_capacity(conn)
        scalars = fetch_verify_scalars(conn, as_of)

    return make_envelope(
        headline=(
            f"ANCHOR AS-OF {as_of} — ground every month name and OTB window on this date. "
            f"{scalars['total_reservations']} reservations in dataset, "
            f"{capacity} physical rooms across {len(lookups['room_types'])} room types."
        ),
        key_numbers={
            "as_of_date": as_of,
            "anchor_as_of_date": as_of,
            "room_capacity": capacity,
            "total_reservations": scalars["total_reservations"],
            "total_stay_rows": scalars["total_stay_rows"],
            "current_reservations": scalars["current_reservations"],
            "last_year_reservations": scalars["last_year_reservations"],
            "market_codes": lookups["market_codes"],
            "channel_codes": lookups["channel_codes"],
            "room_types": lookups["room_types"],
            "label_maps": label_maps,
        },
        filters_and_definitions={
            "as_of_date": as_of,
            "otb_window": otb_window_description(),
            "current_reservation_window": (
                f"arrival_date >= as_of_date - {CURRENT_LOOKBACK_DAYS} days"
            ),
            "last_year_reservation_window": (
                f"arrival_date < as_of_date - {CURRENT_LOOKBACK_DAYS} days"
            ),
            "cancelled_excluded": "By default for OTB/STLY/ADR; use cancellations tool for cancelled business",
            "month_resolution_rule": (
                "Month without year resolves to next occurrence on/after as-of "
                "(e.g. as-of 2026-06-11: July -> 2026-07, June -> 2026-06)."
            ),
            "segment_label_maps": label_maps,
        },
        caveats=[
            "Current vs last-year reservation split uses arrival_date with 180-day lookback.",
            "Call describe_dataset first when a question names a month without a year.",
        ],
    )


@tool
def revenue_on_books(
    group_by: Literal["none", "month"] = "none",
    month: str | None = None,
    revenue_measure: Literal["total", "room"] = "total",
) -> dict:
    """On-the-books reservations, room nights, and revenue (Reserved, stay_date >= as_of).

    month: YYYY-MM or month name (resolved against as-of via resolve_month).
    """
    measure = RevenueMeasure.TOTAL if revenue_measure == "total" else RevenueMeasure.ROOM
    with get_connection() as conn:
        as_of = get_as_of_date(conn)
        resolved_month = resolve_month(month, as_of) if month else None
        where = otb_stay_predicate()
        month_clause, month_params = stay_month_filter(resolved_month)
        full_where = where + month_clause
        p = bind_params(as_of, month_params)

        room_nights = sum_room_nights(conn, full_where, as_of, month_params)
        reservations = count_reservations(conn, full_where, as_of, month_params)
        revenue = sum_revenue(conn, full_where, measure, as_of, month_params)

        breakdown = []
        if group_by == "month":
            col = date_column(DatePurpose.STAY)
            rev_col = revenue_column(measure)
            sql = f"""
            SELECT TO_CHAR({col}, 'YYYY-MM') AS period,
                   COUNT(DISTINCT reservation_id) AS reservations,
                   COALESCE(SUM(number_of_spaces), 0) AS room_nights,
                   COALESCE(SUM({rev_col}), 0) AS revenue
            FROM {FACT_TABLE}
            WHERE {full_where}
            GROUP BY TO_CHAR({col}, 'YYYY-MM')
            ORDER BY period
            """
            rows = fetch_all(conn, sql, p)
            breakdown = [
                {
                    "month": r["period"],
                    "reservations": int(r["reservations"]),
                    "room_nights": int(r["room_nights"]),
                    "revenue": float(quantize_money(r["revenue"])),
                }
                for r in rows
            ]

    rev_label = "total revenue" if measure == RevenueMeasure.TOTAL else "room revenue"
    headline = (
        f"OTB: {reservations:,} reservations, {room_nights:,} room nights, "
        f"${revenue:,.2f} {rev_label} (as of {as_of})"
    )
    if resolved_month:
        headline += f" for {resolved_month}"

    key_numbers: dict = {
        "reservations": reservations,
        "room_nights": room_nights,
        "revenue": float(revenue),
        "revenue_measure": measure.value,
    }
    if breakdown:
        key_numbers["by_month"] = breakdown

    return make_envelope(
        headline=headline,
        key_numbers=key_numbers,
        filters_and_definitions={
            "as_of_date": as_of,
            "window": "otb",
            "date_field": date_column(DatePurpose.STAY),
            "revenue_field": revenue_column(measure),
            "cancelled_excluded": True,
            "status_filter": "Reserved",
            "month_filter": resolved_month,
            "month_input": month,
            "group_by": group_by,
        },
        caveats=[
            "OTB uses stay_date, not arrival_date or create_datetime.",
            "Total revenue includes package effects; use revenue_measure='room' for room-only.",
            "reservations = COUNT(DISTINCT reservation_id); room_nights = SUM(number_of_spaces).",
        ],
    )


@tool
def segment_mix(
    dimension: Literal["market_code", "macro_group", "channel_code"] = "market_code",
    month: str | None = None,
    filter_corporate: bool = False,
    revenue_measure: Literal["total", "room"] = "total",
) -> dict:
    """OTB segment breakdown with room nights, revenue, and share percentages.

    month: YYYY-MM or month name (resolved against as-of).
    """
    measure = RevenueMeasure.TOTAL if revenue_measure == "total" else RevenueMeasure.ROOM
    with get_connection() as conn:
        as_of = get_as_of_date(conn)
        resolved_month = resolve_month(month, as_of) if month else None
        where = otb_stay_predicate()
        month_clause, month_params = stay_month_filter(resolved_month)
        full_where = where + month_clause
        p = bind_params(as_of, month_params)

        if dimension == "macro_group":
            dim_expr = "m.macro_group"
            name_expr = "m.macro_group"
            join = f"""
            JOIN market_code_lookup m ON {FACT_TABLE}.market_code = m.market_code
            """
            group_by = "m.macro_group"
            if filter_corporate:
                full_where += " AND m.macro_group = 'Corporate'"
        elif dimension == "channel_code":
            dim_expr = "c.channel_code"
            name_expr = "c.channel_name"
            join = f"""
            JOIN channel_code_lookup c ON {FACT_TABLE}.channel_code = c.channel_code
            """
            group_by = "c.channel_code, c.channel_name"
        else:
            dim_expr = "m.market_code"
            name_expr = "m.market_name"
            join = f"""
            JOIN market_code_lookup m ON {FACT_TABLE}.market_code = m.market_code
            """
            group_by = "m.market_code, m.market_name"
            if filter_corporate:
                full_where += " AND m.macro_group = 'Corporate'"

        rev_col = revenue_column(measure)
        sql = f"""
        SELECT {dim_expr} AS segment,
               {name_expr} AS segment_name,
               COUNT(DISTINCT reservation_id) AS reservations,
               COALESCE(SUM(number_of_spaces), 0) AS room_nights,
               COALESCE(SUM({rev_col}), 0) AS revenue
        FROM {FACT_TABLE}
        {join}
        WHERE {full_where}
        GROUP BY {group_by}
        ORDER BY revenue DESC
        """
        rows = fetch_all(conn, sql, p)
        total_reservations = count_reservations(conn, full_where, as_of, month_params)
        total_nights = sum(int(r["room_nights"]) for r in rows)
        total_rev = sum(quantize_money(r["revenue"]) for r in rows)

        segments = []
        for r in rows:
            nights = int(r["room_nights"])
            rev = quantize_money(r["revenue"])
            share_nights = round(nights / total_nights * 100, 2) if total_nights else 0.0
            share_rev = (
                round(float(rev / total_rev * 100), 2) if total_rev > 0 else 0.0
            )
            segments.append({
                "segment": r["segment"],
                "segment_name": r["segment_name"],
                "reservations": int(r["reservations"]),
                "room_nights": nights,
                "revenue": float(rev),
                "share_pct_nights": share_nights,
                "share_pct_revenue": share_rev,
                "share_pct": share_rev,
            })

    dim_label = dimension.replace("_", " ")
    headline = (
        f"OTB segment mix by {dim_label}: {len(segments)} segments, "
        f"{total_reservations:,} reservations, {total_nights:,} room nights"
    )
    if resolved_month:
        headline += f" in {resolved_month}"
    if filter_corporate:
        headline += " (corporate only)"

    return make_envelope(
        headline=headline,
        key_numbers={
            "total_reservations": total_reservations,
            "total_room_nights": total_nights,
            "total_revenue": float(total_rev),
            "segments": segments,
        },
        filters_and_definitions={
            "as_of_date": as_of,
            "window": "otb",
            "date_field": date_column(DatePurpose.STAY),
            "revenue_field": revenue_column(measure),
            "cancelled_excluded": True,
            "dimension": dimension,
            "month_filter": resolved_month,
            "month_input": month,
            "filter_corporate": filter_corporate,
        },
        caveats=[
            "share_pct reflects revenue share; share_pct_nights reflects room-night share.",
            "Corporate = macro_group 'Corporate' (CSR, CNR).",
        ],
    )


@tool
def adr_analysis() -> dict:
    """ADR by room type for current Reserved reservations (arrival within 180-day window)."""
    with get_connection() as conn:
        as_of = get_as_of_date(conn)
        adr_map = adr_by_room_type(conn, as_of)
        room_types = adr_by_room_type_detail(conn, as_of)

    if not adr_map:
        highest = None
        highest_name = None
    else:
        highest = max(adr_map, key=lambda k: adr_map[k])
        highest_name = next(
            (rt["name"] for rt in room_types if rt["code"] == highest),
            highest,
        )

    by_type = {k: float(v) for k, v in sorted(adr_map.items())}

    return make_envelope(
        headline=(
            f"Highest ADR room type: {highest_name} ({highest}) at ${adr_map[highest]:,.2f}"
            if highest
            else "No ADR data"
        ),
        key_numbers={
            "adr_by_room_type": by_type,
            "room_types": room_types,
            "highest_adr_type": highest,
            "highest_adr_type_name": highest_name,
            "highest_adr": float(adr_map[highest]) if highest else None,
        },
        filters_and_definitions={
            "as_of_date": as_of,
            "window": "current",
            "date_field": date_column(DatePurpose.ARRIVAL),
            "cancelled_excluded": True,
            "lookback_days": CURRENT_LOOKBACK_DAYS,
            "formula": "AVG(adr_room) at reservation grain (one row per reservation_id)",
        },
        caveats=[
            "Verify ADR uses reservation-level AVG(adr_room), not stay-weighted revenue/nights.",
        ],
    )
