"""Execution history persistence for skill runs."""

import json
import uuid
from datetime import datetime, timezone

from backend.services.database import execute_db, query_db


def create_execution(skill_id: str, trigger: str = "manual", items_total: int = 0) -> str:
    execution_id = str(uuid.uuid4())
    execute_db(
        "INSERT INTO skill_executions (id, skill_id, started_at, status, trigger, items_total) VALUES (?, ?, ?, 'running', ?, ?)",
        (execution_id, skill_id, datetime.now(timezone.utc).isoformat(), trigger, items_total),
    )
    return execution_id


def record_item(
    execution_id: str,
    item_index: int,
    entity_id: str | None = None,
    entity_name: str | None = None,
    status: str = "success",
    tools_called: list[str] | None = None,
    duration_ms: int | None = None,
) -> None:
    item_id = str(uuid.uuid4())
    execute_db(
        "INSERT INTO skill_execution_items (id, execution_id, item_index, entity_id, entity_name, status, tools_called, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            item_id,
            execution_id,
            item_index,
            entity_id,
            entity_name,
            status,
            json.dumps(tools_called) if tools_called else None,
            duration_ms,
        ),
    )


def complete_execution(
    execution_id: str,
    status: str = "completed",
    items_succeeded: int = 0,
    items_failed: int = 0,
    duration_ms: int | None = None,
    summary: str | None = None,
    error: str | None = None,
    tokens_input: int | None = None,
    tokens_output: int | None = None,
    estimated_cost_usd: float | None = None,
    llm_latency_ms: int | None = None,
) -> None:
    execute_db(
        """UPDATE skill_executions
           SET status = ?, completed_at = ?, items_succeeded = ?, items_failed = ?,
               duration_ms = ?, summary = ?, error = ?,
               tokens_input = ?, tokens_output = ?, estimated_cost_usd = ?, llm_latency_ms = ?
           WHERE id = ?""",
        (
            status,
            datetime.now(timezone.utc).isoformat(),
            items_succeeded,
            items_failed,
            duration_ms,
            summary,
            error,
            tokens_input,
            tokens_output,
            estimated_cost_usd,
            llm_latency_ms,
            execution_id,
        ),
    )


def get_executions(skill_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
    return query_db(
        "SELECT * FROM skill_executions WHERE skill_id = ? ORDER BY started_at DESC LIMIT ? OFFSET ?",
        (skill_id, limit, offset),
    )


def get_execution_detail(execution_id: str) -> dict | None:
    rows = query_db("SELECT * FROM skill_executions WHERE id = ?", (execution_id,))
    if not rows:
        return None
    execution = rows[0]
    execution["items"] = query_db(
        "SELECT * FROM skill_execution_items WHERE execution_id = ? ORDER BY item_index",
        (execution_id,),
    )
    return execution
