"""UI activity tracking service — records frontend interactions for pattern detection."""

import json
from backend.services.database import query_db, execute_db, get_connection


def log_activity(
    session_id: str,
    action_type: str,
    action_detail: dict | str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    view: str | None = None,
    duration_ms: int | None = None,
    metadata: dict | str | None = None,
) -> None:
    """Record a single UI activity event."""
    execute_db(
        """INSERT INTO ui_activity_log
           (session_id, action_type, action_detail, entity_type, entity_id, view, duration_ms, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            action_type,
            json.dumps(action_detail) if isinstance(action_detail, dict) else action_detail,
            entity_type,
            entity_id,
            view,
            duration_ms,
            json.dumps(metadata) if isinstance(metadata, dict) else metadata,
        ),
    )


def log_activities(session_id: str, events: list[dict]) -> int:
    """Batch-insert multiple UI activity events. Returns count inserted."""
    if not events:
        return 0
    conn = get_connection()
    try:
        for ev in events:
            detail = ev.get("action_detail")
            meta = ev.get("metadata")
            conn.execute(
                """INSERT INTO ui_activity_log
                   (session_id, action_type, action_detail, entity_type, entity_id, view, duration_ms, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    ev["action_type"],
                    json.dumps(detail) if isinstance(detail, dict) else detail,
                    ev.get("entity_type"),
                    ev.get("entity_id"),
                    ev.get("view"),
                    ev.get("duration_ms"),
                    json.dumps(meta) if isinstance(meta, dict) else meta,
                ),
            )
        conn.commit()
        return len(events)
    finally:
        conn.close()


def get_activities(
    session_id: str | None = None,
    action_type: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    """Query UI activity events with optional filters."""
    clauses: list[str] = []
    params: list = []

    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)
    if action_type:
        clauses.append("action_type = ?")
        params.append(action_type)
    if start_time:
        clauses.append("timestamp >= ?")
        params.append(start_time)
    if end_time:
        clauses.append("timestamp <= ?")
        params.append(end_time)

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return query_db(
        f"SELECT * FROM ui_activity_log{where} ORDER BY timestamp",  # nosec B608
        tuple(params),
    )
