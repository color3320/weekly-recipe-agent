"""Single create_deep_agent() assembly for the Revenue Manager harness."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from agent.config import (
    BRIEFINGS_DIR,
    CHECKPOINT_DATABASE_URL,
    CHECKPOINT_SQLITE,
    ENV,
    KNOWLEDGE_ROOT,
    MODEL,
    SYSTEM_PROMPT_PATH,
)
from agent.tools import ALL_TOOLS

# Purpose-built tools only — analyst fetches; orchestrator keeps run_sql behind HITL.
ANALYST_TOOLS = [t for t in ALL_TOOLS if t.name != "run_sql"]

_DATA_ANALYST_PROMPT = """\
You are the data-analyst subagent. Your job is to fetch numbers — not to brief the GM.

- Call Part 5 metric tools to answer the delegated question.
- Return STRUCTURED findings: headline metrics, segment/channel breakdowns (use segment_name from envelopes), and caveats rephrased for upstream use.
- Do NOT include tool names, SQL, table/column names, or envelope field names in findings.
- Do not write GM narrative, recommendations, or load briefing-style skills.
- Never call run_sql.
"""

_REVENUE_STRATEGIST_PROMPT = """\
You are the revenue-strategist subagent. You interpret findings — you do not query the database.

- You receive structured findings from the analyst (or the orchestrator). Turn them into commercial judgment.
- Load relevant SKILL.md files from /knowledge/skills/ for pace health, OTA risk, displacement, briefing style, etc.
- Open with BLUF — direct answer to the question in 1–2 sentences before any table or detail.
- Use full segment/channel names (never bare codes). Never expose SQL, tool names, or database vocabulary.
- Output: BLUF, supporting drivers, caveat, risk, and actionable levers in GM-ready language.
- Do not call any database or metric tools.
"""


def _load_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def _knowledge_backend() -> CompositeBackend:
    """Route on-disk skills/memory through FilesystemBackend; scratch + framework internals stay in StateBackend."""
    BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)
    return CompositeBackend(
        default=StateBackend(),
        routes={
            "/knowledge/": FilesystemBackend(
                root_dir=str(KNOWLEDGE_ROOT),
                virtual_mode=True,
            ),
        },
    )


def use_postgres_checkpointer() -> bool:
    """True when production env expects a Postgres-backed checkpointer."""
    return ENV == "production" or bool(CHECKPOINT_DATABASE_URL)


def _make_checkpointer() -> Any:
    """SQLite file for durable local threads; falls back to MemorySaver if sqlite extra missing."""
    if use_postgres_checkpointer():
        # AsyncPostgresSaver is wired in api.main lifespan — sync fallback for CLI only.
        return MemorySaver()
    if CHECKPOINT_SQLITE:
        try:
            import sqlite3

            from langgraph.checkpoint.sqlite import SqliteSaver

            Path(CHECKPOINT_SQLITE).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(CHECKPOINT_SQLITE, check_same_thread=False)
            return SqliteSaver(conn)
        except ImportError:
            pass
    return MemorySaver()


def build_agent(*, checkpointer: Any | None = None, store: Any | None = None):
    """Assemble the Revenue Manager deep agent (one deliberate create_deep_agent call)."""
    if checkpointer is None:
        checkpointer = _make_checkpointer()
    if store is None:
        # Cross-thread store for prod-style memory; InMemoryStore is fine for local dev (Part 8 needs persistent).
        store = InMemoryStore()

    backend = _knowledge_backend()

    data_analyst = {
        "name": "data-analyst",
        "description": (
            "Fetches hotel revenue data via Part 5 metric tools. "
            "Use for multi-tool pulls, month breakdowns, segment/channel cross-checks. "
            "Returns structured findings — not GM narrative."
        ),
        "system_prompt": _DATA_ANALYST_PROMPT,
        "tools": ANALYST_TOOLS,
    }

    revenue_strategist = {
        "name": "revenue-strategist",
        "description": (
            "Turns analyst findings into GM-ready commercial judgment and recommendations. "
            "Use when the question is primarily 'what should we do?' or needs briefing-style narrative. "
            "Has no database access."
        ),
        "system_prompt": _REVENUE_STRATEGIST_PROMPT,
        "tools": [],
    }

    return create_deep_agent(
        # Gemini persona + tool-first briefing shape; trap detail lives in AGENTS.md memory.
        model=MODEL,
        system_prompt=_load_system_prompt(),
        # All 12 Part 5 tools on the orchestrator; analyst subagent gets the 11 purpose-built ones.
        tools=ALL_TOOLS,
        # Progressive disclosure: SKILL.md trees under agent/knowledge/skills/.
        skills=["/knowledge/skills/"],
        # Always-on operating memory: grain traps, delegation rules, briefing scaffold pointer.
        memory=["/knowledge/AGENTS.md"],
        # Isolated fetch vs interpret: analyst has DB tools; strategist is narrative-only.
        subagents=[data_analyst, revenue_strategist],
        # Same composite backend: on-disk knowledge + thread-scoped scratch/briefings.
        backend=backend,
        # Built-in write_todos ships with deepagents — no extra wiring needed for planning.
        # Gate arbitrary SQL only; purpose-built tools run without approval.
        interrupt_on={
            "run_sql": {"allowed_decisions": ["approve", "reject"]},
        },
        # Required for multi-turn threads and HITL resume after run_sql interrupts.
        checkpointer=checkpointer,
        store=store,
    )


_agent: Any | None = None


def get_agent():
    """Lazy singleton — avoids resolving the Gemini model at import time."""
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent
