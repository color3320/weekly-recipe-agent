"""Booking pace and change detection tools."""

from __future__ import annotations

from decimal import Decimal

from langchain_core.tools import tool

from agent.db import fetch_all, fetch_scalar, get_connection
from agent.semantic import (
    CURRENT_LOOKBACK_DAYS,
    DatePurpose,
    FACT_TABLE,
    RevenueMeasure,
    build_stay_filter,
    date_column,
    exclude_cancelled_clause,
    get_as_of_date,
    make_envelope,
    otb_stay_predicate,
    params,
    quantize_money,
    revenue_column,
    stly_stay_predicate,
    sum_revenue,
    sum_room_nights,
)


@tool
def whats_changed(days: int = 7) -> dict:
    """Net change in future business from bookings and cancellations in the last N days."""
    with get_connection() as conn:
        as_of = get_as_of_date(conn)
        p = {**params(as_of), "days": days}

        new_bookings_sql = f"""
        SELECT COUNT(DISTINCT reservation_id)
        FROM {FACT_TABLE}
        WHERE {exclude_cancelled_clause()}
          AND stay_date >= %(as_of_date)s::date
          AND create_datetime >= %(as_of_date)s::date - (%(days)s || ' days')::interval
        """
        new_bookings = int(fetch_scalar(conn, new_bookings_sql, p) or 0)

        new_nights_sql = f"""
        SELECT COALESCE(SUM(number_of_spaces), 0)
        FROM {FACT_TABLE}
        WHERE {exclude_cancelled_clause()}
          AND stay_date >= %(as_of_date)s::date
          AND create_datetime >= %(as_of_date)s::date - (%(days)s || ' days')::interval
        """
        new_room_nights = int(fetch_scalar(conn, new_nights_sql, p) or 0)

        new_revenue_sql = f"""
        SELECT COALESCE(SUM(daily_total_revenue_before_tax), 0)
        FROM {FACT_TABLE}
        WHERE {exclude_cancelled_clause()}
          AND stay_date >= %(as_of_date)s::date
          AND create_datetime >= %(as_of_date)s::date - (%(days)s || ' days')::interval
        """
        new_revenue = quantize_money(fetch_scalar(conn, new_revenue_sql, p))

        cancelled_sql = f"""
        SELECT COUNT(DISTINCT reservation_id)
        FROM {FACT_TABLE}
        WHERE reservation_status = 'Cancelled'
          AND stay_date >= %(as_of_date)s::date
          AND cancellation_datetime >= %(as_of_date)s::date - (%(days)s || ' days')::interval
        """
        cancelled_count = int(fetch_scalar(conn, cancelled_sql, p) or 0)

        cancelled_nights_sql = f"""
        SELECT COALESCE(SUM(number_of_spaces), 0)
        FROM {FACT_TABLE}
        WHERE reservation_status = 'Cancelled'
          AND stay_date >= %(as_of_date)s::date
          AND cancellation_datetime >= %(as_of_date)s::date - (%(days)s || ' days')::interval
        """
        cancelled_nights = int(fetch_scalar(conn, cancelled_nights_sql, p) or 0)

        otb_nights = sum_room_nights(conn, otb_stay_predicate(), as_of)
        otb_revenue = sum_revenue(conn, otb_stay_predicate(), RevenueMeasure.TOTAL, as_of)

    net_nights = new_room_nights - cancelled_nights

    return make_envelope(
        headline=(
            f"Last {days} days: +{new_bookings} bookings ({new_room_nights:,} room nights, "
            f"${new_revenue:,.2f}), -{cancelled_count} cancellations ({cancelled_nights:,} nights); "
            f"net {net_nights:+,} future room nights"
        ),
        key_numbers={
            "new_bookings": new_bookings,
            "new_room_nights": new_room_nights,
            "new_revenue": float(new_revenue),
            "cancelled_bookings": cancelled_count,
            "cancelled_room_nights": cancelled_nights,
            "net_room_nights_change": net_nights,
            "current_otb_room_nights": otb_nights,
            "current_otb_total_revenue": float(otb_revenue),
        },
        filters_and_definitions={
            "as_of_date": as_of,
            "lookback_days": days,
            "booking_date_field": date_column(DatePurpose.PACE),
            "cancellation_date_field": date_column(DatePurpose.CANCELLATION),
            "future_stay_filter": f"stay_date >= {as_of}",
            "cancelled_excluded": "For new bookings only; cancellations counted separately",
        },
        caveats=[
            "New bookings filtered by create_datetime; cancellations by cancellation_datetime.",
            "Both restricted to future stays (stay_date >= as_of).",
        ],
    )


