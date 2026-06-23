"""Eval harness — real model + DB; logs answers, tools, skills, and subagent activity."""

from __future__ import annotations

import json
import os
import sys
import textwrap
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.utils.uuid import uuid7
from langgraph.types import Command

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from agent.config import agent_run_config
from agent.graph import build_agent


def _require_api_key() -> None:
    if not any(
        os.environ.get(name)
        for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")
    ):
        raise SystemExit(
            "Set an API key in .env: GOOGLE_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY."
        )

# Section 11 example questions (what_do_i_want_to_do.md).
SECTION_11_QUESTIONS: list[str] = [
    "What revenue is on the books by month?",
    "Which segments are driving July?",
    "How much of July is group business?",
    "Are we too dependent on OTA?",
    "What changed in the last 7 days for future stays?",
    "Which room type is generating the highest ADR?",
    "How much business was cancelled in June?",
    "What share of our future business is corporate?",
    "Which companies are contributing the most revenue?",
    "Is our business concentrated in a few large bookings?",
]

# Presentation smoke — BLUF, lookup names, no database vocabulary.
PRESENTATION_SMOKE_QUESTIONS: list[str] = [
    "What is the average booking lead time by market segment for July on-the-books stays?",
    "Which segments are driving July?",
    "Which room type is generating the highest ADR?",
]

# Hard questions probing judgment and data traps.
HARD_QUESTIONS: list[str] = [
    "Are we too dependent on OTA, and what should we do?",
    "Is July's pace healthy vs last year?",
    "How many bookings do we have for July?",
    "Should we accept a 40-room group block in July at a discounted rate?",
    "What's driving July revenue — and is the mix a risk?",
]

SKILL_MARKERS = ("SKILL.md", "/knowledge/skills/")


@dataclass
class RunLog:
    question: str
    answer: str = ""
    tools_called: list[str] = field(default_factory=list)
    skills_loaded: list[str] = field(default_factory=list)
    subagent_tasks: list[dict[str, Any]] = field(default_factory=list)
    interrupted: bool = False
    error: str | None = None


def _tool_name(call: Any) -> str:
    if isinstance(call, dict):
        return str(call.get("name", ""))
    return str(getattr(call, "name", ""))


def _tool_args(call: Any) -> dict[str, Any]:
    if isinstance(call, dict):
        args = call.get("args")
        return args if isinstance(args, dict) else {}
    args = getattr(call, "args", None)
    return args if isinstance(args, dict) else {}


def _extract_path_from_read(args: dict[str, Any]) -> str | None:
    for key in ("file_path", "path", "target_file"):
        val = args.get(key)
        if isinstance(val, str):
            return val
    return None


def _walk_messages(messages: list[Any], log: RunLog) -> None:
    """Collect tool, skill, and subagent activity from a message list."""
    tool_call_index: dict[str, str] = {}

    for msg in messages:
        if isinstance(msg, AIMessage) or (isinstance(msg, dict) and msg.get("type") == "ai"):
            tool_calls = (
                msg.tool_calls
                if isinstance(msg, AIMessage)
                else msg.get("tool_calls", [])
            )
            for call in tool_calls or []:
                name = _tool_name(call)
                if not name:
                    continue
                log.tools_called.append(name)
                call_id = (
                    call.get("id")
                    if isinstance(call, dict)
                    else getattr(call, "id", None)
                )
                if call_id:
                    tool_call_index[str(call_id)] = name
                if name == "task":
                    args = _tool_args(call)
                    log.subagent_tasks.append(
                        {
                            "subagent_type": args.get("subagent_type"),
                            "description": args.get("description"),
                        }
                    )
                if name == "read_file":
                    path = _extract_path_from_read(_tool_args(call))
                    if path and any(m in path for m in SKILL_MARKERS):
                        log.skills_loaded.append(path)

        if isinstance(msg, ToolMessage) or (
            isinstance(msg, dict) and msg.get("type") == "tool"
        ):
            name = (
                msg.name
                if isinstance(msg, ToolMessage)
                else msg.get("name", "")
            )
            if name == "read_file":
                content = (
                    msg.content
                    if isinstance(msg, ToolMessage)
                    else msg.get("content", "")
                )
                if isinstance(content, str) and "SKILL.md" in content:
                    for line in content.splitlines()[:3]:
                        if "SKILL.md" in line:
                            log.skills_loaded.append(line.strip())
                            break


