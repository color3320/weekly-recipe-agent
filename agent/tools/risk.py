"""Risk and concentration analysis tools."""

from __future__ import annotations

from decimal import Decimal

from langchain_core.tools import tool

from agent.db import fetch_all, fetch_scalar, get_connection
from agent.semantic import (
    DatePurpose,
    FACT_TABLE,
    OTA_MARKET_CODE,
    RevenueMeasure,
    bind_params,
    cancellation_month_filter,
    cancelled_only_clause,
    date_column,
    get_as_of_date,
    make_envelope,
    otb_stay_predicate,
    params,
    quantize_money,
    resolve_month,
    revenue_column,
    stay_month_filter,
    sum_revenue,
    sum_room_nights,
)


@tool
def ota_dependency() -> dict:
    """OTA share of on-the-books room nights and revenue."""
    with get_connection() as conn:
        as_of = get_as_of_date(conn)
        p = params(as_of)
        where = otb_stay_predicate()

        total_nights = sum_room_nights(conn, where, as_of)
        total_revenue = sum_revenue(conn, where, RevenueMeasure.TOTAL, as_of)

        ota_nights = sum_room_nights(
            conn, f"{where} AND market_code = '{OTA_MARKET_CODE}'", as_of
        )
        ota_revenue = sum_revenue(
            conn,
            f"{where} AND market_code = '{OTA_MARKET_CODE}'",
            RevenueMeasure.TOTAL,
            as_of,
        )

        rev_col = revenue_column(RevenueMeasure.TOTAL)
        web_sql = f"""
        SELECT COALESCE(SUM(number_of_spaces), 0) AS web_room_nights,
               COALESCE(SUM(CASE WHEN market_code = '{OTA_MARKET_CODE}'
                                 THEN number_of_spaces ELSE 0 END), 0)
                   AS ota_market_on_web_nights,
               COALESCE(SUM(CASE WHEN market_code = '{OTA_MARKET_CODE}'
                                 THEN {rev_col} ELSE 0 END), 0)
                   AS ota_market_on_web_revenue
        FROM {FACT_TABLE}
        WHERE {where} AND channel_code = 'WEB'
        """
        web_row = fetch_all(conn, web_sql, p)[0]
        web_nights = int(web_row["web_room_nights"])
        ota_on_web_nights = int(web_row["ota_market_on_web_nights"])
        ota_on_web_revenue = quantize_money(web_row["ota_market_on_web_revenue"])
        non_ota_on_web_nights = web_nights - ota_on_web_nights

    nights_share = round(ota_nights / total_nights * 100, 2) if total_nights else 0.0
    revenue_share = (
        round(float(ota_revenue / total_revenue * 100), 2) if total_revenue > 0 else 0.0
    )

    caveats = []
    if revenue_share > 30:
        caveats.append(f"OTA revenue share ({revenue_share}%) exceeds 30% — elevated dependency risk.")

    return make_envelope(
        headline=(
            f"OTA accounts for {revenue_share}% of OTB revenue "
            f"({ota_nights:,} of {total_nights:,} room nights)"
        ),
        key_numbers={
            "ota_room_nights": ota_nights,
            "ota_revenue": float(ota_revenue),
            "total_room_nights": total_nights,
            "total_revenue": float(total_revenue),
            "ota_share_pct_nights": nights_share,
            "ota_share_pct_revenue": revenue_share,
            "web_channel_room_nights": web_nights,
            "ota_market_on_web_channel_room_nights": ota_on_web_nights,
            "non_ota_on_web_channel_room_nights": non_ota_on_web_nights,
            "ota_market_on_web_channel_revenue": float(ota_on_web_revenue),
        },
        filters_and_definitions={
            "as_of_date": as_of,
            "window": "otb",
            "date_field": date_column(DatePurpose.STAY),
            "revenue_field": revenue_column(RevenueMeasure.TOTAL),
            "cancelled_excluded": True,
            "ota_market_code": OTA_MARKET_CODE,
            "ota_market_vs_web_channel": (
                "ota_room_nights = OTA market across ALL channels. "
                "web_channel_room_nights = WEB booking path (OTA + non-OTA markets). "
                "Never substitute one for the other."
            ),
        },
        caveats=(caveats or [])
        + [
            "OTA defined as market_code = 'OTA' (all channels).",
            (
                f"WEB channel has {web_nights} room nights total — "
                f"{ota_on_web_nights} OTA-market + {non_ota_on_web_nights} non-OTA. "
                f"Do not describe ota_room_nights ({ota_nights}) as a subset of WEB."
            ),
        ],
    )