@tool
def booking_pace(days: int = 30) -> dict:
    """Booking pickup by create date for forward stays."""
    with get_connection() as conn:
        as_of = get_as_of_date(conn)
        p = {**params(as_of), "days": days}

        sql = f"""
        SELECT DATE(create_datetime) AS booking_date,
               COUNT(DISTINCT reservation_id) AS bookings,
               COALESCE(SUM(number_of_spaces), 0) AS room_nights,
               COALESCE(SUM(daily_total_revenue_before_tax), 0) AS revenue
        FROM {FACT_TABLE}
        WHERE {exclude_cancelled_clause()}
          AND stay_date >= %(as_of_date)s::date
          AND create_datetime >= %(as_of_date)s::date - (%(days)s || ' days')::interval
        GROUP BY DATE(create_datetime)
        ORDER BY booking_date
        """
        rows = fetch_all(conn, sql, p)
        daily = [
            {
                "booking_date": str(r["booking_date"]),
                "bookings": int(r["bookings"]),
                "room_nights": int(r["room_nights"]),
                "revenue": float(quantize_money(r["revenue"])),
            }
            for r in rows
        ]
        total_bookings = sum(d["bookings"] for d in daily)
        total_nights = sum(d["room_nights"] for d in daily)
        total_revenue = sum(Decimal(str(d["revenue"])) for d in daily)

    return make_envelope(
        headline=(
            f"Booking pace last {days} days: {total_bookings} bookings, "
            f"{total_nights:,} forward room nights, ${quantize_money(total_revenue):,.2f}"
        ),
        key_numbers={
            "total_bookings": total_bookings,
            "total_room_nights": total_nights,
            "total_revenue": float(quantize_money(total_revenue)),
            "daily": daily,
        },
        filters_and_definitions={
            "as_of_date": as_of,
            "lookback_days": days,
            "date_field": date_column(DatePurpose.PACE),
            "stay_filter": f"stay_date >= {as_of}",
            "revenue_field": revenue_column(RevenueMeasure.TOTAL),
            "cancelled_excluded": True,
        },
        caveats=[
            "Pace uses create_datetime (booking date), not stay_date.",
        ],
    )


@tool
def stly_comparison() -> dict:
    """Compare on-the-books (OTB) vs same-time-last-year (STLY) room nights and revenue."""
    with get_connection() as conn:
        as_of = get_as_of_date(conn)
        otb_nights = sum_room_nights(conn, otb_stay_predicate(), as_of)
        otb_revenue = sum_revenue(conn, otb_stay_predicate(), RevenueMeasure.TOTAL, as_of)
        stly_nights = sum_room_nights(conn, stly_stay_predicate(), as_of)
        stly_revenue = sum_revenue(conn, stly_stay_predicate(), RevenueMeasure.TOTAL, as_of)

    nights_change = (
        round((otb_nights - stly_nights) / stly_nights * 100, 1) if stly_nights else None
    )
    revenue_change = (
        round(float((otb_revenue - stly_revenue) / stly_revenue * 100), 1)
        if stly_revenue > 0
        else None
    )

    return make_envelope(
        headline=(
            f"OTB {otb_nights:,} nights (${otb_revenue:,.2f}) vs STLY {stly_nights:,} nights "
            f"(${stly_revenue:,.2f})"
        ),
        key_numbers={
            "otb_room_nights": otb_nights,
            "otb_total_revenue": float(otb_revenue),
            "stly_room_nights": stly_nights,
            "stly_total_revenue": float(stly_revenue),
            "room_nights_change_pct": nights_change,
            "revenue_change_pct": revenue_change,
        },
        filters_and_definitions={
            "as_of_date": as_of,
            "otb_window": build_stay_filter("otb"),
            "stly_window": build_stay_filter("stly"),
            "date_field": date_column(DatePurpose.STAY),
            "revenue_field": revenue_column(RevenueMeasure.TOTAL),
            "cancelled_excluded": True,
            "lookback_days": CURRENT_LOOKBACK_DAYS,
        },
        caveats=[
            "STLY uses stay_date < as_of - 180 days (verify definition).",
            "Percent change is OTB vs STLY, not calendar year-over-year.",
        ],
    )
