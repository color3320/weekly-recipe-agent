"""Purpose-built agent tools."""

from agent.tools.escape import run_sql
from agent.tools.metrics import adr_analysis, describe_dataset, revenue_on_books, segment_mix
from agent.tools.pace import booking_pace, stly_comparison, whats_changed
from agent.tools.risk import (
    cancellations,
    concentration,
    group_vs_transient,
    ota_dependency,
)

ALL_TOOLS = [
    describe_dataset,
    revenue_on_books,
    segment_mix,
    adr_analysis,
    whats_changed,
    booking_pace,
    stly_comparison,
    ota_dependency,
    concentration,
    cancellations,
    group_vs_transient,
    run_sql,
]

__all__ = [
    "ALL_TOOLS",
    "describe_dataset",
    "revenue_on_books",
    "segment_mix",
    "adr_analysis",
    "whats_changed",
    "booking_pace",
    "stly_comparison",
    "ota_dependency",
    "concentration",
    "cancellations",
    "group_vs_transient",
    "run_sql",
]
