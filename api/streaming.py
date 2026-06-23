"""Map LangGraph astream_events output to normalized SSE JSON payloads."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from langchain_core.messages import AIMessage, ToolMessage

SKILL_MARKERS = ("SKILL.md", "/knowledge/skills/")


def sse_event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _extract_skill_path(args: dict[str, Any]) -> str | None:
    for key in ("file_path", "path", "target_file"):
        val = args.get(key)
        if isinstance(val, str) and any(m in val for m in SKILL_MARKERS):
            return val
    return None


def _final_answer_from_messages(messages: list[Any]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content = msg.content
            if isinstance(content, str) and content.strip():
                return content.strip()
            if isinstance(content, list):
                parts = [
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                joined = "\n".join(p for p in parts if p).strip()
                if joined:
                    return joined
    return ""


def _tool_args_from_event(data: dict[str, Any]) -> dict[str, Any]:
    inp = data.get("input")
    if isinstance(inp, dict):
        return inp
    return {}


async def stream_agent_events(
    agent: Any,
    thread_id: str,
    *,
    user_message: str | None = None,
    resume_decisions: list[dict[str, Any]] | None = None,
) -> AsyncIterator[str]:
    from langgraph.types import Command

    from agent.config import agent_run_config

    config = agent_run_config(thread_id)

    if resume_decisions is not None:
        graph_input = Command(resume={"decisions": resume_decisions})
    elif user_message:
        graph_input = {"messages": [{"role": "user", "content": user_message}]}
    else:
        yield sse_event({"type": "error", "message": "No message or resume payload"})
        return

    answer_parts: list[str] = []
    interrupted = False

    try:
        async for event in agent.astream_events(
            graph_input,
            config=config,
            version="v2",
        ):
            kind = event.get("event", "")
            data = event.get("data") or {}
            name = str(event.get("name") or "")

            if kind == "on_chat_model_stream":
                chunk = data.get("chunk")
                if chunk is None:
                    continue
                content = getattr(chunk, "content", None)
                if isinstance(content, str) and content:
                    answer_parts.append(content)
                    yield sse_event({"type": "token", "text": content})
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if text:
                                answer_parts.append(text)
                                yield sse_event({"type": "token", "text": text})

            elif kind == "on_tool_start":
                args = _tool_args_from_event(data)
                if name == "task":
                    yield sse_event(
                        {
                            "type": "subagent",
                            "subagent_type": args.get("subagent_type"),
                            "description": args.get("description"),
                        }
                    )
                elif name == "read_file":
                    path = _extract_skill_path(args)
                    if path:
                        yield sse_event({"type": "skill", "path": path})
                    else:
                        yield sse_event({"type": "tool_start", "name": name, "args": args})
                elif name == "write_todos":
                    items = args.get("items") or args.get("todos") or args
                    yield sse_event({"type": "todo", "todos": items})
                else:
                    yield sse_event({"type": "tool_start", "name": name, "args": args})

            elif kind == "on_tool_end":
                output = data.get("output")
                out_text = ""
                if isinstance(output, ToolMessage):
                    out_text = str(output.content or "")
                    tool = output.name or name
                else:
                    tool = name
                    out_text = str(output or "")
                if tool == "read_file" and "SKILL.md" in out_text:
                    for line in out_text.splitlines()[:3]:
                        if "SKILL.md" in line:
                            yield sse_event({"type": "skill", "path": line.strip()})
                            break
                yield sse_event(
                    {
                        "type": "tool_end",
                        "name": tool,
                        "output": out_text[:2000],
                    }
                )

        state = await agent.aget_state(config)
        if state.interrupts:
            interrupted = True
            action_requests: list[Any] = []
            for item in state.interrupts:
                iv = item.value if hasattr(item, "value") else item
                if isinstance(iv, dict):
                    action_requests.extend(iv.get("action_requests", []))
            yield sse_event({"type": "interrupt", "action_requests": action_requests})
            return

        messages = list((state.values or {}).get("messages", []))
        final = _final_answer_from_messages(messages) or "".join(answer_parts).strip()
        yield sse_event({"type": "done", "answer": final or "(no answer)"})

    except Exception as exc:
        if not interrupted:
            yield sse_event({"type": "error", "message": str(exc)})
