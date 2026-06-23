"""Typed ETL records matching schema.sql (excluding DB-generated keys)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RoomTypeLookup:
    space_type: str
    room_class: str
    display_name: str
    number_of_rooms: int


@dataclass(frozen=True, slots=True)
class MarketCodeLookup:
    market_code: str
    market_name: str
    macro_group: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ChannelCodeLookup:
    channel_code: str
    channel_name: str
    channel_group: str


@dataclass(frozen=True, slots=True)
class ReservationStay:
    reservation_id: str
    arrival_date: date
    departure_date: date
    stay_date: date
    reservation_status: str
    create_datetime: datetime
    cancellation_datetime: datetime | None
    guest_country: str | None
    is_block: bool
    is_walk_in: bool
    number_of_spaces: int
    space_type: str
    market_code: str
    channel_code: str
    source_name: str
    rate_plan_code: str
    daily_room_revenue_before_tax: Decimal
    daily_total_revenue_before_tax: Decimal
    nights: int
    adr_room: Decimal
    lead_time: int
    company_name: str | None = None
    travel_agent_name: str | None = None
