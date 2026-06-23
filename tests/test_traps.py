"""Trap tests: correct rule matches verify; naive wrong approach differs."""

from __future__ import annotations

from decimal import Decimal

import pytest

from agent.db import fetch_scalar
from agent.semantic import (
    FACT_TABLE,
    adr_by_room_type,
    count_reservations,
    count_stay_rows,
    otb_stay_predicate,
    params,
    quantize_money,
    sum_revenue,
    sum_room_nights,
)
from agent.semantic import RevenueMeasure
from etl.metric_windows import STATUS_RESERVED


def test_trap_rows_vs_reservations(db, as_of, targets):
    correct = count_reservations(db)
    wrong = count_stay_rows(db)
    assert correct == targets["scalars"]["total_reservations"]
    assert wrong == targets["scalars"]["total_stay_rows"]
    assert correct != wrong


def test_trap_room_nights_vs_row_count(db, as_of, targets):
    where = otb_stay_predicate()
    correct = sum_room_nights(db, where, as_of)
    wrong = count_stay_rows(db, where, as_of)
    assert correct == targets["scalars"]["otb_room_nights"]
    assert correct != wrong


def test_trap_cancelled_inclusion_otb_revenue(db, as_of, targets):
    where_reserved = otb_stay_predicate()
    correct = sum_revenue(db, where_reserved, RevenueMeasure.TOTAL, as_of)
    where_with_cancelled = f"stay_date >= %(as_of_date)s::date"
    wrong = sum_revenue(db, where_with_cancelled, RevenueMeasure.TOTAL, as_of)
    assert correct == Decimal(str(targets["scalars"]["otb_total_revenue_before_tax"]))
    assert correct != wrong


def test_trap_wrong_date_field_otb_nights(db, as_of, targets):
    where_stay = otb_stay_predicate()
    correct = sum_room_nights(db, where_stay, as_of)
    # Naive mistake: use booking date (create_datetime) instead of stay_date for OTB
    where_pace = (
        f"reservation_status = '{STATUS_RESERVED}' "
        f"AND create_datetime::date >= %(as_of_date)s::date"
    )
    wrong = sum_room_nights(db, where_pace, as_of)
    assert correct == targets["scalars"]["otb_room_nights"]
    assert correct != wrong


def test_trap_wrong_revenue_field_otb(db, as_of, targets):
    where = otb_stay_predicate()
    correct = sum_revenue(db, where, RevenueMeasure.TOTAL, as_of)
    wrong = sum_revenue(db, where, RevenueMeasure.ROOM, as_of)
    assert correct == Decimal(str(targets["scalars"]["otb_total_revenue_before_tax"]))
    assert wrong == Decimal(str(targets["scalars"]["otb_room_revenue_before_tax"]))
    assert correct != wrong


def test_trap_adr_reservation_vs_stay_weighted(db, as_of, targets):
    correct = adr_by_room_type(db, as_of)
    for room, expected_adr in targets["adr_by_room_type"].items():
        assert quantize_money(correct[room]) == Decimal(str(expected_adr))

        wrong_sql = f"""
        SELECT ROUND(
          COALESCE(SUM(daily_room_revenue_before_tax), 0) /
          NULLIF(COALESCE(SUM(number_of_spaces), 0), 0),
          2
        )
        FROM {FACT_TABLE}
        WHERE {otb_stay_predicate()}
          AND space_type = %(room)s
        """
        wrong = fetch_scalar(db, wrong_sql, {**params(as_of), "room": room})
        wrong = quantize_money(wrong) if wrong is not None else Decimal("0")
        assert correct[room] != wrong, f"ADR trap for {room} should differ"


def test_trap_july_bookings_not_room_nights():
    from agent.tools.metrics import revenue_on_books
    from tests.conftest import invoke

    result = invoke(revenue_on_books, month="2026-07")
    kn = result["key_numbers"]
    assert kn["reservations"] == 32
    assert kn["room_nights"] == 175
    assert kn["reservations"] < kn["room_nights"]