def _final_answer(messages: list[Any]) -> str:
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
        if isinstance(msg, dict) and msg.get("type") == "ai":
            content = msg.get("content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return "(no final answer)"


def _state_messages(state: Any) -> list[Any]:
    if isinstance(state, dict):
        return list(state.get("messages", []))
    return []


def run_question(
    agent: Any,
    question: str,
    *,
    thread_id: str | None = None,
    resume_decisions: list[dict[str, Any]] | None = None,
) -> RunLog:
    """Invoke the agent for one question; optionally resume after HITL."""
    log = RunLog(question=question)
    config = agent_run_config(thread_id or str(uuid7()))

    try:
        if resume_decisions is not None:
            output = agent.invoke(
                Command(resume={"decisions": resume_decisions}),
                config=config,
                version="v2",
            )
        else:
            output = agent.invoke(
                {"messages": [{"role": "user", "content": question}]},
                config=config,
                version="v2",
            )

        if output.interrupts:
            log.interrupted = True
            log.answer = f"[INTERRUPTED — {len(output.interrupts)} pending approval(s)]"
            iv = output.interrupts[0].value
            for action in iv.get("action_requests", []):
                log.tools_called.append(f"pending:{action.get('name')}")
            return log

        messages = _state_messages(output.value)
        _walk_messages(messages, log)
        log.answer = _final_answer(messages)
    except Exception as exc:
        log.error = str(exc)

    return log


def print_log(log: RunLog, *, index: int | None = None) -> None:
    prefix = f"[{index}] " if index is not None else ""
    print("=" * 72)
    print(f"{prefix}Q: {log.question}")
    if log.error:
        print(f"ERROR: {log.error}")
        return
    print("-" * 72)
    print("ANSWER:")
    print(textwrap.indent(log.answer, "  "))
    print("-" * 72)
    print(f"Tools called ({len(log.tools_called)}): {', '.join(log.tools_called) or '(none)'}")
    print(f"Skills loaded ({len(log.skills_loaded)}): {', '.join(log.skills_loaded) or '(none)'}")
    if log.subagent_tasks:
        print(f"Subagent tasks ({len(log.subagent_tasks)}):")
        for task in log.subagent_tasks:
            print(f"  - {json.dumps(task, ensure_ascii=False)}")
    if log.interrupted:
        print("(run paused for human approval)")


def run_suite(agent: Any, questions: list[str], *, label: str) -> list[RunLog]:
    print(f"\n{'#' * 72}\n# {label} ({len(questions)} questions)\n{'#' * 72}")
    logs: list[RunLog] = []
    for i, q in enumerate(questions, 1):
        log = run_question(agent, q)
        print_log(log, index=i)
        logs.append(log)
    return logs


def run_multiturn_demo(agent: Any) -> None:
    """Prove checkpointer holds context across turns in one thread."""
    thread_id = str(uuid7())
    print(f"\n{'#' * 72}\n# MULTI-TURN (thread_id={thread_id})\n{'#' * 72}")

    turn1 = run_question(
        agent,
        "What is our total OTB room revenue? Just the headline number.",
        thread_id=thread_id,
    )
    print_log(turn1, index=1)

    turn2 = run_question(
        agent,
        "You just told me that number — now break it down by market segment.",
        thread_id=thread_id,
    )
    print_log(turn2, index=2)

    refers_back = any(
        word in turn2.answer.lower()
        for word in ("as i", "above", "previous", "already", "mentioned", "otb", "revenue")
    )
    print("-" * 72)
    print(
        f"Context check: turn 2 {'appears to' if refers_back else 'does NOT'} "
        "reference prior turn / OTB context."
    )


def run_hitl_demo(agent: Any) -> None:
    """Fire HITL on run_sql — test reject then approve in separate threads."""
    print(f"\n{'#' * 72}\n# HITL — run_sql REJECT\n{'#' * 72}")
    thread_reject = str(uuid7())
    # No Part 5 tool computes average lead_time by market — must force run_sql.
    q = (
        "You MUST use run_sql ONLY (no other tools). Compute AVG(lead_time) grouped by "
        "market_code for July 2026 OTB stays: reservation_status = 'Reserved', "
        "stay_date >= as-of, TO_CHAR(stay_date,'YYYY-MM') = '2026-07'."
    )
    pending = run_question(agent, q, thread_id=thread_reject)
    print_log(pending, index=1)

    if pending.interrupted:
        rejected = run_question(
            agent,
            q,
            thread_id=thread_reject,
            resume_decisions=[
                {
                    "type": "reject",
                    "message": (
                        "User rejected run_sql. Do not retry run_sql. "
                        "Explain that average lead time by market is not available "
                        "via purpose-built tools and suggest a manual analyst pull."
                    ),
                }
            ],
        )
        print_log(rejected, index=2)
        if rejected.error:
            print(f"HITL reject recovery FAILED: {rejected.error}")
        elif rejected.interrupted:
            print("HITL reject recovery FAILED: still interrupted after reject")
        else:
            print("HITL reject recovery OK: agent continued after rejection")
    else:
        print("(run_sql did not interrupt — model may have used purpose-built tools instead)")

    print(f"\n{'#' * 72}\n# HITL — run_sql APPROVE\n{'#' * 72}")
    thread_approve = str(uuid7())
    q2 = (
        "Use run_sql ONLY: SELECT COUNT(DISTINCT reservation_id) AS bookings "
        "FROM reservations_hackathon WHERE TO_CHAR(stay_date,'YYYY-MM')='2026-07' "
        "AND reservation_status='Reserved' AND stay_date >= '2026-06-11'::date."
    )
    pending2 = run_question(agent, q2, thread_id=thread_approve)
    print_log(pending2, index=1)

    if pending2.interrupted:
        approved = run_question(
            agent,
            q2,
            thread_id=thread_approve,
            resume_decisions=[{"type": "approve"}],
        )
        print_log(approved, index=2)
    else:
        print("(run_sql did not interrupt — check model followed instructions)")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    _require_api_key()
    agent = build_agent()

    if not argv:
        run_suite(agent, SECTION_11_QUESTIONS, label="Section 11")
        run_suite(agent, HARD_QUESTIONS, label="Hard questions")
        return 0

    if argv[0] == "--multiturn":
        run_multiturn_demo(agent)
        return 0

    if argv[0] == "--hitl":
        run_hitl_demo(agent)
        return 0

    if argv[0] == "--presentation":
        run_suite(agent, PRESENTATION_SMOKE_QUESTIONS, label="Presentation smoke")
        return 0

    if argv[0] == "--all":
        run_suite(agent, SECTION_11_QUESTIONS, label="Section 11")
        run_suite(agent, HARD_QUESTIONS, label="Hard questions")
        run_multiturn_demo(agent)
        run_hitl_demo(agent)
        return 0

    question = " ".join(argv)
    print_log(run_question(agent, question))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
