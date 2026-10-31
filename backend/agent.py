"""The PydanticAI agent behind POST /api/chat.

main.py imports run_agent from here and expects:
    run_agent(message: str) -> {"reply": str, "tools_used": list[str]}

Model: gpt-5.6-luna via Portkey. Two tools only: search_courses, web_search.
Every loop is appended to output/audit_trail.json.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.messages import TextPart, ThinkingPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from models import AgentResult, AuditEntry, ToolRecord
from tools import search_courses, web_search

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROMPT_PATH = HERE / "prompts" / "prompt.md"
AUDIT_PATH = ROOT / "output" / "audit_trail.json"

# The .env may sit in this Lecture 7 folder or one level up in the workspace.
load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")
load_dotenv(ROOT.parent.parent / ".env")

MODEL_NAME = "gpt-5.6-luna"
DEFAULT_BASE_URL = "https://api.portkey.ai/v1"
MISSING_KEY_MESSAGE = (
    "PORTKEY_API_KEY is not set. Add it to yale_som_courses_aymon/.env or the parent "
    "workspace .env (see .env.example), then restart uvicorn."
)


def _system_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return "You are the Yale course assistant. Never invent course details."


def build_agent() -> Agent:
    """Wire the Portkey-backed model to the two tools."""
    provider = OpenAIProvider(
        base_url=os.getenv("PORTKEY_BASE_URL", DEFAULT_BASE_URL),
        api_key=os.environ["PORTKEY_API_KEY"],
    )
    model = OpenAIChatModel(MODEL_NAME, provider=provider)
    return Agent(
        model=model,
        system_prompt=_system_prompt(),
        tools=[search_courses, web_search],
        defer_model_check=True,
    )


def _preview(value: Any, chars: int = 400) -> str:
    """A short, readable stand-in for a tool result in the audit trail."""
    if isinstance(value, (dict, list)):
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(value)
    else:
        text = str(value)
    text = " ".join(text.split())
    return text[:chars] + ("…" if len(text) > chars else "")


def _read_audit() -> tuple[list[dict], bool]:
    """Existing rows plus whether the file was unreadable."""
    if not AUDIT_PATH.exists():
        return [], False
    try:
        raw = AUDIT_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return [], True
    if not raw:
        return [], False
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        return [], True
    return (rows, False) if isinstance(rows, list) else ([rows], False)


def _append_audit(entry: AuditEntry) -> None:
    """Append one row. Earlier rows are never dropped."""
    rows, unreadable = _read_audit()
    if unreadable:
        # Preserve whatever was there before writing a fresh, valid file.
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        sidecar = AUDIT_PATH.with_name(f"audit_trail.unreadable-{stamp}.json")
        try:
            sidecar.write_bytes(AUDIT_PATH.read_bytes())
        except OSError:
            return
    rows.append(entry.model_dump())
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _harvest(result: Any) -> tuple[list[str], list[str], list[ToolRecord], str]:
    """Pull thoughts, tool calls and the stop reason out of the run messages."""
    thoughts: list[str] = []
    order: list[str] = []
    calls: dict[str, ToolRecord] = {}
    positional: list[ToolRecord] = []

    for message in result.all_messages():
        for part in getattr(message, "parts", []) or []:
            if isinstance(part, ThinkingPart) and part.content:
                thoughts.append(" ".join(str(part.content).split()))
            elif isinstance(part, ToolCallPart):
                record = ToolRecord(name=part.tool_name, args=part.args)
                key = part.tool_call_id or f"{part.tool_name}:{len(positional)}"
                calls[key] = record
                positional.append(record)
                order.append(part.tool_name)
            elif isinstance(part, ToolReturnPart):
                key = part.tool_call_id or ""
                record = calls.get(key)
                if record is None:
                    record = next(
                        (r for r in positional if r.name == part.tool_name and not r.result_preview),
                        None,
                    )
                if record is not None:
                    record.result_preview = _preview(part.content)

    response = getattr(result, "response", None)
    stop_reason = str(getattr(response, "finish_reason", "") or "") or "final_answer"
    return thoughts, order, positional, stop_reason


def _reply_text(result: Any) -> str:
    """The model's final text, falling back to the raw output."""
    output = getattr(result, "output", None)
    if isinstance(output, str) and output.strip():
        return output.strip()
    for message in reversed(result.all_messages()):
        for part in getattr(message, "parts", []) or []:
            if isinstance(part, TextPart) and part.content and str(part.content).strip():
                return str(part.content).strip()
    return "" if output is None else str(output)


def run_agent(message: str) -> dict:
    """Answer one question. Always returns the reply / tools_used contract."""
    asked_at = datetime.now(timezone.utc).isoformat()
    question = (message or "").strip()

    if not question:
        return AgentResult(reply="Ask me something about the Yale course catalog.").as_dict()

    if not os.getenv("PORTKEY_API_KEY"):
        _append_audit(
            AuditEntry(
                time=asked_at,
                user_message=question,
                reply=MISSING_KEY_MESSAGE,
                stop_reason="missing_api_key",
                model=MODEL_NAME,
            )
        )
        return AgentResult(reply=MISSING_KEY_MESSAGE).as_dict()

    try:
        result = build_agent().run_sync(question)
    except Exception as exc:
        failure = f"Agent error: {type(exc).__name__}: {exc}"
        _append_audit(
            AuditEntry(
                time=asked_at,
                user_message=question,
                reply=failure,
                stop_reason="exception",
                model=MODEL_NAME,
            )
        )
        return AgentResult(reply=failure).as_dict()

    thoughts, order, records, stop_reason = _harvest(result)
    reply = _reply_text(result)

    _append_audit(
        AuditEntry(
            time=asked_at,
            user_message=question,
            thoughts=thoughts,
            tools=records,
            reply=reply,
            stop_reason=stop_reason,
            model=MODEL_NAME,
        )
    )

    # Preserve call order, drop repeats, keep only the two real tool names.
    seen: list[str] = []
    for name in order:
        if name not in seen:
            seen.append(name)
    return AgentResult(reply=reply, tools_used=seen).as_dict()
