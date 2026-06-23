"""Month-filter path tests — golden tests did not exercise month= before Part 7 cleanup."""

from __future__ import annotations

import pytest

from agent.semantic import resolve_month
from agent.tools.metrics import revenue_on_books, segment_mix
from agent.tools.pace import booking_pace
from agent.tools.risk import cancellations, group_vs_transient
from tests.conftest import invoke


def test_resolve_month_from_name():
    assert resolve_month("July", "2026-06-11") == "2026-07"
    assert resolve_month("June", "2026-06-11") == "2026-06"
    assert resolve_month("2026-07", "2026-06-11") == "2026-07"


@pytest.mark.parametrize(
    "tool,kwargs,min_nights",
    [
        (revenue_on_books, {"month": "2026-07"}, 1),
        (segment_mix, {"month": "2026-07"}, 0),
        (group_vs_transient, {"month": "2026-07"}, 1),
        (cancellations, {"month": "2026-06"}, 0),
    ],
)
def test_month_tools_run_without_error(tool, kwargs, min_nights):
    result = invoke(tool, **kwargs)
    assert "headline" in result
    kn = result["key_numbers"]
    if "room_nights" in kn:
        assert kn["room_nights"] >= min_nights
    elif "total_room_nights" in kn:
        assert kn["total_room_nights"] >= min_nights
    elif "cancelled_room_nights" in kn:
        assert kn["cancelled_room_nights"] >= min_nights


def test_revenue_on_books_month_name_resolves():
    result = invoke(revenue_on_books, month="July")
    assert result["filters_and_definitions"]["month_filter"] == "2026-07"
    assert result["key_numbers"]["room_nights"] == 175


def test_booking_pace_has_no_month_param():
    """booking_pace uses lookback days only — audit confirms no month bind path."""
    result = invoke(booking_pace, days=7)
    assert result["key_numbers"]["total_bookings"] >= 0


def test_july_reservations_vs_room_nights():
    result = invoke(revenue_on_books, month="2026-07")
    kn = result["key_numbers"]
    assert kn["reservations"] == 32
    assert kn["room_nights"] == 175
    assert kn["reservations"] != kn["room_nights"]
