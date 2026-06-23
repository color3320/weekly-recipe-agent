"""Unit tests for month resolution against as-of."""

from __future__ import annotations

import pytest

from agent.semantic import resolve_month


def test_resolve_month_same_year_forward():
    assert resolve_month("July", "2026-06-11") == "2026-07"
    assert resolve_month("August", "2026-06-11") == "2026-08"


def test_resolve_month_current_month():
    assert resolve_month("June", "2026-06-11") == "2026-06"


def test_resolve_month_rolls_to_next_year():
    assert resolve_month("May", "2026-06-11") == "2027-05"


def test_resolve_month_passthrough_ym():
    assert resolve_month("2026-07", "2026-06-11") == "2026-07"


def test_resolve_month_invalid():
    with pytest.raises(ValueError):
        resolve_month("NotAMonth", "2026-06-11")
