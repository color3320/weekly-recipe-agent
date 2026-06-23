"""Agent runtime configuration — model id and paths live here, not hardcoded in graph.py."""

from __future__ import annotations

import os
from pathlib import Path

# Gemini via GOOGLE_API_KEY; override with AGENT_MODEL for experiments.
# Verified against LangChain + Deep Agents docs (2026-06): gemini-2.5-flash on Developer API.
MODEL: str = os.environ.get("AGENT_MODEL", "google_genai:gemini-2.5-flash")

REPO_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_ROOT = Path(__file__).resolve().parent / "knowledge"
SYSTEM_PROMPT_PATH = REPO_ROOT / "prompts" / "system_prompt.md"
BRIEFINGS_DIR = KNOWLEDGE_ROOT / "briefings"

# Dev persistence: MemorySaver in-process; set CHECKPOINT_SQLITE for durable local threads.
CHECKPOINT_SQLITE = os.environ.get("CHECKPOINT_SQLITE", str(REPO_ROOT / "data" / "agent_checkpoints.db"))

# production | development — production uses Postgres checkpointer when CHECKPOINT_DATABASE_URL is set.
ENV: str = os.environ.get("ENV", "development")

# Postgres checkpointer URL; defaults to DATABASE_URL in production.
CHECKPOINT_DATABASE_URL: str | None = os.environ.get("CHECKPOINT_DATABASE_URL") or (
    os.environ.get("DATABASE_URL") if ENV == "production" else None
)

# HTTP basic auth for the public agent URL (Render deploy).
BASIC_AUTH_USER: str | None = os.environ.get("BASIC_AUTH_USER")
BASIC_AUTH_PASS: str | None = os.environ.get("BASIC_AUTH_PASS")

# LangGraph step budget per turn (default 25 is tight when the model over-plans).
AGENT_RECURSION_LIMIT: int = int(os.environ.get("AGENT_RECURSION_LIMIT", "40"))


def agent_run_config(thread_id: str) -> dict:
    """Shared invoke config for eval CLI and API streaming."""
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": AGENT_RECURSION_LIMIT}
