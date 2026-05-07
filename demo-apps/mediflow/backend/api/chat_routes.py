"""Chat API routes with SSE streaming."""

import json
import re
import uuid
import logging
import asyncio
from datetime import datetime
from fastapi import APIRouter, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.agent.agent import create_agent
from backend.services.audit_service import log_conversation_turn
from backend.services.memory_service import extract_memories_from_conversation, get_memories_for_context
from backend.services.database import query_db

logger = logging.getLogger(__name__)
router = APIRouter()

# Pre-compiled pattern for patient IDs like "pat-001", "pat-042"
_PAT_ID_RE = re.compile(r"\bpat-\d{3}\b", re.IGNORECASE)


def _detect_patient_context(message: str) -> str | None:
    """Scan a user message for patient references and return formatted memories.

    Detection strategy (lightweight, no LLM):
    1. Explicit patient IDs (pat-XXX)
    2. Patient name matches against the patients table

    Returns the formatted memory string for the first matched patient, or None.
    """
    # 1. Check for explicit patient IDs
    id_match = _PAT_ID_RE.search(message)
    if id_match:
        patient_id = id_match.group(0).lower()
        context = get_memories_for_context(patient_id)
        if context:
            return context

    # 2. Check for patient names (fuzzy match against DB)
    # Only query if the message is long enough to contain a name
    if len(message) >= 3:
        patients = query_db(
            "SELECT id, first_name, last_name FROM patients ORDER BY last_name, first_name"
        )
        msg_lower = message.lower()
        for p in patients:
            first = p["first_name"].lower()
            last = p["last_name"].lower()
            full = f"{first} {last}"
            # Match full name or last name (last names are more specific)
            if full in msg_lower or (len(last) >= 3 and last in msg_lower):
                context = get_memories_for_context(p["id"])
                if context:
                    return context

    return None


class ChatMessage(BaseModel):
    message: str
    session_id: str | None = None
    day: int = 1
    history: list[dict] | None = None  # Prior turns: [{"role": "user"|"assistant", "content": "..."}]
    view_context: dict | None = None   # Current UI state: {"view": "patients", "params": {...}}


@router.post("/api/chat")
async def chat(msg: ChatMessage):
    """Stream an agent response via SSE."""
    session_id = msg.session_id or f"sess-{uuid.uuid4().hex[:8]}"

    # Log user turn
    log_conversation_turn(session_id, "user", msg.message)

    # Load enabled non-scheduled skills for agent behavioral context
    enabled_skills = query_db(
        "SELECT name, trigger_description, agent_prompt_template, tool_config "
        "FROM skills WHERE status = 'enabled' AND scheduled = 0"
    )

    # Inject patient memories if any enabled skill uses get_patient_memories
    uses_memories = any(
        'get_patient_memories' in (sk.get('tool_config') or '')
        for sk in enabled_skills
    )
    patient_context = _detect_patient_context(msg.message) if uses_memories else None

    agent = create_agent(
        day=msg.day,
        patient_context=patient_context,
        active_skills=enabled_skills or None,
        view_context=msg.view_context,
        conversation_history=msg.history,
        session_id=session_id,
    )

    async def event_stream():
        try:
            accumulated_text = ""
            tool_calls_made = []
            seen_tool_ids = set()
            text_buffer = ""
            last_flush = 0

            async for event in agent.stream_async(msg.message):
                if not isinstance(event, dict):
                    continue

                # Real-time text streaming — emit chunks to frontend
                if "data" in event and isinstance(event["data"], str):
                    chunk = event["data"]
                    accumulated_text += chunk
                    text_buffer += chunk
                    # Flush text buffer on sentence boundaries or every ~80 chars
                    import time
                    now = time.monotonic()
                    if (
                        text_buffer.rstrip().endswith(('.', '!', '?', ':', '\n'))
                        or len(text_buffer) >= 80
                        or (now - last_flush) > 0.3
                    ):
                        yield {
                            "event": "text_delta",
                            "data": json.dumps({
                                "delta": text_buffer,
                                "session_id": session_id,
                            }),
                        }
                        text_buffer = ""
                        last_flush = now

                # Tool invocation start — flush any pending text first, then emit tool_call
                if event.get("type") == "tool_use_stream" and "current_tool_use" in event:
                    # Flush remaining text before tool call
                    if text_buffer:
                        yield {
                            "event": "text_delta",
                            "data": json.dumps({"delta": text_buffer, "session_id": session_id}),
                        }
                        text_buffer = ""

                    tu = event["current_tool_use"]
                    tool_id = tu.get("toolUseId", "")
                    if tool_id and tool_id not in seen_tool_ids:
                        seen_tool_ids.add(tool_id)
                        tool_name = tu.get("name", "unknown")
                        tool_params = tu.get("input", {})
                        if isinstance(tool_params, str):
                            try:
                                tool_params = json.loads(tool_params)
                            except (json.JSONDecodeError, TypeError):
                                tool_params = {}
                        tool_calls_made.append({"tool": tool_name, "params": tool_params})
                        yield {
                            "event": "tool_call",
                            "data": json.dumps({"tool": tool_name, "params": tool_params}),
                        }

                # Tool stream events — ui_action events from async generator tools
                if event.get("type") == "tool_stream" and "tool_stream_event" in event:
                    tse = event["tool_stream_event"]
                    data = tse.get("data", {})
                    if isinstance(data, dict) and "ui_action" in data:
                        yield {
                            "event": "ui_action",
                            "data": json.dumps(data),
                        }

            # Flush any remaining text
            if text_buffer:
                yield {
                    "event": "text_delta",
                    "data": json.dumps({"delta": text_buffer, "session_id": session_id}),
                }

            # Log assistant turn
            log_conversation_turn(
                session_id, "assistant", accumulated_text,
                tool_calls_in_turn=tool_calls_made if tool_calls_made else None,
            )

            # Send final message (with full content for the frontend to finalize)
            yield {
                "event": "message",
                "data": json.dumps({
                    "session_id": session_id,
                    "content": accumulated_text,
                    "tool_calls": tool_calls_made,
                    "timestamp": datetime.now().isoformat(),
                }),
            }

            # Signal completion
            yield {"event": "done", "data": json.dumps({"session_id": session_id})}

            # Background: extract patient memories
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, extract_memories_from_conversation, session_id
                )
            except Exception:
                logger.debug("Memory extraction skipped for session %s", session_id)

        except Exception as e:
            logger.exception("Chat error")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e), "session_id": session_id}),
            }

    return EventSourceResponse(event_stream())


