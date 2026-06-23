"""Segment share percentages must sum to ~100%."""

from __future__ import annotations

from agent.tools.metrics import segment_mix
from tests.conftest import invoke


def test_market_share_sums_to_100():
    result = invoke(segment_mix, dimension="market_code")
    shares = [s["share_pct"] for s in result["key_numbers"]["segments"]]
    assert abs(sum(shares) - 100.0) <= 0.1


def test_macro_group_share_sums_to_100():
    result = invoke(segment_mix, dimension="macro_group")
    shares = [s["share_pct"] for s in result["key_numbers"]["segments"]]
    assert abs(sum(shares) - 100.0) <= 0.1
