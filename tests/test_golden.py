"""Golden tests: tool outputs must match verify_targets.json."""

from __future__ import annotations

from decimal import Decimal

import pytest

from agent.tools.metrics import adr_analysis, describe_dataset, revenue_on_books, segment_mix
from agent.tools.pace import stly_comparison
from agent.tools.risk import cancellations
from tests.conftest import invoke


def test_describe_dataset_as_of(targets):
    result = invoke(describe_dataset)
    assert result["key_numbers"]["as_of_date"] == targets["anchor_date"]


def test_describe_dataset_row_counts(targets):
    result = invoke(describe_dataset)
    scalars = targets["scalars"]
    kn = result["key_numbers"]
    assert kn["total_reservations"] == scalars["total_reservations"]
    assert kn["total_stay_rows"] == scalars["total_stay_rows"]
    assert kn["current_reservations"] == scalars["current_reservations"]
    assert kn["last_year_reservations"] == scalars["last_year_reservations"]


def test_revenue_on_books_totals(targets):
    result = invoke(revenue_on_books)
    scalars = targets["scalars"]
    kn = result["key_numbers"]
    assert kn["room_nights"] == scalars["otb_room_nights"]
    assert Decimal(str(kn["revenue"])) == Decimal(str(scalars["otb_total_revenue_before_tax"]))


def test_revenue_on_books_room_revenue(targets, db, as_of):
    result = invoke(revenue_on_books, revenue_measure="room")
    scalars = targets["scalars"]
    assert Decimal(str(result["key_numbers"]["revenue"])) == Decimal(
        str(scalars["otb_room_revenue_before_tax"])
    )


def test_segment_mix_by_market(targets):
    result = invoke(segment_mix, dimension="market_code")
    expected = targets["otb_room_nights_by_market"]
    by_segment = {s["segment"]: s["room_nights"] for s in result["key_numbers"]["segments"]}
    for market, nights in expected.items():
        assert by_segment[market] == nights


def test_adr_analysis(targets):
    result = invoke(adr_analysis)
    expected = targets["adr_by_room_type"]
    actual = result["key_numbers"]["adr_by_room_type"]
    for room, adr in expected.items():
        assert Decimal(str(actual[room])) == Decimal(str(adr))


def test_stly_comparison(targets):
    result = invoke(stly_comparison)
    scalars = targets["scalars"]
    kn = result["key_numbers"]
    assert kn["stly_room_nights"] == scalars["stly_room_nights"]
    assert Decimal(str(kn["stly_total_revenue"])) == Decimal(
        str(scalars["stly_total_revenue_before_tax"])
    )
    assert kn["otb_room_nights"] == scalars["otb_room_nights"]


def test_cancellations_all_time(targets):
    result = invoke(cancellations)
    assert result["key_numbers"]["cancelled_reservations"] == targets["scalars"][
        "cancelled_reservations"
    ]
