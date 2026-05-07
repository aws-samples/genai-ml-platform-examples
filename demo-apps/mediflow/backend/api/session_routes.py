"""Session API routes for viewing conversation history."""

from fastapi import APIRouter, HTTPException

from backend.services.audit_service import get_all_sessions, get_conversation, get_tool_calls

router = APIRouter()


@router.get("/api/sessions")
async def list_sessions():
    """List all conversation sessions with summary stats."""
    return {"sessions": get_all_sessions()}


@router.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get the full conversation and tool calls for a session."""
    conversation = get_conversation(session_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Session not found")

    tool_calls = get_tool_calls(session_id)

    return {
        "session_id": session_id,
        "conversation": conversation,
        "tool_calls": tool_calls,
    }
