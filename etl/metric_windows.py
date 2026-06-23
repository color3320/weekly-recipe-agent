"""Verify-page metric window definitions (aligned to anchor 2026-06-11).

These predicates are the source of truth for etl/verify.py and the Part 5
semantic layer. Tune boundaries here only — never adjust loaded data.
"""

from __future__ import annotations

from datetime import date

# Lookback from as_of_date for the "current" reservation cohort.
CURRENT_LOOKBACK_DAYS = 180

# Status values observed on the data site.
STATUS_RESERVED = "Reserved"
STATUS_CANCELLED = "Cancelled"


def parse_as_of(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def otb_stay_predicate(as_of_param: str = "%(as_of_date)s") -> str:
    """On-the-books: Reserved, stay_date >= as_of_date (verify heading)."""
    return (
        f"reservation_status = '{STATUS_RESERVED}' "
        f"AND stay_date >= {as_of_param}::date"
    )


def current_reservation_predicate(as_of_param: str = "%(as_of_date)s") -> str:
    """Current block: arrival within lookback window ending at as_of_date."""
    return (
        f"arrival_date >= {as_of_param}::date - INTERVAL '{CURRENT_LOOKBACK_DAYS} days'"
    )


def last_year_reservation_predicate(as_of_param: str = "%(as_of_date)s") -> str:
    """Last-year block: arrivals before the current lookback window."""
    return (
        f"arrival_date < {as_of_param}::date - INTERVAL '{CURRENT_LOOKBACK_DAYS} days'"
    )


def stly_stay_predicate(as_of_param: str = "%(as_of_date)s") -> str:
    """STLY: Reserved stays before the current lookback boundary on stay_date."""
    return (
        f"reservation_status = '{STATUS_RESERVED}' "
        f"AND stay_date < {as_of_param}::date - INTERVAL '{CURRENT_LOOKBACK_DAYS} days'"
    )


def adr_reservation_predicate(as_of_param: str = "%(as_of_date)s") -> str:
    """ADR by room type: Reserved reservations in the current arrival window."""
    return (
        f"reservation_status = '{STATUS_RESERVED}' "
        f"AND arrival_date >= {as_of_param}::date - INTERVAL '{CURRENT_LOOKBACK_DAYS} days'"
    )


# --- Named SQL snippets used by verify.py ---

SQL_TOTAL_RESERVATIONS = "SELECT COUNT(DISTINCT reservation_id) FROM reservations_hackathon"

SQL_TOTAL_STAY_ROWS = "SELECT COUNT(*) FROM reservations_hackathon"

SQL_CURRENT_RESERVATIONS = f"""
SELECT COUNT(DISTINCT reservation_id)
FROM reservations_hackathon
WHERE {current_reservation_predicate()}
"""

SQL_LAST_YEAR_RESERVATIONS = f"""
SELECT COUNT(DISTINCT reservation_id)
FROM reservations_hackathon
WHERE {last_year_reservation_predicate()}
"""

SQL_CANCELLED_RESERVATIONS = f"""
SELECT COUNT(DISTINCT reservation_id)
FROM reservations_hackathon
WHERE reservation_status = '{STATUS_CANCELLED}'
"""

SQL_OTB_ROOM_NIGHTS = f"""
SELECT COALESCE(SUM(number_of_spaces), 0)
FROM reservations_hackathon
WHERE {otb_stay_predicate()}
"""

SQL_OTB_ROOM_REVENUE = f"""
SELECT COALESCE(SUM(daily_room_revenue_before_tax), 0)
FROM reservations_hackathon
WHERE {otb_stay_predicate()}
"""

SQL_OTB_TOTAL_REVENUE = f"""
SELECT COALESCE(SUM(daily_total_revenue_before_tax), 0)
FROM reservations_hackathon
WHERE {otb_stay_predicate()}
"""

SQL_STLY_ROOM_NIGHTS = f"""
SELECT COALESCE(SUM(number_of_spaces), 0)
FROM reservations_hackathon
WHERE {stly_stay_predicate()}
"""

SQL_STLY_TOTAL_REVENUE = f"""
SELECT COALESCE(SUM(daily_total_revenue_before_tax), 0)
FROM reservations_hackathon
WHERE {stly_stay_predicate()}
"""

SQL_ADR_BY_ROOM_TYPE = f"""
SELECT r.space_type,
       l.display_name,
       ROUND(AVG(r.adr_room), 2) AS adr
FROM (
  SELECT DISTINCT ON (reservation_id)
    reservation_id, space_type, adr_room
  FROM reservations_hackathon
  WHERE {adr_reservation_predicate()}
  ORDER BY reservation_id
) r
JOIN room_type_lookup l ON r.space_type = l.space_type
GROUP BY r.space_type, l.display_name
ORDER BY r.space_type
"""

SQL_OTB_NIGHTS_BY_MARKET = f"""
SELECT market_code, COALESCE(SUM(number_of_spaces), 0) AS room_nights
FROM reservations_hackathon
WHERE {otb_stay_predicate()}
GROUP BY market_code
ORDER BY market_code
"""

SQL_DATASET_AS_OF = "SELECT as_of_date FROM dataset_metadata WHERE id = 1"
