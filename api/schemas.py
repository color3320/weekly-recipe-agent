"""Request/response models for the chat API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatStartRequest(BaseModel):
    message: str = Field(..., min_length=1)
    thread_id: str | None = None


class ChatStartResponse(BaseModel):
    thread_id: str


class ResumeRequest(BaseModel):
    decisions: list[dict[str, Any]]
