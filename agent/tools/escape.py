"""Optional read-only SQL escape hatch."""

from __future__ import annotations

from langchain_core.tools import tool

from agent.db import ReadOnlySQLError, get_connection, run_readonly_query
from agent.semantic import get_as_of_date, make_envelope

@tool
def run_sql(query: str) -> dict:
    """Execute a read-only SELECT/WITH query. Prefer purpose-built tools when possible.

    Schema (exact column names — do NOT use `status`; use reservation_status):

    reservations_hackathon:
      reservation_stay_id, reservation_id, arrival_date, departure_date, stay_date,
      reservation_status ('Reserved' | 'Cancelled'), create_datetime, cancellation_datetime,
      guest_country, is_block, is_walk_in, number_of_spaces, space_type, market_code,
      channel_code, source_name, rate_plan_code, daily_room_revenue_before_tax,
      daily_total_revenue_before_tax, nights, adr_room, lead_time, company_name,
      travel_agent_name

    Lookups: room_type_lookup, market_code_lookup, channel_code_lookup

    Grain: one row per reservation_id × stay_date. Bookings = COUNT(DISTINCT reservation_id).
    Room nights = SUM(number_of_spaces). OTB: reservation_status = 'Reserved' AND stay_date >= as_of_date.
    """
    try:
        with get_connection() as conn:
            as_of = get_as_of_date(conn)
            rows = run_readonly_query(conn, query, {"as_of_date": as_of})
    except ReadOnlySQLError as exc:
        return make_envelope(
            headline=f"Query rejected: {exc}",
            key_numbers={"rows": []},
            filters_and_definitions={"query": query},
            caveats=["Only single SELECT or WITH statements are allowed."],
        )
    except Exception as exc:
        return make_envelope(
            headline=f"Query failed: {exc}",
            key_numbers={"rows": []},
            filters_and_definitions={"query": query},
            caveats=["Check SQL syntax and table/column names."],
        )

    serializable = []
    for row in rows[:100]:
        serializable.append({k: (str(v) if v is not None else None) for k, v in row.items()})

    return make_envelope(
        headline=f"Query returned {len(rows)} row(s)" + (" (truncated to 100)" if len(rows) > 100 else ""),
        key_numbers={
            "row_count": len(rows),
            "rows": serializable,
        },
        filters_and_definitions={
            "as_of_date": as_of,
            "query": query,
        },
        caveats=[
            "Secondary escape hatch — prefer purpose-built tools for business metrics.",
            "Results truncated to 100 rows in envelope.",
            "Use reservation_status, not status.",
        ],
    )