@router.post("/api/chat/sync")
async def chat_sync(msg: ChatMessage):
    """Non-streaming chat endpoint for simpler clients."""
    session_id = msg.session_id or f"sess-{uuid.uuid4().hex[:8]}"

    log_conversation_turn(session_id, "user", msg.message)

    # Load enabled non-scheduled skills for agent behavioral context
    enabled_skills = query_db(
        "SELECT name, trigger_description, agent_prompt_template, tool_config "
        "FROM skills WHERE status = 'enabled' AND scheduled = 0"
    )

    uses_memories = any(
        'get_patient_memories' in (sk.get('tool_config') or '')
        for sk in enabled_skills
    )
    patient_context = _detect_patient_context(msg.message) if uses_memories else None

    agent = create_agent(
        day=msg.day,
        patient_context=patient_context,
        active_skills=enabled_skills or None,
        view_context=msg.view_context,
        conversation_history=msg.history,
        session_id=session_id,
    )

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: agent(msg.message))

    response_text = ""
    tool_calls_made = []

    if hasattr(result, "message") and result.message:
        msg_obj = result.message
        content_blocks = (
            msg_obj.get("content", []) if isinstance(msg_obj, dict)
            else getattr(msg_obj, "content", [])
        )
        for block in content_blocks:
            if isinstance(block, dict):
                if "text" in block:
                    response_text += block["text"]
                tu = block.get("toolUse")
            else:
                if hasattr(block, "text"):
                    response_text += block.text
                tu = getattr(block, "tool_use", None)
            if tu:
                tool_info = {
                    "tool": tu.get("name", "unknown") if isinstance(tu, dict) else getattr(tu, "name", "unknown"),
                    "params": tu.get("input", {}) if isinstance(tu, dict) else getattr(tu, "input", {}),
                }
                tool_calls_made.append(tool_info)
        if not response_text and isinstance(msg_obj, str):
            response_text = msg_obj
    elif isinstance(result, str):
        response_text = result
    else:
        response_text = str(result)

    log_conversation_turn(
        session_id, "assistant", response_text,
        tool_calls_in_turn=tool_calls_made if tool_calls_made else None,
    )

    return {
        "session_id": session_id,
        "content": response_text,
        "tool_calls": tool_calls_made,
        "timestamp": datetime.now().isoformat(),
    }