@tool
def concentration(top_n: int = 10, large_booking_rooms: int = 5) -> dict:
    """Revenue concentration by company and large multi-room bookings."""
    with get_connection() as conn:
        as_of = get_as_of_date(conn)
        p = params(as_of)
        where = otb_stay_predicate()
        rev_col = revenue_column(RevenueMeasure.TOTAL)

        sql = f"""
        SELECT COALESCE(company_name, '(no company)') AS company,
               COUNT(DISTINCT reservation_id) AS reservations,
               COALESCE(SUM(number_of_spaces), 0) AS room_nights,
               COALESCE(SUM({rev_col}), 0) AS revenue
        FROM {FACT_TABLE}
        WHERE {where}
        GROUP BY COALESCE(company_name, '(no company)')
        ORDER BY revenue DESC
        LIMIT %(top_n)s
        """
        p_top = {**p, "top_n": top_n}
        rows = fetch_all(conn, sql, p_top)

        total_revenue = sum_revenue(conn, where, RevenueMeasure.TOTAL, as_of)
        top_companies = [
            {
                "company": r["company"],
                "reservations": int(r["reservations"]),
                "room_nights": int(r["room_nights"]),
                "revenue": float(quantize_money(r["revenue"])),
            }
            for r in rows
        ]
        top3_revenue = sum(quantize_money(r["revenue"]) for r in rows[:3])
        top3_share = (
            round(float(top3_revenue / total_revenue * 100), 2)
            if total_revenue > 0
            else 0.0
        )

        large_sql = f"""
        SELECT COUNT(DISTINCT reservation_id)
        FROM (
          SELECT reservation_id, MAX(number_of_spaces) AS max_rooms
          FROM {FACT_TABLE}
          WHERE {where}
          GROUP BY reservation_id
          HAVING MAX(number_of_spaces) >= %(min_rooms)s
        ) large
        """
        p_large = {**p, "min_rooms": large_booking_rooms}
        large_booking_count = int(fetch_scalar(conn, large_sql, p_large) or 0)

    return make_envelope(
        headline=(
            f"Top {min(top_n, len(top_companies))} companies hold "
            f"{top3_share}% of OTB revenue; {large_booking_count} bookings with "
            f">={large_booking_rooms} rooms"
        ),
        key_numbers={
            "top_companies": top_companies,
            "top3_revenue_share_pct": top3_share,
            "total_otb_revenue": float(total_revenue),
            "large_booking_count": large_booking_count,
            "large_booking_threshold_rooms": large_booking_rooms,
        },
        filters_and_definitions={
            "as_of_date": as_of,
            "window": "otb",
            "date_field": date_column(DatePurpose.STAY),
            "revenue_field": rev_col,
            "cancelled_excluded": True,
            "top_n": top_n,
        },
        caveats=[
            "Reservations without company_name grouped as '(no company)'.",
            "Large booking threshold is max rooms per reservation on any stay night.",
        ],
    )


