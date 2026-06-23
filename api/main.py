"""FastAPI application — chat UI, SSE streaming, HITL resume."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.utils.uuid import uuid7

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from agent.config import CHECKPOINT_DATABASE_URL, ENV
from agent.graph import build_agent, use_postgres_checkpointer
from api.auth import BasicAuthMiddleware
from api.schemas import ChatStartRequest, ChatStartResponse, ResumeRequest
from api.streaming import stream_agent_events

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = REPO_ROOT / "static"

_pending: dict[str, dict[str, Any]] = {}


def _checkpoint_conn_string() -> str:
    url = CHECKPOINT_DATABASE_URL or os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("CHECKPOINT_DATABASE_URL or DATABASE_URL required in production")
    if "pooler.supabase.com" in url and "prepare_threshold" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}prepare_threshold=0"
    return url


@asynccontextmanager
async def lifespan(app: FastAPI):
    checkpointer_cm = None
    if use_postgres_checkpointer():
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        checkpointer_cm = AsyncPostgresSaver.from_conn_string(_checkpoint_conn_string())
        checkpointer = await checkpointer_cm.__aenter__()
        await checkpointer.setup()
        app.state.agent = build_agent(checkpointer=checkpointer)
        app.state.checkpointer_cm = checkpointer_cm
    else:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        from agent.config import CHECKPOINT_SQLITE

        Path(CHECKPOINT_SQLITE).parent.mkdir(parents=True, exist_ok=True)
        checkpointer_cm = AsyncSqliteSaver.from_conn_string(CHECKPOINT_SQLITE)
        checkpointer = await checkpointer_cm.__aenter__()
        app.state.agent = build_agent(checkpointer=checkpointer)
        app.state.checkpointer_cm = checkpointer_cm

    yield

    if checkpointer_cm is not None:
        await checkpointer_cm.__aexit__(None, None, None)


app = FastAPI(title="Revenue Manager Agent", lifespan=lifespan)
app.add_middleware(BasicAuthMiddleware)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="UI not found")
    return FileResponse(index_path)


@app.post("/api/chat", response_model=ChatStartResponse)
def start_chat(body: ChatStartRequest):
    thread_id = body.thread_id or str(uuid7())
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message required")
    _pending[thread_id] = {"message": message}
    return ChatStartResponse(thread_id=thread_id)


@app.get("/api/chat/{thread_id}/stream")
async def chat_stream(thread_id: str):
    payload = _pending.pop(thread_id, None)
    if payload is None:
        raise HTTPException(status_code=404, detail="No pending chat for this thread")

    agent = app.state.agent
    resume_decisions = payload.get("decisions")
    user_message = payload.get("message")

    return StreamingResponse(
        stream_agent_events(
            agent,
            thread_id,
            user_message=user_message,
            resume_decisions=resume_decisions,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat/{thread_id}/resume", response_model=ChatStartResponse)
def resume_chat(thread_id: str, body: ResumeRequest):
    _pending[thread_id] = {"decisions": body.decisions}
    return ChatStartResponse(thread_id=thread_id)
