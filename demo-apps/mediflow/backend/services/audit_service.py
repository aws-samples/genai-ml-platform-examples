"""Audit logging service for tool calls and conversations."""

import json

from backend.services.database import query_db, execute_db


def _next_sequence(session_id: str, table: str) -> int:
    """Return the next sequence_number for a session in the given table."""
    rows = query_db(
        f"SELECT MAX(sequence_number) AS max_seq FROM {table} WHERE session_id = ?",  # nosec B608
        (session_id,),
    )
    current = rows[0]["max_seq"] if rows and rows[0]["max_seq"] is not None else 0
    return current + 1


def log_tool_call(
    session_id: str,
    tool_name: str,
    tool_params: dict,
    result_summary: str,
    duration_ms: int = 0,
    success: bool = True,
    error_message: str | None = None,
) -> None:
    """Record a tool invocation in the audit log.

    Args:
        session_id: The conversation session identifier.
        tool_name: Name of the tool that was called.
        tool_params: Parameters passed to the tool (serialised as JSON).
        result_summary: Brief description of the result.
        duration_ms: Wall-clock time of the call in milliseconds.
        success: Whether the tool completed without error.
        error_message: Error details if the tool failed.
    """
    seq = _next_sequence(session_id, "tool_call_log")
    execute_db(
        """INSERT INTO tool_call_log
           (session_id, tool_name, tool_params, result_summary, duration_ms, sequence_number, success, error_message)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, tool_name, json.dumps(tool_params), result_summary, duration_ms, seq, int(success), error_message),
    )


def log_conversation_turn(
    session_id: str,
    role: str,
    content: str,
    tool_calls_in_turn: list = None,
) -> None:
    """Record a single conversation turn (user or assistant) in the audit log.

    Args:
        session_id: The conversation session identifier.
        role: Speaker role ("user", "assistant", "system").
        content: The message text.
        tool_calls_in_turn: Optional list of tool call references made
            during this turn, serialised as JSON.
    """
    seq = _next_sequence(session_id, "conversation_log")
    execute_db(
        """INSERT INTO conversation_log
           (session_id, role, content, tool_calls_in_turn, sequence_number)
           VALUES (?, ?, ?, ?, ?)""",
        (
            session_id,
            role,
            content,
            json.dumps(tool_calls_in_turn) if tool_calls_in_turn else None,
            seq,
        ),
    )


def get_tool_calls(session_id: str = None) -> list:
    """Retrieve tool call log entries, optionally filtered by session."""
    if session_id:
        return query_db(
            """SELECT * FROM tool_call_log
               WHERE session_id = ?
               ORDER BY sequence_number""",
            (session_id,),
        )
    return query_db("SELECT * FROM tool_call_log ORDER BY timestamp DESC")


def get_conversation(session_id: str) -> list:
    """Retrieve the full conversation log for a session in order."""
    return query_db(
        """SELECT * FROM conversation_log
           WHERE session_id = ?
           ORDER BY sequence_number""",
        (session_id,),
    )


def get_all_sessions() -> list:
    """Return a summary of all known sessions with counts and date ranges."""
    return query_db(
        """SELECT session_id,
                  COUNT(*) AS turn_count,
                  MIN(timestamp) AS first_turn,
                  MAX(timestamp) AS last_turn
           FROM conversation_log
           GROUP BY session_id
           ORDER BY last_turn DESC"""
    )