@tool
def cancellations(month: str | None = None) -> dict:
    """Cancelled reservation count, optionally filtered by cancellation month (YYYY-MM or name)."""
    with get_connection() as conn:
        as_of = get_as_of_date(conn)
        resolved_month = resolve_month(month, as_of) if month else None
        where = cancelled_only_clause()
        month_clause, month_params = cancellation_month_filter(resolved_month)
        where += month_clause
        p = bind_params(as_of, month_params)

        sql = f"""
        SELECT COUNT(DISTINCT reservation_id)
        FROM {FACT_TABLE}
        WHERE {where}
        """
        count = int(fetch_scalar(conn, sql, p) or 0)

        nights_sql = f"""
        SELECT COALESCE(SUM(number_of_spaces), 0)
        FROM {FACT_TABLE}
        WHERE {where}
        """
        room_nights = int(fetch_scalar(conn, nights_sql, p) or 0)

        revenue_sql = f"""
        SELECT COALESCE(SUM(daily_total_revenue_before_tax), 0)
        FROM {FACT_TABLE}
        WHERE {where}
        """
        lost_revenue = quantize_money(fetch_scalar(conn, revenue_sql, p))

    period = resolved_month or "all time"
    return make_envelope(
        headline=f"{count} cancelled reservations ({room_nights:,} room nights, ${lost_revenue:,.2f} lost revenue) — {period}",
        key_numbers={
            "cancelled_reservations": count,
            "cancelled_room_nights": room_nights,
            "lost_total_revenue": float(lost_revenue),
        },
        filters_and_definitions={
            "as_of_date": as_of,
            "date_field": date_column(DatePurpose.CANCELLATION),
            "revenue_field": revenue_column(RevenueMeasure.TOTAL),
            "cancelled_excluded": False,
            "status_filter": "Cancelled",
            "month_filter": resolved_month,
            "month_input": month,
        },
        caveats=[
            "Uses cancellation_datetime for period filter, not stay_date.",
            "Lost revenue is sum of stay-row revenue for cancelled reservations.",
            "Month without year resolves to next occurrence on/after as-of.",
        ],
    )


@tool
def group_vs_transient(month: str | None = None) -> dict:
    """OTB split between group (is_block) and transient business.

    month: YYYY-MM or month name (resolved against as-of).
    """
    with get_connection() as conn:
        as_of = get_as_of_date(conn)
        resolved_month = resolve_month(month, as_of) if month else None
        where = otb_stay_predicate()
        month_clause, month_params = stay_month_filter(resolved_month)
        full_where = where + month_clause
        p = bind_params(as_of, month_params)
        rev_col = revenue_column(RevenueMeasure.TOTAL)

        sql = f"""
        SELECT is_block,
               COALESCE(SUM(number_of_spaces), 0) AS room_nights,
               COALESCE(SUM({rev_col}), 0) AS revenue,
               COUNT(DISTINCT reservation_id) AS reservations
        FROM {FACT_TABLE}
        WHERE {full_where}
        GROUP BY is_block
        ORDER BY is_block DESC
        """
        rows = fetch_all(conn, sql, p)

        segments = {}
        for r in rows:
            label = "group" if r["is_block"] else "transient"
            segments[label] = {
                "reservations": int(r["reservations"]),
                "room_nights": int(r["room_nights"]),
                "revenue": float(quantize_money(r["revenue"])),
            }

        total_nights = sum(s["room_nights"] for s in segments.values())
        total_revenue = sum(Decimal(str(s["revenue"])) for s in segments.values())

        for label, seg in segments.items():
            seg["share_pct_nights"] = (
                round(seg["room_nights"] / total_nights * 100, 2) if total_nights else 0.0
            )
            seg["share_pct_revenue"] = (
                round(seg["revenue"] / float(total_revenue) * 100, 2)
                if total_revenue > 0
                else 0.0
            )

    group = segments.get("group", {"room_nights": 0, "revenue": 0.0, "share_pct_revenue": 0.0})
    period = f" in {resolved_month}" if resolved_month else ""
    return make_envelope(
        headline=(
            f"Group business{period}: {group.get('share_pct_revenue', 0)}% of OTB revenue "
            f"({group.get('room_nights', 0):,} room nights)"
        ),
        key_numbers={
            "group": segments.get("group"),
            "transient": segments.get("transient"),
            "total_room_nights": total_nights,
            "total_revenue": float(total_revenue),
        },
        filters_and_definitions={
            "as_of_date": as_of,
            "window": "otb",
            "date_field": date_column(DatePurpose.STAY),
            "revenue_field": rev_col,
            "cancelled_excluded": True,
            "group_definition": "is_block = true",
            "month_filter": resolved_month,
            "month_input": month,
        },
        caveats=[
            "Group defined by is_block flag on reservation, not macro_group.",
            "reservations = COUNT(DISTINCT reservation_id) per segment.",
        ],
    )
