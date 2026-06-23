"""Presentation enrichment: lookup names in tool envelopes."""

from __future__ import annotations

from agent.tools.metrics import adr_analysis, describe_dataset, segment_mix
from agent.tools.risk import ota_dependency
from tests.conftest import invoke

EXPECTED_MARKET_NAMES = {
    "CNI": "Conference / Incentive Group",
    "CSR": "Corporate Negotiated",
    "OTA": "Online Travel Agency",
}

EXPECTED_ROOM_NAMES = {
    "KS": "Standard King",
    "TB": "Standard Twin",
    "EX": "Executive King",
}


def test_segment_mix_includes_segment_name():
    result = invoke(segment_mix, dimension="market_code")
    segments = result["key_numbers"]["segments"]
    assert segments
    for seg in segments:
        assert seg.get("segment_name"), f"missing segment_name for {seg['segment']}"
        code = seg["segment"]
        if code in EXPECTED_MARKET_NAMES:
            assert seg["segment_name"] == EXPECTED_MARKET_NAMES[code]


def test_segment_mix_channel_includes_segment_name():
    result = invoke(segment_mix, dimension="channel_code")
    for seg in result["key_numbers"]["segments"]:
        assert seg.get("segment_name")
        assert seg["segment_name"] != seg["segment"]


def test_adr_analysis_includes_room_type_names():
    result = invoke(adr_analysis)
    room_types = result["key_numbers"]["room_types"]
    assert room_types
    for rt in room_types:
        assert rt.get("name"), f"missing name for {rt['code']}"
        if rt["code"] in EXPECTED_ROOM_NAMES:
            assert rt["name"] == EXPECTED_ROOM_NAMES[rt["code"]]
    assert result["key_numbers"].get("highest_adr_type_name")


def test_ota_dependency_web_channel_breakdown():
    result = invoke(ota_dependency)
    kn = result["key_numbers"]
    assert kn["ota_room_nights"] == 71
    assert kn["web_channel_room_nights"] == 104
    assert kn["ota_market_on_web_channel_room_nights"] == 69
    assert kn["non_ota_on_web_channel_room_nights"] == 35
    assert kn["ota_market_on_web_channel_room_nights"] + kn[
        "non_ota_on_web_channel_room_nights"
    ] == kn["web_channel_room_nights"]
    assert kn["ota_market_on_web_channel_room_nights"] <= kn["ota_room_nights"]


def test_describe_dataset_label_maps():
    result = invoke(describe_dataset)
    maps = result["key_numbers"]["label_maps"]
    assert len(maps["market_code"]) == 10
    assert len(maps["channel_code"]) == 4
    assert len(maps["space_type"]) == 3
    assert maps["market_code"]["CNI"] == "Conference / Incentive Group"
    assert maps["channel_code"]["WEB"] == "Web / OTA Web"
    assert maps["space_type"]["KS"] == "Standard King"
    assert result["filters_and_definitions"]["segment_label_maps"] == maps
